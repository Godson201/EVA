"use client";

import { FormEvent, useEffect, useMemo, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { ArrowUp, Bot, FileAudio, FilePlus2, FileText, LoaderCircle, Mic, Plus, Sparkles, Square, Volume2 } from "lucide-react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { api } from "@/lib/api";
import { useAuthStore } from "@/stores/auth-store";
import type { Message } from "@/types/api";
import { Button } from "@/components/ui/button";

const starters = ["Explain a difficult idea simply", "Sobanura inyandiko yanjye", "Translate a professional reply"];
const delay = (milliseconds: number) => new Promise((resolve) => setTimeout(resolve, milliseconds));

export function ChatWorkspace({ initialId = null }: { initialId?: string | null }) {
  const token = useAuthStore((state) => state.accessToken)!; const user = useAuthStore((state) => state.user)!;
  const router = useRouter();
  const queryClient = useQueryClient(); const [conversationId, setConversationId] = useState<string | null>(initialId); const [draft, setDraft] = useState(""); const end = useRef<HTMLDivElement>(null);
  const documentInput = useRef<HTMLInputElement>(null); const audioInput = useRef<HTMLInputElement>(null);
  const recorder = useRef<MediaRecorder | null>(null); const recordingChunks = useRef<Blob[]>([]);
  const activeSendId = useRef<string | null>(null);
  const [attachmentMenu, setAttachmentMenu] = useState(false); const [recording, setRecording] = useState(false); const [uploadStatus, setUploadStatus] = useState("");
  const [audioLanguage, setAudioLanguage] = useState<"rw" | "en">("rw");
  const [pendingUser, setPendingUser] = useState(""); const [streamedAnswer, setStreamedAnswer] = useState("");
  const detail = useQuery({ queryKey: ["conversation", conversationId], queryFn: () => api.conversation(conversationId!, token), enabled: !!conversationId });
  const send = useMutation({
    mutationFn: async (content: string) => {
      let id = conversationId;
      if (!id) { const created = await api.createConversation(token, content.slice(0, 52)); id = created.id; setConversationId(id); }
      activeSendId.current = id;
      await api.streamMessage(id, content, token, (chunk) => setStreamedAnswer((answer) => answer + chunk));
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
        if (job.status === "completed") return uploaded.document;
        if (job.status === "failed") throw new Error(job.error_message || "Document processing failed");
      }
      throw new Error("The document is still processing. You can find it in Documents.");
    },
    onSuccess: (document) => { setUploadStatus(`${document.title} is ready in Documents.`); queryClient.invalidateQueries({ queryKey: ["documents"] }); },
    onError: (reason) => setUploadStatus(reason instanceof Error ? reason.message : "Document upload failed"),
  });
  const transcribeAudio = useMutation({
    mutationFn: async (file: File) => {
      const uploaded = await api.uploadAudio(file, token, audioLanguage); setUploadStatus(`Transcribing ${file.name} as ${audioLanguage === "rw" ? "Kinyarwanda" : "English"}…`);
      for (let attempt = 0; attempt < 120; attempt++) {
        await delay(1000); const job = await api.speechJob(uploaded.job_id, token);
        if (job.status === "completed") return api.transcription(uploaded.transcription.id, token);
        if (job.status === "failed") throw new Error(job.error_message || "Audio transcription failed");
      }
      throw new Error("Audio transcription is taking longer than expected.");
    },
    onSuccess: (transcription) => { const text = transcription.corrected_text || transcription.raw_text || ""; setDraft((current) => current ? `${current}\n${text}` : text); setUploadStatus("Audio transcribed. Review the text, then send it."); },
    onError: (reason) => setUploadStatus(reason instanceof Error ? reason.message : "Audio upload failed"),
  });
  const messages = useMemo(() => detail.data?.messages || [], [detail.data?.messages]);
  useEffect(() => { end.current?.scrollIntoView({ behavior: "smooth" }); }, [messages, pendingUser, streamedAnswer]);
  function submit(event?: FormEvent) { event?.preventDefault(); const content = draft.trim(); if (!content || send.isPending) return; setDraft(""); setPendingUser(content); setStreamedAnswer(""); send.mutate(content); }
  function newChat() { setConversationId(null); setDraft(""); router.push("/chat"); }
  async function toggleRecording() {
    if (recording && recorder.current) { recorder.current.stop(); setRecording(false); return; }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const mediaRecorder = new MediaRecorder(stream); recorder.current = mediaRecorder; recordingChunks.current = [];
      mediaRecorder.ondataavailable = (event) => { if (event.data.size) recordingChunks.current.push(event.data); };
      mediaRecorder.onstop = () => { const blob = new Blob(recordingChunks.current, { type: mediaRecorder.mimeType || "audio/webm" }); stream.getTracks().forEach((track) => track.stop()); transcribeAudio.mutate(new File([blob], `eva-recording-${Date.now()}.webm`, { type: blob.type })); };
      mediaRecorder.start(); setRecording(true); setUploadStatus("Recording… select Stop when you finish.");
    } catch { setUploadStatus("Microphone access was denied. Allow microphone permission and try again."); }
  }
  return <section className="chat-shell">
    <header className="topbar"><div><span className="mobile-brand">EVA</span><p>{conversationId ? detail.data?.title || "Conversation" : "New conversation"}</p></div><Button variant="outline" size="sm" onClick={newChat}><Plus size={15}/> New</Button></header>
    <div className="message-scroll">
      {!conversationId && <div className="welcome"><div className="welcome-symbol"><Bot size={34}/></div><span className="kicker">YOUR BILINGUAL THOUGHT PARTNER</span><h1>Muraho, {user.full_name?.split(" ")[0] || user.username}.</h1><p>What would you like to understand, create, or translate today?</p><div className="starter-grid">{starters.map((item, index) => <button key={item} onClick={() => setDraft(item)}><span>0{index + 1}</span>{item}<ArrowUp size={15}/></button>)}</div></div>}
      {messages.map((message) => <MessageBubble key={message.id} message={message}/>)}
      {pendingUser && <article className="message user pending-message"><div className="message-body"><span>YOU</span><p>{pendingUser}</p></div></article>}
      {send.isPending && <article className="message assistant streaming-message"><div className="message-icon"><Sparkles size={16}/></div><div className="message-body"><span>EVA</span>{streamedAnswer ? <MarkdownContent content={streamedAnswer}/> : <div className="thinking"><i/><i/><i/></div>}</div></article>}
      {send.error && <p className="chat-error" role="alert">{send.error.message}</p>}<div ref={end}/>
    </div>
    <form className="composer-wrap" onSubmit={submit}>
      {uploadStatus && <div className="upload-status">{(uploadDocument.isPending || transcribeAudio.isPending) && <LoaderCircle className="spin"/>}<span>{uploadStatus}</span><button type="button" onClick={() => setUploadStatus("")} aria-label="Dismiss upload status">×</button></div>}
      <div className="composer"><textarea value={draft} onChange={(event) => setDraft(event.target.value)} onKeyDown={(event) => { if (event.key === "Enter" && !event.shiftKey) { event.preventDefault(); submit(); } }} placeholder="Message EVA in English or Kinyarwanda…" rows={1} aria-label="Message EVA"/><div className="composer-actions"><div className="media-actions">
        <div className="audio-language" role="group" aria-label="Recording language"><button type="button" className={audioLanguage === "rw" ? "active" : ""} onClick={() => setAudioLanguage("rw")} title="Transcribe in Kinyarwanda">RW</button><button type="button" className={audioLanguage === "en" ? "active" : ""} onClick={() => setAudioLanguage("en")} title="Transcribe in English">EN</button></div>
        <div className="attach-control"><Button type="button" variant="ghost" size="icon" aria-label="Upload a document or audio file" title="Upload file" onClick={() => setAttachmentMenu((open) => !open)}><FilePlus2 size={19}/></Button>{attachmentMenu && <div className="attachment-menu"><button type="button" onClick={() => { setAttachmentMenu(false); documentInput.current?.click(); }}><FileText/> Upload document</button><button type="button" onClick={() => { setAttachmentMenu(false); audioInput.current?.click(); }}><FileAudio/> Upload audio</button></div>}</div>
        <Button type="button" variant="ghost" size="icon" className={recording ? "recording-button" : ""} aria-label={recording ? "Stop recording" : "Record audio"} title={recording ? "Stop recording" : "Record audio"} onClick={toggleRecording}>{recording ? <Square size={16}/> : <Mic size={19}/>}</Button>
      </div><Button size="icon" aria-label="Send message" disabled={!draft.trim() || send.isPending}><ArrowUp size={19}/></Button></div></div>
      <input ref={documentInput} className="hidden-file-input" type="file" accept=".pdf,.docx,.txt,.png,.jpg,.jpeg,.tif,.tiff,text/plain,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document,image/png,image/jpeg,image/tiff" onChange={(event) => { const file = event.target.files?.[0]; if (file) uploadDocument.mutate(file); event.target.value = ""; }}/>
      <input ref={audioInput} className="hidden-file-input" type="file" accept="audio/*,.mp3,.wav,.ogg,.m4a,.webm" onChange={(event) => { const file = event.target.files?.[0]; if (file) transcribeAudio.mutate(file); event.target.value = ""; }}/>
      <small>EVA can make mistakes. Verify important information.</small>
    </form>
  </section>;
}

function MessageBubble({ message }: { message: Message }) {
  const assistant = message.role === "assistant";
  const [speaking, setSpeaking] = useState(false);
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
  return <article className={`message ${assistant ? "assistant" : "user"}`}>
    {assistant && <div className="message-icon"><Sparkles size={16}/></div>}
    <div className="message-body">
      <span>{assistant ? "EVA" : "YOU"}</span>
      {assistant ? <MarkdownContent content={message.content}/> : <p>{message.content}</p>}
      {assistant && <button type="button" className={`listen ${speaking ? "speaking" : ""}`} onClick={listen} aria-label={speaking ? "Stop reading response" : "Read response aloud"}><Volume2 size={14}/> {speaking ? "Stop" : "Listen"}</button>}
    </div>
  </article>;
}

function MarkdownContent({ content }: { content: string }) {
  return <div className="message-markdown"><ReactMarkdown remarkPlugins={[remarkGfm]}>{content}</ReactMarkdown></div>;
}
