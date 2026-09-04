import asyncio
import base64
import uuid

import pytest

from app.core.config import Settings
from app.core.errors import AppError
from app.schemas.calls import AudioChunk, TextTurn
from app.services.call_service import BoundedAudioBuffer, CallAssistantService, CallConnectionRegistry, CallTicketService


def test_call_ticket_is_one_time_and_user_scoped():
    settings = Settings(environment="test", secret_key="call-test-secret", _env_file=None)
    user_id = uuid.uuid4(); ticket = CallTicketService.issue(user_id, settings, "rw", "en")
    assert CallTicketService.configuration(ticket, settings) == ("rw", "en")
    assert CallTicketService.consume(ticket, settings) == user_id
    with pytest.raises(AppError) as reused: CallTicketService.consume(ticket, settings)
    assert reused.value.code == "call_ticket_reused"


def test_audio_buffer_applies_backpressure_and_drains_in_order():
    buffer = BoundedAudioBuffer(4, 10)
    for sequence in range(4): buffer.submit(AudioChunk(type="audio_chunk", sequence=sequence, audio=base64.b64encode(b"ab").decode()))
    with pytest.raises(AppError) as full: buffer.submit(AudioChunk(type="audio_chunk", sequence=4, audio=base64.b64encode(b"a").decode()))
    assert full.value.code == "call_backpressure"
    assert asyncio.run(buffer.drain()) == b"abababab"


class Translator:
    async def translate(self, text, source, target): return f"translated:{text}"


class LLM:
    async def complete(self, messages): return "Please let me help resolve that."


def test_call_turn_reuses_translation_and_reply_services():
    service = CallAssistantService(Translator(), LLM())
    result = asyncio.run(service.process_turn(TextTurn(type="text_turn", text="I am frustrated with this bad service"), "en", "rw"))
    assert result["translation"].startswith("translated:")
    assert result["sentiment"] == "negative"
    assert "help" in result["reply_suggestion"]


def test_registry_enforces_connection_ownership_and_cleanup():
    registry = CallConnectionRegistry(); session_id, user_id = uuid.uuid4(), uuid.uuid4()
    registry.add(session_id, user_id)
    assert registry.owns(session_id, user_id)
    assert not registry.owns(session_id, uuid.uuid4())
    registry.remove(session_id)
    assert not registry.owns(session_id, user_id)
