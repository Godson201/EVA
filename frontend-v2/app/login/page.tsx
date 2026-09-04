"use client";

import { FormEvent, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { ArrowRight, Languages, Sparkles } from "lucide-react";
import { api } from "@/lib/api";
import { useAuthStore } from "@/stores/auth-store";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

export default function LoginPage() {
  const router = useRouter();
  const accessToken = useAuthStore((state) => state.accessToken);
  const setSession = useAuthStore((state) => state.setSession);
  const [identifier, setIdentifier] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  useEffect(() => { if (accessToken) router.replace("/chat"); }, [accessToken, router]);
  async function submit(event: FormEvent) {
    event.preventDefault(); setBusy(true); setError("");
    try { const session = await api.login(identifier.trim(), password); setSession(session.access_token, session.user); router.replace("/chat"); }
    catch (reason) { setError(reason instanceof Error ? reason.message : "Sign in failed"); }
    finally { setBusy(false); }
  }
  return <main className="login-page">
    <section className="login-story">
      <div className="brand"><span className="eva-mark">E</span><span>EVA</span></div>
      <div className="story-copy"><div className="eyebrow"><Sparkles size={15}/> Intelligence that understands context</div><h1>Think, speak, and learn<br/><em>without translation gaps.</em></h1><p>Your English–Kinyarwanda workspace for conversation, documents, speech, and study.</p></div>
      <div className="language-orbit"><span>Hello</span><Languages/><span>Muraho</span></div>
    </section>
    <section className="login-panel"><form onSubmit={submit} className="login-card"><div><span className="kicker">WELCOME BACK</span><h2>Continue with EVA</h2><p>Use your migrated EVA account.</p></div><label>Username or email<Input autoComplete="username" value={identifier} onChange={(e) => setIdentifier(e.target.value)} required/></label><label>Password<Input type="password" autoComplete="current-password" value={password} onChange={(e) => setPassword(e.target.value)} required/></label>{error && <p className="form-error" role="alert">{error}</p>}<Button disabled={busy} className="w-full">{busy ? "Signing in…" : "Sign in"}<ArrowRight size={17}/></Button><p className="legacy-note">Account registration remains available in the <a href={process.env.NEXT_PUBLIC_LEGACY_APP_URL || "http://localhost:3000"}>classic EVA app</a> during migration.</p></form></section>
  </main>;
}
