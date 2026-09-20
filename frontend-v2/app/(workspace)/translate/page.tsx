"use client";

import { FormEvent, useEffect, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeftRight, Check, Clock3, Copy, Languages, LoaderCircle, Mic, Sparkles, Square } from "lucide-react";
import { api } from "@/lib/api";
import { useAuthStore } from "@/stores/auth-store";
import type { Translation } from "@/types/api";
import { Button } from "@/components/ui/button";

type LanguageCode = "en" | "rw" | "fr" | "sw" | "es" | "de" | "pt" | "ar" | "zh" | "hi";
type SourceLanguage = "auto" | LanguageCode;
type SpeechResult = { isFinal: boolean; 0: { transcript: string } };
type SpeechEvent = { resultIndex: number; results: ArrayLike<SpeechResult> };
type SpeechRecognitionLike = { lang: string; continuous: boolean; interimResults: boolean; onresult: ((event: SpeechEvent) => void) | null; onerror: (() => void) | null; onend: (() => void) | null; start: () => void; stop: () => void };

const modes = [["natural", "Natural"], ["professional", "Professional"], ["academic", "Academic"], ["simple", "Simple"], ["direct", "Direct"]];
const languages: Array<{ code: LanguageCode; name: string; speech: string }> = [
  { code: "rw", name: "Kinyarwanda", speech: "rw-RW" }, { code: "en", name: "English", speech: "en-US" },
  { code: "fr", name: "French", speech: "fr-FR" }, { code: "sw", name: "Swahili", speech: "sw-KE" },
  { code: "es", name: "Spanish", speech: "es-ES" }, { code: "de", name: "German", speech: "de-DE" },
  { code: "pt", name: "Portuguese", speech: "pt-BR" }, { code: "ar", name: "Arabic", speech: "ar-SA" },
  { code: "zh", name: "Chinese (Simplified)", speech: "zh-CN" }, { code: "hi", name: "Hindi", speech: "hi-IN" },
];
const languageName = (code: string) => languages.find(language => language.code === code)?.name || code.toUpperCase();
const delay = (ms: number) => new Promise(resolve => setTimeout(resolve, ms));

