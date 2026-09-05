"use client";

import { FormEvent, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  BookOpen,
  FileSearch,
  FileText,
  FileUp,
  LoaderCircle,
  Search,
  Send,
  Sparkles,
} from "lucide-react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { api } from "@/lib/api";
import { useAuthStore } from "@/stores/auth-store";
import type { DocumentSource } from "@/types/api";
import { Button } from "@/components/ui/button";

const delay = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms));

export default function DocumentsPage() {
  const token = useAuthStore((state) => state.accessToken)!,
    queryClient = useQueryClient(),
    fileInput = useRef<HTMLInputElement>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null),
    [query, setQuery] = useState(""),
    [mode, setMode] = useState<"ask" | "search">("ask"),
    [answer, setAnswer] = useState(""),
    [sources, setSources] = useState<DocumentSource[]>([]),
    [showSources, setShowSources] = useState(false),
    [notice, setNotice] = useState(""),
    [typing, setTyping] = useState(false);
  const typingRun = useRef(0);
  const documents = useQuery({
    queryKey: ["documents"],
    queryFn: () => api.documents(token),
  });
  const selected =
    documents.data?.items.find((item) => item.id === selectedId) || null;
  const upload = useMutation({
    mutationFn: async (file: File) => {
      const created = await api.uploadDocument(file, token);
      setNotice(`Processing ${file.name}…`);
      for (let i = 0; i < 120; i++) {
        await delay(1000);
        const job = await api.documentJob(created.job_id, token);
        if (job.status === "completed") return created.document;
        if (job.status === "failed")
          throw new Error(job.error_message || "Document processing failed");
      }
      throw new Error("Processing is taking longer than expected");
    },
    onSuccess: (document) => {
      setSelectedId(document.id);
      setNotice(`${document.title} is ready.`);
      queryClient.invalidateQueries({ queryKey: ["documents"] });
    },
    onError: (error) => setNotice(error.message),
  });
  const ask = useMutation({
    mutationFn: () => api.askDocument(query.trim(), selectedId, token),
    onSuccess: (result) => {
      typeAnswer(result.answer);
      setSources(result.sources);
      setShowSources(false);
      setQuery("");
    },
  });
  const search = useMutation({
    mutationFn: () => api.searchDocument(query.trim(), selectedId, token),
    onSuccess: (result) => {
      setAnswer("");
      setSources(result);
      setShowSources(true);
    },
  });
  const summarize = useMutation({
    mutationFn: () => api.summarizeDocument(selectedId!, token),
    onSuccess: (result) => {
      typeAnswer(result.summary);
      setSources(result.sources);
      setShowSources(false);
    },
  });
  function submit(event: FormEvent) {
    event.preventDefault();
    if (!query.trim()) return;
    if (mode === "ask") ask.mutate();
    else search.mutate();
  }
  async function typeAnswer(content: string) {
    const run = ++typingRun.current;
    setAnswer("");
    setTyping(true);
    const step = content.length > 2500 ? 12 : content.length > 1000 ? 7 : 4;
    for (let index = step; index < content.length; index += step) {
      if (run !== typingRun.current) return;
      setAnswer(content.slice(0, index));
      await delay(12);
    }
    if (run === typingRun.current) {
      setAnswer(content);
      setTyping(false);
    }
  }
  const busy = ask.isPending || search.isPending || summarize.isPending || typing;
  return (
    <section className="documents-page">
      <header className="documents-head">
        <div>
          <span className="kicker">DOCUMENT INTELLIGENCE</span>
          <h1>
            Ask better questions
            <br />
            of <em>your files.</em>
          </h1>
          <p>
            Upload private notes and reports, search their meaning, and receive
            grounded answers with traceable source passages.
          </p>
        </div>
        <div className="documents-mark">
          <FileText />
          <span>
            Private by
            <br />
            default
          </span>
        </div>
      </header>
      <div className="documents-workspace">
        <aside className="document-library">
          <div className="document-library-head">
            <div>
              <strong>My Documents</strong>
              <small>{documents.data?.total || 0} files</small>
            </div>
            <Button
              size="sm"
              onClick={() => fileInput.current?.click()}
              disabled={upload.isPending}
            >
              {upload.isPending ? (
                <LoaderCircle className="spin" />
              ) : (
                <FileUp />
              )}{" "}
              Upload
            </Button>
            <input
              ref={fileInput}
              className="hidden-file-input"
              type="file"
              accept=".pdf,.docx,.txt,.png,.jpg,.jpeg,.tif,.tiff"
              onChange={(event) => {
                const file = event.target.files?.[0];
                if (file) upload.mutate(file);
                event.target.value = "";
              }}
            />
          </div>
          {notice && <p className="document-notice">{notice}</p>}
          {documents.isLoading && (
            <p className="document-muted">Loading your library…</p>
          )}
          {!documents.isLoading && !documents.data?.items.length && (
            <div className="document-empty">
              <FileUp />
              <strong>No documents yet</strong>
              <p>Upload your first note or report.</p>
            </div>
          )}
          {documents.data?.items.map((item) => (
            <button
              key={item.id}
              className={`document-row ${selectedId === item.id ? "selected" : ""}`}
              onClick={() => {
                typingRun.current += 1;
                setTyping(false);
                setSelectedId(item.id);
                setAnswer("");
                setSources([]);
                setShowSources(false);
              }}
            >
              <FileText />
              <span>
                <strong>{item.title}</strong>
                <small>
                  {item.status}
                  {item.word_count ? ` · ${item.word_count} words` : ""}
                </small>
              </span>
              <i className={item.status} />
            </button>
          ))}
        </aside>
        <main className="document-console">
          {!selected ? (
            <div className="document-welcome">
              <FileSearch />
              <h2>Select a document</h2>
              <p>
                Choose one file for focused answers, or search across your
                entire private library.
              </p>
            </div>
          ) : (
            <>
              <header>
                <div>
                  <span>SELECTED DOCUMENT</span>
                  <h2>{selected.title}</h2>
                  <p>
                    {selected.document_type?.toUpperCase()} ·{" "}
                    {selected.word_count || 0} words
                    {selected.page_count
                      ? ` · ${selected.page_count} pages`
                      : ""}
                  </p>
                </div>
                <Button
                  variant="outline"
                  onClick={() => summarize.mutate()}
                  disabled={busy}
                >
                  <Sparkles /> Summarize
                </Button>
              </header>
              {(ask.error || search.error || summarize.error) && (
                <p className="form-error">
                  {(ask.error || search.error || summarize.error)?.message}
                </p>
              )}
              {busy && (
                <div className="document-thinking">
                  <LoaderCircle className="spin" /> EVA is reading your sources…
                </div>
              )}
              {answer && (
                <article className={`document-answer ${typing ? "typing" : ""}`}>
                  <span>EVA ANSWER</span>
                  <ReactMarkdown remarkPlugins={[remarkGfm]}>
                    {answer}
                  </ReactMarkdown>
                </article>
              )}
              {sources.length > 0 && !answer && (
                <section className="source-results">
                  <h3>Relevant passages</h3>
                  {sources.map((source, index) => (
                    <article key={source.chunk_id}>
                      <header>
                        <strong>[Source {index + 1}]</strong>
                        <span>
                          {Math.round(source.score * 100)}% match
                          {source.page_number
                            ? ` · page ${source.page_number}`
                            : ""}
                        </span>
                      </header>
                      <p>{source.content}</p>
                    </article>
                  ))}
                </section>
              )}
              {sources.length > 0 && answer && (
                <div className="source-toggle">
                  <Button variant="outline" onClick={() => setShowSources(value => !value)}>
                    {showSources ? "Hide sources used" : `Show sources used (${sources.length})`}
                  </Button>
                  {showSources && <section className="source-results"><h3>Sources used</h3>{sources.map((source,index)=><article key={source.chunk_id}><header><strong>[Source {index+1}]</strong><span>{Math.round(source.score*100)}% match{source.page_number?` · page ${source.page_number}`:""}</span></header><p>{source.content}</p></article>)}</section>}
                </div>
              )}
              {!answer && !sources.length && !busy && (
                <div className="document-prompt">
                  <Sparkles />
                  <h3>Understand this document</h3>
                  <p>
                    Ask a question, create a faithful summary, or locate
                    passages by meaning—not only exact words.
                  </p>
                </div>
              )}
              <form className="document-query document-query-bottom" onSubmit={submit}>
                <div className="query-modes">
                  <button type="button" className={mode === "ask" ? "active" : ""} onClick={() => setMode("ask")}><BookOpen /> Ask EVA</button>
                  <button type="button" className={mode === "search" ? "active" : ""} onClick={() => setMode("search")}><Search /> Semantic search</button>
                </div>
                <div>
                  <input value={query} onChange={(event) => setQuery(event.target.value)} placeholder={mode === "ask" ? "Ask another question about this document…" : "Search for concepts or passages…"}/>
                  <Button size="icon" disabled={!query.trim() || busy} aria-label={mode === "ask" ? "Ask question" : "Search document"}>{busy ? <LoaderCircle className="spin" /> : <Send />}</Button>
                </div>
              </form>
            </>
          )}
        </main>
      </div>
    </section>
  );
}
