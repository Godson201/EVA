"use client";

import { FormEvent, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { ArrowLeft, ArrowRight, Check, Eye, EyeOff, Languages, ShieldCheck, Sparkles } from "lucide-react";
import { api } from "@/lib/api";
import { useAuthStore } from "@/stores/auth-store";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

type Mode = "login" | "register" | "forgot" | "reset";
const copy = {
  login: ["WELCOME BACK", "Continue with EVA", "Sign in securely to your workspace."],
  register: ["CREATE YOUR ACCOUNT", "Start with EVA", "One account for conversation, speech, documents, and study."],
  forgot: ["ACCOUNT RECOVERY", "Reset your password", "Enter your username or email to continue."],
  reset: ["SECURE RECOVERY", "Create a new password", "Choose a strong password you have not used before."],
} as const;

function Required() { return <span className="required-mark" aria-hidden="true">*</span>; }

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
  const [showPassword, setShowPassword] = useState(false);
  const [showConfirm, setShowConfirm] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => { if (accessToken) router.replace("/chat"); }, [accessToken, router]);

  function switchMode(next: Mode) {
    setMode(next); setError(""); setNotice(""); setPassword(""); setConfirmPassword("");
    setShowPassword(false); setShowConfirm(false);
  }

  async function submit(event: FormEvent) {
    event.preventDefault(); setBusy(true); setError(""); setNotice("");
    try {
      if (mode === "login") {
        const session = await api.login(identifier.trim(), password);
        setSession(session.access_token, session.user); router.replace("/chat");
      } else if (mode === "register") {
        if (password !== confirmPassword) throw new Error("Passwords do not match.");
        const session = await api.register({ username: username.trim(), email: email.trim(), password, full_name: fullName.trim() });
        setSession(session.access_token, session.user); router.replace("/chat");
      } else if (mode === "forgot") {
        const result = await api.forgotPassword(identifier.trim());
        setNotice(result.message);
        if (result.reset_token) { setResetToken(result.reset_token); setMode("reset"); }
      } else {
        if (password !== confirmPassword) throw new Error("Passwords do not match.");
        const result = await api.resetPassword(resetToken, password);
        switchMode("login"); setNotice(result.message);
      }
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Request failed"); }
    finally { setBusy(false); }
  }

  const passwordField = (confirm = false) => {
    const visible = confirm ? showConfirm : showPassword;
    return <div className="password-field">
      <Input type={visible ? "text" : "password"} minLength={mode === "login" ? 1 : 8}
        autoComplete={mode === "login" ? "current-password" : "new-password"}
        value={confirm ? confirmPassword : password}
        onChange={(event) => confirm ? setConfirmPassword(event.target.value) : setPassword(event.target.value)} required/>
      <button type="button" className="password-toggle" onClick={() => confirm ? setShowConfirm(!visible) : setShowPassword(!visible)} aria-label={visible ? "Hide password" : "Show password"}>
        {visible ? <EyeOff/> : <Eye/>}
      </button>
    </div>;
  };

  return <main className="login-page">
    <section className="login-story">
      <div className="brand"><span className="eva-mark">E</span><span>EVA</span></div>
      <div className="story-copy"><div className="eyebrow"><Sparkles size={15}/> Intelligence that understands context</div><h1>Think, speak, and learn<br/><em>without translation gaps.</em></h1><p>Your English–Kinyarwanda workspace for conversation, documents, speech, and study.</p></div>
      <div className="language-orbit"><span>Hello</span><Languages/><span>Muraho</span></div>
    </section>

    <section className="login-panel"><form onSubmit={submit} className="login-card">
      {(mode === "login" || mode === "register") && <div className="auth-tabs" role="tablist" aria-label="Account access">
        <button type="button" role="tab" aria-selected={mode === "login"} onClick={() => switchMode("login")}>Sign in</button>
        <button type="button" role="tab" aria-selected={mode === "register"} onClick={() => switchMode("register")}>Create account</button>
      </div>}
      <header className="auth-heading"><span className="kicker">{copy[mode][0]}</span><h2>{copy[mode][1]}</h2><p>{copy[mode][2]}</p></header>
      {mode === "register" && <div className="auth-fields">
        <label>Full name <Required/><Input autoComplete="name" minLength={2} value={fullName} onChange={(e) => setFullName(e.target.value)} required/></label>
        <label>Username <Required/><Input autoComplete="username" minLength={3} pattern="[A-Za-z0-9_.-]+" title="Use letters, numbers, dots, hyphens, or underscores" value={username} onChange={(e) => setUsername(e.target.value)} required/></label>
        <label>Email address <Required/><Input type="email" autoComplete="email" value={email} onChange={(e) => setEmail(e.target.value)} required/></label>
        <label>Password <Required/>{passwordField()}</label>
        <div className="password-hint"><ShieldCheck/><span>Use 8 or more characters.</span></div>
        <label>Confirm password <Required/>{passwordField(true)}</label>
      </div>}
      {mode === "login" && <div className="auth-fields">
        <label>Username or email <Required/><Input autoComplete="username" value={identifier} onChange={(e) => setIdentifier(e.target.value)} required/></label>
        <label><span className="label-row"><span>Password <Required/></span><button type="button" className="forgot-link" onClick={() => switchMode("forgot")}>Forgot password?</button></span>{passwordField()}</label>
      </div>}
      {mode === "forgot" && <div className="auth-fields"><label>Username or email <Required/><Input autoComplete="username" value={identifier} onChange={(e) => setIdentifier(e.target.value)} required/></label></div>}
      {mode === "reset" && <div className="auth-fields"><label>New password <Required/>{passwordField()}</label><div className="password-hint"><ShieldCheck/><span>Use 8 or more characters.</span></div><label>Confirm new password <Required/>{passwordField(true)}</label></div>}
      {notice && <p className="form-notice" role="status"><Check/>{notice}</p>}
      {error && <p className="form-error" role="alert">{error}</p>}
      <Button disabled={busy} className="w-full auth-submit">{busy ? "Please wait…" : mode === "login" ? "Sign in securely" : mode === "register" ? "Create my account" : mode === "forgot" ? "Continue recovery" : "Set new password"}<ArrowRight size={17}/></Button>
      {mode !== "login" && mode !== "register" && <button type="button" className="back-link" onClick={() => switchMode("login")}><ArrowLeft/> Back to sign in</button>}
      <p className="required-note"><Required/> Required fields</p>
    </form></section>
  </main>;
}
