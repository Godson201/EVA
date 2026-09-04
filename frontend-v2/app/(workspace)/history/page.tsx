"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { ArrowUpRight, Clock3, MessageCircle } from "lucide-react";
import { api } from "@/lib/api";
import { useAuthStore } from "@/stores/auth-store";

export default function HistoryPage() {
  const token = useAuthStore((state) => state.accessToken)!;
  const { data, isLoading } = useQuery({ queryKey: ["conversations"], queryFn: () => api.conversations(token) });
  return <section className="feature-page"><header className="feature-head"><span className="kicker">CONVERSATIONS</span><h1>Your thinking, continued.</h1><p>Return to an earlier exchange without losing the thread.</p></header><div className="history-list">{isLoading && <p>Loading conversations…</p>}{data?.items.map((item) => <Link href={`/chat/${item.id}`} key={item.id} className="history-row"><div className="feature-icon"><MessageCircle/></div><div><strong>{item.title || "Untitled conversation"}</strong><small>{new Date(item.updated_at).toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" })}</small></div><ArrowUpRight/></Link>)}{!isLoading && !data?.items.length && <div className="empty-state"><Clock3/><h2>No conversations yet</h2><p>Your EVA conversations will appear here.</p></div>}</div></section>;
}
