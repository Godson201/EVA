"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { BookOpen, Clock3, FileText, Languages, LogOut, Menu, MessageSquarePlus, Mic2, PhoneCall, Settings, X } from "lucide-react";
import { api } from "@/lib/api";
import { cn } from "@/lib/utils";
import { useAuthStore } from "@/stores/auth-store";
import { Button } from "@/components/ui/button";

const navigation = [
  ["/chat", "New chat", MessageSquarePlus], ["/history", "Chat history", Clock3], ["/translate", "Translate", Languages],
  ["/study", "Study", BookOpen], ["/documents", "Documents", FileText], ["/voice", "Voice", Mic2],
  ["/calls", "Call assistant", PhoneCall], ["/settings", "Settings", Settings],
] as const;

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname(); const router = useRouter();
  const { user, accessToken, clear } = useAuthStore(); const [open, setOpen] = useState(false);
  useEffect(() => { if (!accessToken) router.replace("/login"); }, [accessToken, router]);
  if (!accessToken || !user) return null;
  async function logout() { await api.logout().catch(() => undefined); clear(); router.replace("/login"); }
  return <div className="app-frame">
    <button className="mobile-menu" onClick={() => setOpen(true)} aria-label="Open navigation"><Menu/></button>
    {open && <button className="scrim" onClick={() => setOpen(false)} aria-label="Close navigation"/>}
    <aside className={cn("sidebar", open && "sidebar-open")}>
      <div className="sidebar-head"><Link href="/chat" className="brand"><span className="eva-mark">E</span><span>EVA</span></Link><Button className="mobile-close" variant="ghost" size="icon" onClick={() => setOpen(false)} aria-label="Close"><X/></Button></div>
      <div className="status-pill"><span/><p><strong>EVA is ready</strong><small>English · Kinyarwanda</small></p></div>
      <nav aria-label="Primary navigation">{navigation.map(([href, label, Icon]) => <Link key={href} href={href} onClick={() => setOpen(false)} className={cn("nav-link", pathname === href && "active")}><Icon size={18}/><span>{label}</span></Link>)}</nav>
      <div className="sidebar-foot"><div className="avatar">{(user.full_name || user.username).slice(0, 2).toUpperCase()}</div><div className="user-meta"><strong>{user.full_name || user.username}</strong><small>{user.profile_type.replaceAll("_", " ")}</small></div><Button onClick={logout} variant="ghost" size="icon" aria-label="Sign out"><LogOut size={17}/></Button></div>
    </aside>
    <main className="main-stage">{children}</main>
  </div>;
}