export default function TranslatePage() {
  const token = useAuthStore(state => state.accessToken)!; const queryClient = useQueryClient(); const typingRun = useRef(0);
  const recognition = useRef<SpeechRecognitionLike | null>(null); const finalSpeech = useRef(""); const visibleSpeech = useRef(""); const translateOnEnd = useRef(false);
  const [source, setSource] = useState<SourceLanguage>("auto"); const [target, setTarget] = useState<LanguageCode>("rw");
  const [mode, setMode] = useState("natural"); const [input, setInput] = useState(""); const [output, setOutput] = useState("");
  const [detected, setDetected] = useState<string | null>(null); const [typing, setTyping] = useState(false); const [copied, setCopied] = useState(false);
  const [recording, setRecording] = useState(false); const [voiceStatus, setVoiceStatus] = useState("");
  const history = useQuery({ queryKey: ["translations"], queryFn: () => api.translations(token) });
  const translate = useMutation({
    mutationFn: (spokenText?: string) => api.translate((spokenText || input).trim(), source === "auto" ? null : source, target, mode, token),
    onSuccess: result => { setDetected(result.translation.source_language); typeOutput(result.translation.translated_text); setVoiceStatus(""); queryClient.invalidateQueries({ queryKey: ["translations"] }); },
  });
  useEffect(() => () => { typingRun.current += 1; translateOnEnd.current = false; visibleSpeech.current = ""; recognition.current?.stop(); }, []);
  async function typeOutput(content: string) { const run = ++typingRun.current; setOutput(""); setTyping(true); const step = content.length > 2000 ? 12 : content.length > 800 ? 7 : 3; for (let i = step; i < content.length; i += step) { if (run !== typingRun.current) return; setOutput(content.slice(0, i)); await delay(10); } if (run === typingRun.current) { setOutput(content); setTyping(false); } }
  function submit(event: FormEvent) { event.preventDefault(); if (input.trim() && !typing && !translate.isPending) translate.mutate(undefined); }
  function swap() { typingRun.current += 1; setTyping(false); const translated = output; if (source === "auto") { setSource(target); setTarget((detected && detected !== target ? detected : "en") as LanguageCode); } else { const previous = source; setSource(target); setTarget(previous); } setInput(translated || input); setOutput(input); }
  async function copy() { if (!output) return; await navigator.clipboard.writeText(output); setCopied(true); setTimeout(() => setCopied(false), 1600); }
  function restore(item: Translation) { typingRun.current += 1; setTyping(false); setSource(item.source_language as SourceLanguage); setTarget(item.target_language as LanguageCode); setMode(item.mode); setInput(item.source_text); setOutput(item.translated_text); setDetected(item.source_language); }
  function toggleVoice() {
    if (recording && recognition.current) { translateOnEnd.current = true; recognition.current.stop(); setRecording(false); setVoiceStatus("Preparing your translation..."); return; }
    const browser = window as typeof window & { SpeechRecognition?: new () => SpeechRecognitionLike; webkitSpeechRecognition?: new () => SpeechRecognitionLike };
    const Recognition = browser.SpeechRecognition || browser.webkitSpeechRecognition;
    if (!Recognition) { setVoiceStatus("Live speech requires Chrome or Edge. You can still type or paste text."); return; }
    finalSpeech.current = ""; visibleSpeech.current = ""; translateOnEnd.current = false; setInput(""); setOutput(""); setDetected(null);
    const speech = new Recognition(); recognition.current = speech; speech.continuous = true; speech.interimResults = true;
    const selected = source === "auto" ? null : languages.find(language => language.code === source);
    speech.lang = selected?.speech || navigator.language || "en-US";
    speech.onresult = event => { let complete = finalSpeech.current; let interim = ""; for (let index = event.resultIndex; index < event.results.length; index++) { const result = event.results[index]; if (result.isFinal) complete += `${result[0].transcript.trim()} `; else interim += result[0].transcript; } finalSpeech.current = complete; const text = `${complete}${interim}`.trim(); visibleSpeech.current = text; setInput(text); };
    speech.onerror = () => { setRecording(false); setVoiceStatus("EVA could not hear clearly. Check microphone access and try again."); };
    speech.onend = () => { const text = visibleSpeech.current.trim(); const shouldTranslate = translateOnEnd.current || Boolean(text); translateOnEnd.current = false; recognition.current = null; setRecording(false); if (shouldTranslate && text) { setVoiceStatus("Detecting the language and translating..."); translate.mutate(text); } };
    try { speech.start(); setRecording(true); setVoiceStatus("Listening live... Speak naturally, then select Stop."); } catch { setVoiceStatus("Microphone access was denied. Allow access and try again."); }
  }
  return <section className="translate-page"><header className="translate-head"><div><span className="kicker">INTELLIGENT MULTILINGUAL TRANSLATION</span><h1>Meaning,<br/><em>not just words.</em></h1><p>Speak, type, or paste text. EVA detects the language and translates its meaning with the tone you choose.</p></div><div className={`translate-mark ${recording ? "listening" : ""}`}><Languages/><span>{recording ? "LISTENING" : "10 LANGUAGES"}</span></div></header>
    <div className="translate-workspace"><main className="translator-card"><div className="translation-toolbar"><label>From<select value={source} onChange={event => setSource(event.target.value as SourceLanguage)} disabled={recording}><option value="auto">Detect automatically</option>{languages.map(language => <option key={language.code} value={language.code}>{language.name}</option>)}</select></label><Button type="button" variant="ghost" size="icon" onClick={swap} aria-label="Swap languages" disabled={recording}><ArrowLeftRight/></Button><label>To<select value={target} onChange={event => setTarget(event.target.value as LanguageCode)} disabled={recording}>{languages.map(language => <option key={language.code} value={language.code}>{language.name}</option>)}</select></label></div><div className="tone-picker"><span>Tone</span>{modes.map(([value, label]) => <button key={value} type="button" className={mode === value ? "active" : ""} onClick={() => setMode(value)} disabled={recording}>{label}</button>)}</div><form onSubmit={submit}><div className="translation-panels"><section className={recording ? "speech-source-panel" : ""}><header><strong>{source === "auto" ? (detected ? `${languageName(detected)} detected` : "Automatic detection") : languageName(source)}</strong><div className="source-voice-tools"><small>{input.length.toLocaleString()} characters</small><button type="button" className={recording ? "voice-stop" : ""} onClick={toggleVoice} aria-label={recording ? "Stop speaking and translate" : "Translate with live speech"}>{recording ? <Square/> : <Mic/>}<span>{recording ? "Stop & translate" : "Speak"}</span></button></div></header><textarea value={input} onChange={event => setInput(event.target.value)} placeholder={recording ? "Your speech will appear here live..." : "Type, paste, or select Speak..."} maxLength={100000} readOnly={recording}/>{voiceStatus && <div className={`voice-translation-status ${recording ? "active" : ""}`}>{recording && <i/>}<span>{voiceStatus}</span></div>}</section><section className="translated-panel"><header><strong>{languageName(target)}</strong><div><button type="button" onClick={copy} aria-label="Copy translation">{copied ? <Check/> : <Copy/>}</button></div></header><div className={`translation-output ${typing ? "typing" : ""}`}>{translate.isPending ? <span className="translating"><LoaderCircle className="spin"/> EVA is detecting language and translating meaning...</span> : output || <span className="translation-placeholder">Your translation will appear here automatically.</span>}</div></section></div><div className="translate-submit"><span>{source === "auto" ? "Automatic language detection" : `${languageName(source)} to ${languageName(target)}`}</span><Button disabled={!input.trim() || translate.isPending || typing || recording}>{translate.isPending ? <LoaderCircle className="spin"/> : <Sparkles/>} Translate</Button></div>{translate.error && <p className="form-error">{translate.error.message}</p>}</form></main>
      <aside className="translation-history"><div><Clock3/><span><strong>Recent translations</strong><small>{history.data?.total || 0} saved privately</small></span></div>{history.isLoading && <p>Loading...</p>}{!history.isLoading && !history.data?.items.length && <p className="translation-empty">Your recent translations will appear here.</p>}{history.data?.items.map(item => <button key={item.id} onClick={() => restore(item)}><span>{languageName(item.source_language)} to {languageName(item.target_language)} · {item.mode}</span><strong>{item.source_text}</strong><small>{new Date(item.created_at).toLocaleString()}</small></button>)}</aside></div>
  </section>;
}
