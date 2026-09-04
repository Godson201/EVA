"use client";

import { FormEvent, useEffect, useMemo, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { ArrowUp, Bot, FilePlus2, Mic, Plus, Sparkles, Volume2 } from "lucide-react";
import { api } from "@/lib/api";
import { useAuthStore } from "@/stores/auth-store";
import type { Message } from "@/types/api";
import { Button } from "@/components/ui/button";

const starters = ["Explain a difficult idea simply", "Sobanura inyandiko yanjye", "Translate a professional reply"];

export function ChatWorkspace({ initialId = null }: { initialId?: string | null }) {
  const token = useAuthStore((state) => state.accessToken)!; const user = useAuthStore((state) => state.user)!;
  const router = useRouter();
  const queryClient = useQueryClient(); const [conversationId, setConversationId] = useState<string | null>(initialId); const [draft, setDraft] = useState(""); const end = useRef<HTMLDivElement>(null);
  const detail = useQuery({ queryKey: ["conversation", conversationId], queryFn: () => api.conversation(conversationId!, token), enabled: !!conversationId });
  const send = useMutation({ mutationFn: async (content: string) => { let id = conversationId; if (!id) { const created = await api.createConversation(token, content.slice(0, 52)); id = created.id; setConversationId(id); } return { id, result: await api.sendMessage(id, content, token) }; }, onSuccess: ({ id }) => { queryClient.invalidateQueries({ queryKey: ["conversation", id] }); queryClient.invalidateQueries({ queryKey: ["conversations"] }); } });
  const messages = useMemo(() => detail.data?.messages || [], [detail.data?.messages]);
  useEffect(() => { end.current?.scrollIntoView({ behavior: "smooth" }); }, [messages, send.isPending]);
  function submit(event?: FormEvent) { event?.preventDefault(); const content = draft.trim(); if (!content || send.isPending) return; setDraft(""); send.mutate(content); }
  function newChat() { setConversationId(null); setDraft(""); router.push("/chat"); }
  return <section className="chat-shell">
    <header className="topbar"><div><span className="mobile-brand">EVA</span><p>{conversationId ? detail.data?.title || "Conversation" : "New conversation"}</p></div><Button variant="outline" size="sm" onClick={newChat}><Plus size={15}/> New</Button></header>
    <div className="message-scroll">
      {!conversationId && <div className="welcome"><div className="welcome-symbol"><Bot size={34}/></div><span className="kicker">YOUR BILINGUAL THOUGHT PARTNER</span><h1>Muraho, {user.full_name?.split(" ")[0] || user.username}.</h1><p>What would you like to understand, create, or translate today?</p><div className="starter-grid">{starters.map((item, index) => <button key={item} onClick={() => setDraft(item)}><span>0{index + 1}</span>{item}<ArrowUp size={15}/></button>)}</div></div>}
      {messages.map((message) => <MessageBubble key={message.id} message={message}/>)}
      {send.isPending && <div className="message assistant"><div className="message-icon"><Sparkles size={16}/></div><div className="thinking"><i/><i/><i/></div></div>}
      {send.error && <p className="chat-error" role="alert">{send.error.message}</p>}<div ref={end}/>
    </div>
    <form className="composer-wrap" onSubmit={submit}><div className="composer"><textarea value={draft} onChange={(event) => setDraft(event.target.value)} onKeyDown={(event) => { if (event.key === "Enter" && !event.shiftKey) { event.preventDefault(); submit(); } }} placeholder="Message EVA in English or Kinyarwanda…" rows={1} aria-label="Message EVA"/><div className="composer-actions"><div><Button type="button" variant="ghost" size="icon" aria-label="Attach a file" title="Attachments arrive in a later route migration"><FilePlus2 size={19}/></Button><Button type="button" variant="ghost" size="icon" aria-label="Record audio" title="Speech controls arrive in the Voice migration"><Mic size={19}/></Button></div><Button size="icon" aria-label="Send message" disabled={!draft.trim() || send.isPending}><ArrowUp size={19}/></Button></div></div><small>EVA can make mistakes. Verify important information.</small></form>
  </section>;
}

function MessageBubble({ message }: { message: Message }) {
  const assistant = message.role === "assistant";
  return <article className={`message ${assistant ? "assistant" : "user"}`}>{assistant && <div className="message-icon"><Sparkles size={16}/></div>}<div className="message-body"><span>{assistant ? "EVA" : "YOU"}</span><p>{message.content}</p>{assistant && <button className="listen" aria-label="Read response aloud"><Volume2 size={14}/> Listen</button>}</div></article>;
}
