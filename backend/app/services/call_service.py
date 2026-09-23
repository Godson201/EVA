from __future__ import annotations

import asyncio
import base64
import json
import re
import secrets
import bcrypt
import threading
import uuid
from datetime import UTC, datetime, timedelta

from jose import JWTError, jwt
from pydantic import ValidationError

from app.core.errors import AppError
from app.schemas.calls import AudioChunk, CallWrapUp, TextTurn
from app.services.language_detection_service import LanguageDetectionService


class CallTicketService:
    _used: dict[str, float] = {}
    _lock = threading.Lock()

    @classmethod
    def issue(cls, user_id: uuid.UUID, settings, source: str = "auto", target: str = "en") -> str:
        now = datetime.now(UTC)
        return jwt.encode({"sub": str(user_id), "aud": "eva-call", "jti": str(uuid.uuid4()), "source": source, "target": target, "iat": now,
                           "exp": now + timedelta(seconds=settings.call_ticket_seconds)}, settings.secret_key, algorithm="HS256")

    @classmethod
    def consume(cls, ticket: str, settings) -> uuid.UUID:
        try: payload = jwt.decode(ticket, settings.secret_key, algorithms=["HS256"], audience="eva-call")
        except (JWTError, ValueError, KeyError) as exc: raise AppError("invalid_call_ticket", "Call ticket is invalid or expired", status_code=401) from exc
        jti = payload.get("jti")
        with cls._lock:
            now = datetime.now(UTC).timestamp()
            cls._used = {key: expiry for key, expiry in cls._used.items() if expiry > now}
            if not jti or jti in cls._used: raise AppError("call_ticket_reused", "Call ticket has already been used", status_code=401)
            cls._used[jti] = float(payload["exp"])
        return uuid.UUID(payload["sub"])

    @staticmethod
    def configuration(ticket: str, settings) -> tuple[str, str]:
        payload = jwt.decode(ticket, settings.secret_key, algorithms=["HS256"], audience="eva-call")
        return payload.get("source", "auto"), payload.get("target", "en")


class ConversationRoomRegistry:
    def __init__(self):
        self.rooms: dict[str, dict] = {}

    def create(self, user_id: uuid.UUID, language: str, room_type: str = "one_to_one", password: str | None = None) -> dict:
        code = secrets.token_urlsafe(7).replace("_", "").replace("-", "")[:9]
        while code in self.rooms:
            code = secrets.token_urlsafe(7).replace("_", "").replace("-", "")[:9]
        room = {
            "code": code,
            "user_id": user_id,
            "host_language": language,
            "guest_language": None,
            "room_type": room_type,
            "password_hash": bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode() if password else None,
            "participants": {"host": {"language": language, "role": "host"}},
            "connections": {},
            "messages": [],
            "created_at": datetime.now(UTC),
        }
        self.rooms[code] = room
        return room

    def get(self, code: str) -> dict | None:
        return self.rooms.get(code)

    def admit_guest(self, code: str, language: str, password: str | None = None) -> tuple[dict, str]:
        room = self.rooms[code]
        password_hash = room["password_hash"]
        if password_hash and (not password or not bcrypt.checkpw(password.encode(), password_hash.encode())):
            raise AppError("incorrect_room_password", "The conversation password is incorrect", status_code=401)
        active_guests = [key for key in room["connections"] if key != "host"]
        if room["room_type"] == "one_to_one" and active_guests:
            raise AppError("conversation_room_full", "This one-to-one conversation already has a guest", status_code=409)
        participant = f"guest-{secrets.token_urlsafe(6)}"
        room["participants"][participant] = {"language": language, "role": "guest"}
        room["guest_language"] = language
        return room, participant

    def connect(self, code: str, participant: str, websocket) -> None:
        self.rooms[code]["connections"][participant] = websocket

    def disconnect(self, code: str, participant: str) -> None:
        room = self.rooms.get(code)
        if room:
            room["connections"].pop(participant, None)

    def presence(self, code: str) -> dict:
        room = self.rooms[code]
        return {
            "type": "presence",
            "host_connected": "host" in room["connections"],
            "guest_connected": any(key != "host" for key in room["connections"]),
            "participant_count": len(room["connections"]),
            "languages": list({room["participants"][key]["language"] for key in room["connections"]}),
        }

    async def broadcast(self, code: str, event: dict) -> None:
        room = self.rooms.get(code)
        if not room:
            return
        stale = []
        for participant, socket in list(room["connections"].items()):
            try:
                await socket.send_json(event)
            except Exception:
                stale.append(participant)
        for participant in stale:
            room["connections"].pop(participant, None)

    async def close_all(self):
        rooms = list(self.rooms.values())
        self.rooms.clear()
        for room in rooms:
            for websocket in room["connections"].values():
                try:
                    await websocket.close(code=1012, reason="Server shutting down")
                except Exception:
                    pass


