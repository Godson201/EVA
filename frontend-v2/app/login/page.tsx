"use client";

import { FormEvent, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { ArrowRight, Languages, Sparkles } from "lucide-react";
import { api } from "@/lib/api";
import { useAuthStore } from "@/stores/auth-store";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

type Mode = "login" | "register" | "forgot" | "reset";

export default function LoginPage() {
  const router = useRouter();
  const accessToken = useAuthStore((state) => state.accessToken);
  const setSession = useAuthStore((state) => state.setSession);
  const [mode, setMode] = useState<Mode>("login");
  const [identifier, setIdentifier] = useState("");
  const [username, setUsername] = useState("");
  const [email, setEmail] = useState("");
  const [fullName, setFullName] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [resetToken, setResetToken] = useState("");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => { if (accessToken) router.replace("/chat"); }, [accessToken, router]);

  function switchMode(next: Mode) {
    setMode(next); setError(""); setNotice(""); setPassword(""); setConfirmPassword("");
  }

  async function submit(event: FormEvent) {
    event.preventDefault(); setBusy(true); setError(""); setNotice("");
    try {
      if (mode === "login") {
        const session = await api.login(identifier.trim(), password);
        setSession(session.access_token, session.user); router.replace("/chat");
      } else if (mode === "register") {
        if (password !== confirmPassword) throw new Error("Passwords do not match");
        const session = await api.register({ username: username.trim(), email: email.trim(), password, full_name: fullName.trim() || undefined });
        setSession(session.access_token, session.user); router.replace("/chat");
      } else if (mode === "forgot") {
        const result = await api.forgotPassword(identifier.trim());
        setNotice(result.message);
        if (result.reset_token) { setResetToken(result.reset_token); setMode("reset"); }
      } else {
        if (password !== confirmPassword) throw new Error("Passwords do not match");
        const result = await api.resetPassword(resetToken, password);
        switchMode("login"); setNotice(result.message);
      }
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Request failed"); }
    finally { setBusy(false); }
  }

  const titles = {
    login: ["WELCOME BACK", "Continue with EVA", "Sign in to your EVA workspace."],
    register: ["CREATE ACCOUNT", "Join EVA", "Create your account and start working."],
    forgot: ["ACCOUNT RECOVERY", "Forgot password?", "Enter your username or email."],
    reset: ["SECURE RECOVERY", "Choose a new password", "Use at least eight characters."],
  } as const;

  return <main className="login-page">
    <section className="login-story">
      <div className="brand"><span className="eva-mark">E</span><span>EVA</span></div>
      <div className="story-copy"><div className="eyebrow"><Sparkles size={15}/> Intelligence that understands context</div><h1>Think, speak, and learn<br/><em>without translation gaps.</em></h1><p>Your English–Kinyarwanda workspace for conversation, documents, speech, and study.</p></div>
      <div className="language-orbit"><span>Hello</span><Languages/><span>Muraho</span></div>
    </section>
    <section className="login-panel">
      <form onSubmit={submit} className="login-card">
        <div><span className="kicker">{titles[mode][0]}</span><h2>{titles[mode][1]}</h2><p>{titles[mode][2]}</p></div>
        {mode === "register" && <><label>Full name<Input autoComplete="name" value={fullName} onChange={(e) => setFullName(e.target.value)}/></label><label>Username<Input autoComplete="username" minLength={3} value={username} onChange={(e) => setUsername(e.target.value)} required/></label><label>Email<Input type="email" autoComplete="email" value={email} onChange={(e) => setEmail(e.target.value)} required/></label></>}
        {(mode === "login" || mode === "forgot") && <label>Username or email<Input autoComplete="username" value={identifier} onChange={(e) => setIdentifier(e.target.value)} required/></label>}
        {(mode === "login" || mode === "register" || mode === "reset") && <label>{mode === "reset" ? "New password" : "Password"}<Input type="password" minLength={mode === "login" ? 1 : 8} autoComplete={mode === "login" ? "current-password" : "new-password"} value={password} onChange={(e) => setPassword(e.target.value)} required/></label>}
        {(mode === "register" || mode === "reset") && <label>Confirm password<Input type="password" minLength={8} autoComplete="new-password" value={confirmPassword} onChange={(e) => setConfirmPassword(e.target.value)} required/></label>}
        {notice && <p className="form-notice" role="status">{notice}</p>}
        {error && <p className="form-error" role="alert">{error}</p>}
        <Button disabled={busy} className="w-full">{busy ? "Please wait…" : mode === "login" ? "Sign in" : mode === "register" ? "Create account" : mode === "forgot" ? "Continue recovery" : "Reset password"}<ArrowRight size={17}/></Button>
        <div className="auth-links">{mode === "login" ? <><button type="button" onClick={() => switchMode("forgot")}>Forgot password?</button><span>New to EVA? <button type="button" onClick={() => switchMode("register")}>Register</button></span></> : <button type="button" onClick={() => switchMode("login")}>Back to sign in</button>}</div>
      </form>
    </section>
  </main>;
}
