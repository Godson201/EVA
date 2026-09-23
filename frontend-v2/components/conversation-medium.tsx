"use client";

import { FormEvent, useEffect, useRef, useState } from "react";
import {
  Check,
  Copy,
  Lightbulb,
  Mic,
  Send,
  Square,
  Volume2,
  X,
} from "lucide-react";
import { API_URL } from "@/lib/api";
import type { ConversationMessage } from "@/types/api";
import { Button } from "@/components/ui/button";

type SpeechResult = { isFinal: boolean; 0: { transcript: string } };
type SpeechEvent = { resultIndex: number; results: ArrayLike<SpeechResult> };
type Recognition = {
  lang: string;
  continuous: boolean;
  interimResults: boolean;
  onresult: ((event: SpeechEvent) => void) | null;
  onerror: (() => void) | null;
  onend: (() => void) | null;
  start: () => void;
  stop: () => void;
};

type RoomEvent =
  | ConversationMessage
  | {
      type: "room_ready";
      messages?: ConversationMessage[];
      host_language?: string;
      guest_language?: string | null;
    }
  | {
      type: "presence";
      host_connected: boolean;
      guest_connected: boolean;
      host_language?: string;
      guest_language?: string | null;
    }
  | { type: "error"; message: string };

const names: Record<string, string> = { en: "English", rw: "Kinyarwanda" };