class ConversationRoomTicketService:
    @staticmethod
    def issue(code: str, participant: str, language: str, settings, user_id: uuid.UUID | None = None) -> str:
        now = datetime.now(UTC)
        payload = {
            "aud": "eva-conversation-room",
            "room": code,
            "participant": participant,
            "language": language,
            "iat": now,
            "exp": now + timedelta(hours=24),
        }
        if user_id:
            payload["sub"] = str(user_id)
        return jwt.encode(payload, settings.secret_key, algorithm="HS256")

    @staticmethod
    def decode(ticket: str, settings) -> dict:
        try:
            return jwt.decode(ticket, settings.secret_key, algorithms=["HS256"], audience="eva-conversation-room")
        except (JWTError, ValueError, KeyError) as exc:
            raise AppError("invalid_room_ticket", "Conversation link is invalid or expired", status_code=401) from exc


class BoundedAudioBuffer:
    def __init__(self, chunks: int, max_bytes: int):
        self.queue: asyncio.Queue[tuple[int, bytes]] = asyncio.Queue(maxsize=chunks)
        self.max_bytes, self.total_bytes, self.parts, self.next_sequence = max_bytes, 0, [], 0

    def submit(self, event: AudioChunk):
        if event.sequence != self.next_sequence:
            raise AppError("audio_sequence_error", f"Expected audio sequence {self.next_sequence}", status_code=409)
        try: decoded = base64.b64decode(event.audio, validate=True)
        except ValueError as exc: raise AppError("invalid_audio_chunk", "Audio chunk is not valid base64", status_code=422) from exc
        if len(decoded) > 64 * 1024: raise AppError("audio_chunk_too_large", "Audio chunks cannot exceed 64 KiB", status_code=413)
        if self.total_bytes + len(decoded) > self.max_bytes or self.queue.full():
            raise AppError("call_backpressure", "Audio buffer is full; pause sending and retry", status_code=429)
        self.queue.put_nowait((event.sequence, decoded)); self.total_bytes += len(decoded); self.next_sequence += 1

    async def drain(self):
        while not self.queue.empty(): self.parts.append((await self.queue.get())[1]); self.queue.task_done()
        return b"".join(self.parts)

    def clear(self): self.parts.clear(); self.total_bytes = 0; self.next_sequence = 0


class CallConnectionRegistry:
    def __init__(self): self.connections: dict[uuid.UUID, tuple[uuid.UUID, object | None]] = {}
    def add(self, session_id, user_id, websocket=None): self.connections[session_id] = (user_id, websocket)
    def remove(self, session_id): self.connections.pop(session_id, None)
    def owns(self, session_id, user_id): return bool(self.connections.get(session_id) and self.connections[session_id][0] == user_id)
    async def close_all(self):
        connections = list(self.connections.values()); self.connections.clear()
        for _, websocket in connections:
            if websocket is not None:
                try: await websocket.close(code=1012, reason="Server shutting down")
                except Exception: pass


class CallAssistantService:
    NEGATIVE = {"angry", "upset", "frustrated", "complaint", "bad", "ikibazo", "birababaje"}

    def __init__(self, translator, llm, detector=None):
        self.translator, self.llm, self.detector = translator, llm, detector or LanguageDetectionService()

    async def process_turn(self, event: TextTurn, configured_source: str, target: str):
        source = self.detector.detect(event.text)[0] if configured_source == "auto" else configured_source
        translated = event.text if source == target else await self.translator.translate(event.text, source, target)
        language = "English" if target == "en" else "Kinyarwanda"
        suggestion = await self.llm.complete([{"role":"system","content":f"Suggest one concise, courteous call-center reply in {language}. Return only the reply."},{"role":"user","content":translated}])
        words = set(re.findall(r"[a-zA-ZÀ-ÿ']+", event.text.lower()))
        cue = "negative" if words & self.NEGATIVE else "neutral"
        return {"speaker":event.speaker,"text":event.text,"language":source,"translation":translated,
                "reply_suggestion":suggestion.strip(),"sentiment":cue,"timestamp":datetime.now(UTC).isoformat()}

    async def wrap_up(self, transcript: list[dict]):
        if not transcript: return CallWrapUp(summary="No spoken turns were captured.", action_items=[])
        text = "\n".join(f"{x['speaker']}: {x['text']}" for x in transcript)
        response = await self.llm.complete([{"role":"system","content":"Summarize this call and return JSON only: {\"summary\":\"...\",\"action_items\":[\"...\"]}"},{"role":"user","content":text}])
        try:
            match = re.search(r"\{.*\}", response, re.S)
            return CallWrapUp.model_validate(json.loads(match.group() if match else ""))
        except (ValueError, json.JSONDecodeError, ValidationError):
            return CallWrapUp(summary="Call completed. Review the transcript for details.", action_items=[])
