"use client";

import { useState } from "react";
import { Languages, Link2, LoaderCircle, MessagesSquare } from "lucide-react";
import { api } from "@/lib/api";
import { useAuthStore } from "@/stores/auth-store";
import type { ConversationRoomGrant } from "@/types/api";
import { Button } from "@/components/ui/button";
import { ConversationMedium } from "@/components/conversation-medium";

export default function CallsPage() {
  const token = useAuthStore((state) => state.accessToken)!;
  const [language, setLanguage] = useState("rw");
  const [roomType, setRoomType] = useState<"one_to_one" | "group">(
    "one_to_one",
  );
  const [password, setPassword] = useState("");
  const [room, setRoom] = useState<ConversationRoomGrant | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  async function createRoom() {
    setLoading(true);
    setError("");
    try {
      setRoom(
        await api.createConversationRoom(language, roomType, password, token),
      );
    } catch (reason) {
      setError(
        reason instanceof Error
          ? reason.message
          : "Could not create the conversation.",
      );
    } finally {
      setLoading(false);
    }
  }

  const inviteUrl = room
    ? `${window.location.origin}${room.invite_path}`
    : undefined;

  return (
    <section className="calls-page conversation-page">
      <header className="calls-head">
        <div>
          <span className="kicker">EVA CONVERSATION MEDIUM</span>
          <h1>
            Speak your language.
            <br />
            <em>Understand each other.</em>
          </h1>
          <p className="conversation-intro">
            Create a private conversation for two people. EVA turns speech into
            text and translates each message as it travels.
          </p>
        </div>
        <div className="conversation-mark">
          <MessagesSquare />
          <span>
            2 people
            <br />2 languages
          </span>
        </div>
      </header>
      {!room ? (
        <div className="conversation-setup">
          <main>
            <span className="section-number">USER A · CREATE</span>
            <h2>What language will you speak?</h2>
            <p>
              EVA uses this language to recognize your voice and translate your
              messages for User B.
            </p>
            <label>
              Your spoken language
              <select
                value={language}
                onChange={(event) => setLanguage(event.target.value)}
              >
                <option value="rw">Kinyarwanda</option>
                <option value="en">English</option>
              </select>
            </label>
            <div className="room-choice-grid">
              <button
                type="button"
                className={roomType === "one_to_one" ? "active" : ""}
                onClick={() => setRoomType("one_to_one")}
              >
                <strong>One-to-one</strong>
                <small>Only one guest at a time</small>
              </button>
              <button
                type="button"
                className={roomType === "group" ? "active" : ""}
                onClick={() => setRoomType("group")}
              >
                <strong>Group</strong>
                <small>Anyone with the link may join</small>
              </button>
            </div>
            <label>
              Conversation password{" "}
              <small>Optional · leave empty for link-only access</small>
              <input
                type="password"
                value={password}
                minLength={4}
                maxLength={72}
                onChange={(event) => setPassword(event.target.value)}
                placeholder="At least 4 characters"
              />
            </label>
            <Button onClick={createRoom} disabled={loading}>
              {loading ? <LoaderCircle className="spin" /> : <Link2 />} Create
              private conversation
            </Button>
            {error && <p className="form-error">{error}</p>}
          </main>
          <aside>
            <div>
              <strong>01</strong>
              <p>Create a private room in your language.</p>
            </div>
            <div>
              <strong>02</strong>
              <p>Share the secure link with User B.</p>
            </div>
            <div>
              <strong>03</strong>
              <p>Speak, stop, and EVA sends translated text.</p>
            </div>
            <Languages />
          </aside>
        </div>
      ) : (
        <ConversationMedium
          ticket={room.ticket}
          role="host"
          participantId={room.participant_id}
          myLanguage={room.host_language}
          otherLanguage={room.guest_language}
          inviteUrl={inviteUrl}
        />
      )}
    </section>
  );
}
