from __future__ import annotations

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Query, Request, WebSocket, WebSocketDisconnect
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import CurrentUser, get_current_user
from app.core.errors import AppError
from app.db.session import get_session
from app.models import CallSession, User
from app.schemas.calls import AudioChunk, CallConfig, CallSessionRead, CallTicket, TextTurn
from app.services.call_service import BoundedAudioBuffer, CallAssistantService, CallConnectionRegistry, CallTicketService
from app.services.llm_service import build_llm_service
from app.services.translation_service import NLLBTranslationService

router = APIRouter()
registry = CallConnectionRegistry()


@router.post("/tickets", response_model=CallTicket)
async def create_call_ticket(payload: CallConfig, request: Request, user: CurrentUser = Depends(get_current_user)):
    settings = request.app.state.settings
    return CallTicket(ticket=CallTicketService.issue(user.id, settings, payload.source_language, payload.target_language), expires_in=settings.call_ticket_seconds)


@router.get("/sessions", response_model=list[CallSessionRead])
async def list_call_sessions(limit: int = Query(default=20, ge=1, le=100), user: CurrentUser = Depends(get_current_user), session: AsyncSession = Depends(get_session)):
    rows = await session.scalars(select(CallSession).where(CallSession.user_id == user.id).order_by(CallSession.created_at.desc()).limit(limit))
    return list(rows)


@router.get("/sessions/{session_id}", response_model=CallSessionRead)
async def get_call_session(session_id: uuid.UUID, user: CurrentUser = Depends(get_current_user), session: AsyncSession = Depends(get_session)):
    item = await session.scalar(select(CallSession).where(CallSession.id == session_id, CallSession.user_id == user.id))
    if item is None: raise AppError("call_session_not_found", "Call session not found", status_code=404)
    return item


@router.websocket("/ws")
async def call_websocket(websocket: WebSocket, ticket: str, session: AsyncSession = Depends(get_session)):
    settings = websocket.app.state.settings
    try:
        source, target = CallTicketService.configuration(ticket, settings)
        user_id = CallTicketService.consume(ticket, settings)
        user = await session.get(User, user_id)
        if user is None or not user.is_active: raise AppError("invalid_call_ticket", "Call user is unavailable", status_code=401)
    except Exception:
        await websocket.close(code=4401, reason="Invalid or expired call ticket"); return
    await websocket.accept()
    item = CallSession(user_id=user_id, status="active", source_language=source, target_language=target,
                       transcript=[], action_items=[], sentiment_cues=[])
    session.add(item); await session.flush(); await session.commit()
    registry.add(item.id, user_id, websocket)
    buffer = BoundedAudioBuffer(settings.call_audio_queue_chunks, settings.call_max_buffer_bytes)
    assistant = CallAssistantService(NLLBTranslationService(settings), build_llm_service(settings))
    await websocket.send_json({"type":"session_ready","session_id":str(item.id),"source_language":source,"target_language":target})
    try:
        while True:
            message = await websocket.receive_json(); event_type = message.get("type")
            try:
                if event_type == "heartbeat": await websocket.send_json({"type":"heartbeat","at":datetime.now(UTC).isoformat()})
                elif event_type == "audio_chunk":
                    event = AudioChunk.model_validate(message); buffer.submit(event)
                    await websocket.send_json({"type":"audio_ack","sequence":event.sequence,"buffered_bytes":buffer.total_bytes})
                elif event_type == "end_audio":
                    audio = await buffer.drain(); await websocket.send_json({"type":"audio_buffered","bytes":len(audio),"message":"Audio is ready for the future streaming STT worker."}); buffer.clear()
                elif event_type == "text_turn":
                    result = await assistant.process_turn(TextTurn.model_validate(message), source, target)
                    item.transcript = [*item.transcript, result]; item.sentiment_cues = [*item.sentiment_cues, {"cue":result["sentiment"],"timestamp":result["timestamp"]}]
                    await session.commit()
                    await websocket.send_json({"type":"final_transcript","speaker":result["speaker"],"text":result["text"],"language":result["language"]})
                    await websocket.send_json({"type":"translation","text":result["translation"],"language":target})
                    await websocket.send_json({"type":"reply_suggestion","text":result["reply_suggestion"],"language":target})
                    await websocket.send_json({"type":"sentiment_cue","cue":result["sentiment"]})
                elif event_type == "end_call": break
                else: raise AppError("unknown_call_event", "Unsupported call event", status_code=422)
            except AppError as exc:
                await websocket.send_json({"type":"error","code":exc.code,"message":exc.message,"retryable":exc.status_code in {429,503}})
    except WebSocketDisconnect:
        item.status = "disconnected"
    except Exception:
        item.status = "failed"
        try: await websocket.send_json({"type":"error","code":"call_session_error","message":"The call session ended unexpectedly","retryable":False})
        except Exception: pass
    finally:
        try:
            wrap = await assistant.wrap_up(item.transcript)
            item.summary, item.action_items = wrap.summary, wrap.action_items
        except Exception:
            item.summary, item.action_items = "Call ended; automatic summary was unavailable.", []
        item.status = "completed" if item.status == "active" else item.status
        item.ended_at = datetime.now(UTC); await session.commit(); registry.remove(item.id); buffer.clear()
        if item.status == "completed":
            try: await websocket.send_json({"type":"call_summary","summary":item.summary,"action_items":item.action_items})
            except Exception: pass