export function ConversationMedium({
  ticket,
  role,
  myLanguage,
  otherLanguage,
  inviteUrl,
}: {
  ticket: string;
  role: "host" | "guest";
  myLanguage: string;
  otherLanguage: string | null;
  inviteUrl?: string;
}) {
  const socket = useRef<WebSocket | null>(null);
  const recognition = useRef<Recognition | null>(null);
  const spoken = useRef("");
  const [status, setStatus] = useState<"connecting" | "live" | "offline">(
    "connecting",
  );
  const [otherOnline, setOtherOnline] = useState(false);
  const [partnerLanguage, setPartnerLanguage] = useState<string | null>(
    otherLanguage,
  );
  const [messages, setMessages] = useState<ConversationMessage[]>([]);
  const [draft, setDraft] = useState("");
  const [liveText, setLiveText] = useState("");
  const [listening, setListening] = useState(false);
  const [error, setError] = useState("");
  const [copied, setCopied] = useState(false);
  const [showTip, setShowTip] = useState(true);
  const stream = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    setShowTip(localStorage.getItem("eva-conversation-tip") !== "seen");
    const base = new URL(API_URL);
    const url = `${base.protocol === "https:" ? "wss" : "ws"}://${base.host}/api/v1/calls/rooms/ws?ticket=${encodeURIComponent(ticket)}`;
    const ws = new WebSocket(url);
    socket.current = ws;
    ws.onopen = () => setStatus("live");
    ws.onmessage = (message) => {
      const event = JSON.parse(message.data) as RoomEvent;
      if (event.type === "room_ready") {
        if (event.messages) setMessages(event.messages);
        setPartnerLanguage(
          role === "host"
            ? event.guest_language || null
            : event.host_language || null,
        );
      }
      if (event.type === "conversation_message")
        setMessages((current) =>
          current.some((item) => item.id === event.id)
            ? current
            : [...current, event],
        );
      if (event.type === "presence") {
        setOtherOnline(
          role === "host" ? event.guest_connected : event.host_connected,
        );
        setPartnerLanguage(
          role === "host"
            ? event.guest_language || null
            : event.host_language || null,
        );
      }
      if (event.type === "error") setError(event.message);
    };
    ws.onerror = () => setError("The live conversation could not connect.");
    ws.onclose = () => setStatus("offline");
    return () => {
      recognition.current?.stop();
      ws.close();
    };
  }, [role, ticket]);

  useEffect(() => {
    stream.current?.scrollTo({
      top: stream.current.scrollHeight,
      behavior: "smooth",
    });
  }, [messages, liveText]);

  function send(text: string) {
    const clean = text.trim();
    if (!clean || socket.current?.readyState !== WebSocket.OPEN) return;
    socket.current.send(JSON.stringify({ type: "text_turn", text: clean }));
    setDraft("");
    setLiveText("");
  }

  function submit(event: FormEvent) {
    event.preventDefault();
    send(draft);
  }

  function toggleSpeech() {
    if (listening) {
      recognition.current?.stop();
      return;
    }
    const browser = window as typeof window & {
      SpeechRecognition?: new () => Recognition;
      webkitSpeechRecognition?: new () => Recognition;
    };
    const SpeechRecognition =
      browser.SpeechRecognition || browser.webkitSpeechRecognition;
    if (!SpeechRecognition) {
      setError("Live speech requires Chrome or Microsoft Edge.");
      return;
    }
    const engine = new SpeechRecognition();
    recognition.current = engine;
    spoken.current = "";
    engine.lang = myLanguage === "rw" ? "rw-RW" : "en-US";
    engine.continuous = true;
    engine.interimResults = true;
    engine.onresult = (event) => {
      let interim = "";
      for (
        let index = event.resultIndex;
        index < event.results.length;
        index++
      ) {
        const result = event.results[index];
        if (result.isFinal) spoken.current += `${result[0].transcript} `;
        else interim += result[0].transcript;
      }
      setLiveText(`${spoken.current}${interim}`.trim());
    };
    engine.onerror = () => {
      setListening(false);
      setError(
        "EVA could not hear clearly. Check microphone permission and retry.",
      );
    };
    engine.onend = () => {
      setListening(false);
      const finalText = spoken.current.trim();
      if (finalText) send(finalText);
    };
    setError("");
    setListening(true);
    engine.start();
  }

  function read(text: string, language: string) {
    speechSynthesis.cancel();
    const utterance = new SpeechSynthesisUtterance(text);
    utterance.lang = language === "rw" ? "rw-RW" : "en-US";
    speechSynthesis.speak(utterance);
  }

  async function copyInvite() {
    if (!inviteUrl) return;
    await navigator.clipboard.writeText(inviteUrl);
    setCopied(true);
    window.setTimeout(() => setCopied(false), 1800);
  }

  function dismissTip() {
    localStorage.setItem("eva-conversation-tip", "seen");
    setShowTip(false);
  }

  return (
    <div className="medium-room">
      {showTip && (
        <aside className="medium-tip" role="status">
          <Lightbulb />
          <div>
            <strong>How this conversation works</strong>
            <p>
              Hold Speak, talk naturally, then press Stop. EVA writes your
              words, translates them, and sends them automatically.
            </p>
          </div>
          <button onClick={dismissTip} aria-label="Close guide">
            <X />
          </button>
        </aside>
      )}
      <header className="medium-room-head">
        <div>
          <span className={`medium-status ${status}`} />
          <p>
            <strong>
              {status === "live" ? "Conversation ready" : "Connecting…"}
            </strong>
            <small>
              {otherOnline
                ? "The other person is online"
                : "Waiting for the other person"}
            </small>
          </p>
        </div>
        <div className="medium-language-pair">
          <span>You · {names[myLanguage]}</span>
          <i>↔</i>
          <span>
            Partner ·{" "}
            {partnerLanguage ? names[partnerLanguage] : "Choosing language"}
          </span>
        </div>
      </header>

      {inviteUrl && (
        <div className="medium-invite">
          <div>
            <strong>Invite User B</strong>
            <small>
              Anyone with this private link can join without an account.
            </small>
          </div>
          <code>{inviteUrl}</code>
          <Button variant="outline" onClick={copyInvite}>
            {copied ? <Check /> : <Copy />}
            {copied ? "Copied" : "Copy link"}
          </Button>
        </div>
      )}

      <div className="medium-messages" ref={stream}>
        {!messages.length && !liveText && (
          <div className="medium-empty">
            <div>
              <Mic />
            </div>
            <h2>Your shared conversation starts here</h2>
            <p>
              Spoken messages appear as readable text in each person’s selected
              language.
            </p>
          </div>
        )}
        {messages.map((message) => {
          const mine = message.sender === role;
          const displayed = mine
            ? message.original_text
            : message.translated_text;
          return (
            <article
              key={message.id}
              className={`medium-message ${mine ? "mine" : "theirs"}`}
            >
              <span>
                {mine ? "You" : "Partner"} ·{" "}
                {
                  names[
                    mine ? message.source_language : message.target_language
                  ]
                }
              </span>
              <p>{displayed}</p>
              {!mine && (
                <button
                  onClick={() => read(displayed, message.target_language)}
                >
                  <Volume2 /> Read aloud
                </button>
              )}
            </article>
          );
        })}
        {liveText && (
          <article className="medium-message mine live">
            <span>Listening now…</span>
            <p>{liveText}</p>
          </article>
        )}
      </div>

      <form className="medium-composer" onSubmit={submit}>
        <button
          type="button"
          className={listening ? "recording" : ""}
          onClick={toggleSpeech}
          disabled={status !== "live"}
          aria-label={listening ? "Stop and send" : "Speak"}
        >
          {listening ? <Square /> : <Mic />}
          <span>{listening ? "Stop & send" : "Speak"}</span>
        </button>
        <input
          value={draft}
          onChange={(event) => setDraft(event.target.value)}
          placeholder={
            otherOnline
              ? "Or type a message…"
              : "You can prepare a message while you wait…"
          }
        />
        <Button
          size="icon"
          disabled={!draft.trim() || status !== "live"}
          aria-label="Send"
        >
          <Send />
        </Button>
      </form>
      {error && <p className="medium-error">{error}</p>}
    </div>
  );
}
