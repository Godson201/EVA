"use client";

import { FormEvent, useEffect, useMemo, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { ArrowUp, Bot, Check, Copy, ExternalLink, FileAudio, FilePlus2, FileText, Globe2, LoaderCircle, Mic, Plus, Sparkles, Square, Volume2 } from "lucide-react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { api } from "@/lib/api";
import { useAuthStore } from "@/stores/auth-store";
import type { Message } from "@/types/api";
import { Button } from "@/components/ui/button";

const starters = ["Sobanura ingingo ikomeye mu buryo bworoshye", "Mfasha kunoza inyandiko yanjye", "Hindura ubutumwa bube umwuga"];
const delay = (milliseconds: number) => new Promise((resolve) => setTimeout(resolve, milliseconds));
type SpeechRecognitionResultLike = { isFinal: boolean; 0: { transcript: string } };
type SpeechRecognitionEventLike = { resultIndex: number; results: ArrayLike<SpeechRecognitionResultLike> };
type SpeechRecognitionLike = { lang: string; continuous: boolean; interimResults: boolean; onresult: ((event: SpeechRecognitionEventLike) => void) | null; onerror: (() => void) | null; onend: (() => void) | null; start: () => void; stop: () => void };

export function ChatWorkspace({ initialId = null }: { initialId?: string | null }) {
  const token = useAuthStore((state) => state.accessToken)!; const user = useAuthStore((state) => state.user)!;
  const router = useRouter();
  const queryClient = useQueryClient(); const [conversationId, setConversationId] = useState<string | null>(initialId); const [draft, setDraft] = useState(""); const end = useRef<HTMLDivElement>(null);
  const documentInput = useRef<HTMLInputElement>(null); const audioInput = useRef<HTMLInputElement>(null);
  const speechRecognition = useRef<SpeechRecognitionLike | null>(null); const recordingTranscript = useRef(""); const liveSpeechRef = useRef(""); const submitVoiceOnEnd = useRef(false);
  const activeSendId = useRef<string | null>(null);
  const [attachmentMenu, setAttachmentMenu] = useState(false); const [recording, setRecording] = useState(false); const [uploadStatus, setUploadStatus] = useState("");
  const [audioLanguage, setAudioLanguage] = useState<"rw" | "en">("rw");
  const [audioPreviewUrl, setAudioPreviewUrl] = useState("");
  const [pendingDocument, setPendingDocument] = useState<{ title: string; text: string } | null>(null);
  const [pendingUser, setPendingUser] = useState(""); const [streamedAnswer, setStreamedAnswer] = useState(""); const [liveSearch, setLiveSearch] = useState(false); const [liveSpeech, setLiveSpeech] = useState("");
  const detail = useQuery({ queryKey: ["conversation", conversationId], queryFn: () => api.conversation(conversationId!, token), enabled: !!conversationId });
  const send = useMutation({
    mutationFn: async (content: string) => {
      let id = conversationId;
      if (!id) { const created = await api.createConversation(token, content.slice(0, 52)); id = created.id; setConversationId(id); }
      activeSendId.current = id;
      await api.streamMessage(id, content, token, (chunk) => setStreamedAnswer((answer) => answer + chunk), liveSearch);
      return { id };
    },
    onSettled: async (result) => {
      const id = result?.id || activeSendId.current || conversationId;
      if (id) await queryClient.invalidateQueries({ queryKey: ["conversation", id] });
      await queryClient.invalidateQueries({ queryKey: ["conversations"] });
      setPendingUser(""); setStreamedAnswer(""); activeSendId.current = null;
    },
  });
  const uploadDocument = useMutation({
    mutationFn: async (file: File) => {
      const uploaded = await api.uploadDocument(file, token); setUploadStatus(`Processing ${file.name}…`);
      for (let attempt = 0; attempt < 90; attempt++) {
        await delay(1000); const job = await api.documentJob(uploaded.job_id, token);
        if (job.status === "completed") return api.documentContent(uploaded.document.id, token);
        if (job.status === "failed") throw new Error(job.error_message || "Document processing failed");
      }
      throw new Error("The document is still processing. You can find it in Documents.");
    },
    onSuccess: (document) => {
      const text = document.text.length > 12000 ? `${document.text.slice(0, 12000)}\n\n[Document shortened for rewriting]` : document.text;
      setPendingDocument({ title: document.title, text });
      setDraft("Rewrite this document faithfully, then explain it clearly.");
      setUploadStatus(`${document.title} is attached. EVA will wait until you press Enter or Send.`);
      queryClient.invalidateQueries({ queryKey: ["documents"] });
    },
    onError: (reason) => setUploadStatus(reason instanceof Error ? reason.message : "Document upload failed"),
  });
  const transcribeAudio = useMutation({
    mutationFn: async (file: File) => {
      setAudioPreviewUrl(URL.createObjectURL(file));
      const uploaded = await api.uploadAudio(file, token, audioLanguage); setUploadStatus(`Transcribing ${file.name} as ${audioLanguage === "rw" ? "Kinyarwanda" : "English"}…`);
      for (let attempt = 0; attempt < 120; attempt++) {
        await delay(1000); const job = await api.speechJob(uploaded.job_id, token);
        if (job.status === "completed") return api.transcription(uploaded.transcription.id, token);
        if (job.status === "failed") throw new Error(job.error_message || "Audio transcription failed");
      }
      throw new Error("Audio transcription is taking longer than expected.");
    },
    onSuccess: (transcription) => { const text = transcription.corrected_text || transcription.raw_text || ""; setDraft((current) => current ? `${current}\n${text}` : text); setUploadStatus("Audio transcribed. Review the text, then press Send."); },
    onError: (reason) => setUploadStatus(reason instanceof Error ? reason.message : "Audio upload failed"),
  });
  const messages = useMemo(() => detail.data?.messages || [], [detail.data?.messages]);
  useEffect(() => { end.current?.scrollIntoView({ behavior: "smooth" }); }, [messages, pendingUser, streamedAnswer, liveSpeech]);
  useEffect(() => () => { if (audioPreviewUrl) URL.revokeObjectURL(audioPreviewUrl); }, [audioPreviewUrl]);
  function submit(event?: FormEvent) {
    event?.preventDefault();
    const instruction = draft.trim() || (pendingDocument ? "Rewrite this document faithfully, then explain it clearly." : "");
    if (!instruction || send.isPending) return;
    const content = pendingDocument
      ? `${instruction}\n\nFollow this response structure:\n1. Rewritten content — preserve the original meaning and all important details; do not invent information.\n2. Explanation — explain the content clearly in plain language.\n\nAttached document: ${pendingDocument.title}\n\n${pendingDocument.text}`
      : instruction;
    setDraft(""); setPendingUser(pendingDocument ? `${instruction}\n\n📎 ${pendingDocument.title}` : instruction); setPendingDocument(null); setStreamedAnswer(""); send.mutate(content);
  }
  function newChat() { submitVoiceOnEnd.current = false; liveSpeechRef.current = ""; speechRecognition.current?.stop(); setRecording(false); setLiveSpeech(""); setConversationId(null); setDraft(""); setPendingDocument(null); router.push("/chat"); }
  function sendVoiceTurn(text: string) {
    const content = text.trim();
    if (!content || send.isPending) { if (!content) setUploadStatus("I did not hear any words. Please try again."); return; }
    setLiveSpeech(""); liveSpeechRef.current = ""; setPendingUser(content); setStreamedAnswer(""); setUploadStatus(""); send.mutate(content);
  }
  async function toggleRecording() {
    if (recording && speechRecognition.current) {
      submitVoiceOnEnd.current = true; speechRecognition.current.stop(); setRecording(false);
      setUploadStatus("Sending your voice message to EVA..."); return;
    }
    try {
      const browser = window as typeof window & { SpeechRecognition?: new () => SpeechRecognitionLike; webkitSpeechRecognition?: new () => SpeechRecognitionLike };
      const Recognition = browser.SpeechRecognition || browser.webkitSpeechRecognition;
      if (!Recognition) { setUploadStatus("Live speech is not supported by this browser. Use Chrome or Edge, or upload an audio file."); return; }
      recordingTranscript.current = ""; liveSpeechRef.current = ""; submitVoiceOnEnd.current = false; setLiveSpeech("");
      const recognition = new Recognition(); speechRecognition.current = recognition;
      recognition.lang = audioLanguage === "rw" ? "rw-RW" : "en-US"; recognition.continuous = true; recognition.interimResults = true;
      recognition.onresult = (event) => {
        let finalText = recordingTranscript.current; let interimText = "";
        for (let index = event.resultIndex; index < event.results.length; index++) {
          const result = event.results[index];
          if (result.isFinal) finalText += `${result[0].transcript.trim()} `; else interimText += result[0].transcript;
        }
        recordingTranscript.current = finalText;
        const spoken = `${finalText}${interimText}`.trim(); liveSpeechRef.current = spoken; setLiveSpeech(spoken);
      };
      recognition.onerror = () => { setRecording(false); setUploadStatus("EVA could not continue listening. Check microphone permission and try again."); };
      recognition.onend = () => {
        const shouldSubmit = submitVoiceOnEnd.current || Boolean(liveSpeechRef.current.trim()); submitVoiceOnEnd.current = false; speechRecognition.current = null; setRecording(false);
        if (shouldSubmit) sendVoiceTurn(liveSpeechRef.current);
      };
      recognition.start(); setRecording(true); setUploadStatus("Listening live... Select Stop and EVA will answer immediately.");
    } catch { setUploadStatus("Microphone access was denied. Allow microphone permission and try again."); }
  }
  return <section className="chat-shell">
    <header className="topbar"><div><span className="mobile-brand">EVA</span><p>{conversationId ? detail.data?.title || "Conversation" : "New conversation"}</p></div><Button variant="outline" size="sm" onClick={newChat}><Plus size={15}/> New</Button></header>
    <div className="message-scroll">
      {!conversationId && <div className="welcome"><div className="welcome-symbol"><Bot size={34}/></div><span className="kicker">UMUFASHA WAWE MU KINYARWANDA NO MU CYONGEREZA</span><h1>Muraho, {user.full_name?.split(" ")[0] || user.username}.</h1><p>Ni iki wifuza kumenya, gukora cyangwa guhindura uyu munsi?</p><div className="starter-grid">{starters.map((item, index) => <button key={item} onClick={() => setDraft(item)}><span>0{index + 1}</span>{item}<ArrowUp size={15}/></button>)}</div></div>}
      {messages.map((message) => <MessageBubble key={message.id} message={message}/>)}
      {recording && <article className="message user voice-live"><div className="message-body"><span><Mic size={12}/> LIVE VOICE</span><p>{liveSpeech || "Listening..."}</p><div className="voice-live-wave"><i/><i/><i/><i/><i/></div></div></article>}
      {pendingUser && <article className="message user pending-message"><div className="message-body"><span>YOU</span><p>{pendingUser}</p></div></article>}
      {send.isPending && <article className="message assistant streaming-message"><div className="message-icon"><Sparkles size={16}/></div><div className="message-body"><span>EVA</span>{streamedAnswer ? <MarkdownContent content={streamedAnswer}/> : <div className="thinking"><i/><i/><i/></div>}</div></article>}
      {send.error && <p className="chat-error" role="alert">{send.error.message}</p>}<div ref={end}/>
    </div>
    <form className="composer-wrap" onSubmit={submit}>
      {audioPreviewUrl && <div className="audio-preview"><span>Audio playback</span><audio controls src={audioPreviewUrl}/><button type="button" onClick={() => setAudioPreviewUrl("")} aria-label="Close audio playback">×</button></div>}
      {uploadStatus && <div className="upload-status">{(uploadDocument.isPending || transcribeAudio.isPending) && <LoaderCircle className="spin"/>}<span>{uploadStatus}</span><button type="button" onClick={() => setUploadStatus("")} aria-label="Dismiss upload status">×</button></div>}
      <div className="composer">{pendingDocument && <div className="document-chip"><FileText/><span><strong>{pendingDocument.title}</strong><small>Ready to rewrite and explain</small></span><button type="button" onClick={() => setPendingDocument(null)} aria-label="Remove attached document">×</button></div>}<textarea value={draft} onChange={(event) => setDraft(event.target.value)} onKeyDown={(event) => { if (event.key === "Enter" && !event.shiftKey) { event.preventDefault(); submit(); } }} placeholder="Message EVA in English or Kinyarwanda…" rows={1} aria-label="Message EVA"/><div className="composer-actions"><div className="media-actions">
        <div className="audio-language" role="group" aria-label="Recording language"><button type="button" className={audioLanguage === "rw" ? "active" : ""} onClick={() => setAudioLanguage("rw")} title="Transcribe in Kinyarwanda">RW</button><button type="button" className={audioLanguage === "en" ? "active" : ""} onClick={() => setAudioLanguage("en")} title="Transcribe in English">EN</button></div>
        <div className="attach-control"><Button type="button" variant="ghost" size="icon" aria-label="Upload a document or audio file" title="Upload file" onClick={() => setAttachmentMenu((open) => !open)}><FilePlus2 size={19}/></Button>{attachmentMenu && <div className="attachment-menu"><button type="button" onClick={() => { setAttachmentMenu(false); documentInput.current?.click(); }}><FileText/> Upload document</button><button type="button" onClick={() => { setAttachmentMenu(false); audioInput.current?.click(); }}><FileAudio/> Upload audio</button></div>}</div>
        <Button type="button" variant="ghost" size="icon" className={liveSearch ? "live-search-button active" : "live-search-button"} aria-pressed={liveSearch} aria-label="Use live news sources" title="Use live news sources" onClick={() => setLiveSearch(value => !value)}><Globe2 size={19}/></Button>
        <Button type="button" variant="ghost" size="icon" className={recording ? "recording-button" : ""} aria-label={recording ? "Stop recording" : "Record audio"} title={recording ? "Stop recording" : "Record audio"} onClick={toggleRecording}>{recording ? <Square size={16}/> : <Mic size={19}/>}</Button>
      </div><Button size="icon" aria-label="Send message" disabled={(!draft.trim() && !pendingDocument) || send.isPending}><ArrowUp size={19}/></Button></div></div>
      <input ref={documentInput} className="hidden-file-input" type="file" accept=".pdf,.docx,.txt,.png,.jpg,.jpeg,.tif,.tiff,text/plain,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document,image/png,image/jpeg,image/tiff" onChange={(event) => { const file = event.target.files?.[0]; if (file) uploadDocument.mutate(file); event.target.value = ""; }}/>
      <input ref={audioInput} className="hidden-file-input" type="file" accept="audio/*,.mp3,.wav,.ogg,.m4a,.webm" onChange={(event) => { const file = event.target.files?.[0]; if (file) transcribeAudio.mutate(file); event.target.value = ""; }}/>
      <small>EVA can make mistakes. Verify important information.</small>
    </form>
  </section>;
}

function MessageBubble({ message }: { message: Message }) {
  const assistant = message.role === "assistant";
  const [speaking, setSpeaking] = useState(false);
  const [copied, setCopied] = useState(false);
  const sources = message.metadata?.live_sources || [];
  function listen() {
    if (!("speechSynthesis" in window)) return;
    window.speechSynthesis.cancel();
    if (speaking) { setSpeaking(false); return; }
    const cleanText = message.content.replace(/[#*_`>|~-]/g, " ").replace(/\s+/g, " ").trim();
    const utterance = new SpeechSynthesisUtterance(cleanText);
    utterance.lang = message.language === "rw" ? "rw-RW" : "en-US";
    utterance.onend = () => setSpeaking(false);
    utterance.onerror = () => setSpeaking(false);
    setSpeaking(true); window.speechSynthesis.speak(utterance);
  }
  async function copyResult() {
    await navigator.clipboard.writeText(message.content); setCopied(true);
    window.setTimeout(() => setCopied(false), 1800);
  }
  return <article className={`message ${assistant ? "assistant" : "user"}`}>
    {assistant && <div className="message-icon"><Sparkles size={16}/></div>}
    <div className="message-body">
      <span>{assistant ? "EVA" : "YOU"}</span>
      {assistant ? <MarkdownContent content={message.content}/> : <p>{message.content}</p>}
      {assistant && sources.length > 0 && <details className="live-sources"><summary>Live sources used ({sources.length})</summary><div>{sources.map(source => <a key={source.url} href={source.url} target="_blank" rel="noreferrer"><span><strong>[{source.id}] {source.title}</strong><small>{source.domain}{source.published_at ? ` · ${new Date(source.published_at).toLocaleString()}` : ""}{source.country ? ` · ${source.country}` : ""}</small></span><ExternalLink size={14}/></a>)}</div></details>}
      {assistant && <div className="message-actions"><button type="button" className={`listen ${speaking ? "speaking" : ""}`} onClick={listen} aria-label={speaking ? "Stop reading response" : "Read response aloud"}><Volume2 size={14}/> {speaking ? "Stop" : "Listen"}</button><button type="button" className="copy-result" onClick={copyResult} aria-label="Copy EVA response">{copied ? <Check size={14}/> : <Copy size={14}/>} {copied ? "Copied" : "Copy"}</button></div>}
    </div>
  </article>;
}

function MarkdownContent({ content }: { content: string }) {
  return <div className="message-markdown"><ReactMarkdown remarkPlugins={[remarkGfm]}>{content}</ReactMarkdown></div>;
}
