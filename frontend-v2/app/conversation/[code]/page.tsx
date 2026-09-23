"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { Languages, LoaderCircle, MessagesSquare } from "lucide-react";
import { api } from "@/lib/api";
import type { ConversationRoomGrant, ConversationRoomInfo } from "@/types/api";
import { Button } from "@/components/ui/button";
import { ConversationMedium } from "@/components/conversation-medium";

export default function GuestConversationPage() {
  const { code } = useParams<{ code: string }>();
  const [room, setRoom] = useState<ConversationRoomInfo | null>(null),
    [grant, setGrant] = useState<ConversationRoomGrant | null>(null),
    [language, setLanguage] = useState("en"),
    [password, setPassword] = useState(""),
    [loading, setLoading] = useState(true),
    [error, setError] = useState("");
  useEffect(() => {
    api
      .conversationRoom(code)
      .then(setRoom)
      .catch((reason) => setError(reason.message))
      .finally(() => setLoading(false));
  }, [code]);
  async function join() {
    setLoading(true);
    setError("");
    try {
      setGrant(await api.joinConversationRoom(code, language, password));
    } catch (reason) {
      setError(
        reason instanceof Error
          ? reason.message
          : "Could not join the conversation.",
      );
    } finally {
      setLoading(false);
    }
  }
  if (grant)
    return (
      <main className="guest-conversation">
        <header className="guest-brand">
          <span className="eva-mark">E</span>
          <strong>EVA</strong>
          <small>Private translated conversation</small>
        </header>
        <ConversationMedium
          ticket={grant.ticket}
          role="guest"
          participantId={grant.participant_id}
          myLanguage={grant.guest_language || language}
          otherLanguage={grant.host_language}
        />
      </main>
    );
  return (
    <main className="guest-join-page">
      <div className="guest-join-card">
        <div className="guest-brand">
          <span className="eva-mark">E</span>
          <strong>EVA</strong>
        </div>
        {loading ? (
          <div className="guest-loading">
            <LoaderCircle className="spin" /> Opening your invitation…
          </div>
        ) : error ? (
          <p className="form-error">{error}</p>
        ) : (
          room && (
            <>
              <div className="guest-join-icon">
                <MessagesSquare />
              </div>
              <span className="kicker">YOU ARE USER B</span>
              <h1>Join the conversation</h1>
              <p>
                User A will speak{" "}
                <strong>
                  {room.host_language === "rw" ? "Kinyarwanda" : "English"}
                </strong>
                . Choose the language in which you want to speak and read their
                messages.
              </p>
              <label>
                Your language
                <select
                  value={language}
                  onChange={(event) => setLanguage(event.target.value)}
                >
                  <option value="en">English</option>
                  <option value="rw">Kinyarwanda</option>
                </select>
              </label>
              {room.password_required && (
                <label>
                  Conversation password
                  <input
                    type="password"
                    value={password}
                    onChange={(event) => setPassword(event.target.value)}
                    placeholder="Enter the password from User A"
                  />
                </label>
              )}
              <Button onClick={join}>
                <Languages /> Join without an account
              </Button>
              <div className="room-access-note">
                {room.room_type === "group"
                  ? "Group room · multiple people can join with this link."
                  : "One-to-one room · one guest can participate at a time."}
              </div>
              <small className="privacy-note">
                Your microphone starts only when you press Speak. EVA does not
                retain voice recordings in this conversation.
              </small>
            </>
          )
        )}
      </div>
    </main>
  );
}
