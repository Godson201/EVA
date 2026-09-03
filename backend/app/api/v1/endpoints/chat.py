from __future__ import annotations

import json
import uuid

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse

from app.api.dependencies import CurrentUser, get_chat_service, get_current_user
from app.core.errors import AppError
from app.schemas.chat import (
    ChatResponse, ConversationCreate, ConversationDetail, ConversationList,
    ConversationRead, MessageCreate, MessageRead,
)
from app.services.chat_service import ChatService

router = APIRouter()


@router.post("", response_model=ConversationRead, status_code=201)
async def create_conversation(
    payload: ConversationCreate,
    user: CurrentUser = Depends(get_current_user),
    service: ChatService = Depends(get_chat_service),
):
    return await service.create_conversation(user.id, payload.title, payload.language)


@router.get("", response_model=ConversationList)
async def list_conversations(
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    user: CurrentUser = Depends(get_current_user),
    service: ChatService = Depends(get_chat_service),
):
    items, total = await service.repository.list_owned(user.id, offset, limit)
    return ConversationList(items=items, total=total)


@router.get("/{conversation_id}", response_model=ConversationDetail)
async def get_conversation(
    conversation_id: uuid.UUID,
    user: CurrentUser = Depends(get_current_user),
    service: ChatService = Depends(get_chat_service),
):
    conversation = await service.get_conversation(conversation_id, user.id)
    messages = await service.repository.messages(conversation.id)
    return ConversationDetail.model_validate({
        "id": conversation.id, "title": conversation.title, "language": conversation.language,
        "created_at": conversation.created_at, "updated_at": conversation.updated_at, "messages": messages,
    })


@router.delete("/{conversation_id}", status_code=204)
async def archive_conversation(
    conversation_id: uuid.UUID,
    user: CurrentUser = Depends(get_current_user),
    service: ChatService = Depends(get_chat_service),
):
    conversation = await service.get_conversation(conversation_id, user.id)
    await service.repository.archive(conversation)
    await service.session.commit()


@router.post("/{conversation_id}/messages", response_model=ChatResponse)
async def send_message(
    conversation_id: uuid.UUID,
    payload: MessageCreate,
    user: CurrentUser = Depends(get_current_user),
    service: ChatService = Depends(get_chat_service),
):
    user_message, assistant = await service.prompt(conversation_id, user.id, payload.content.strip(), payload.language)
    return ChatResponse(user_message=MessageRead.model_validate(user_message), assistant_message=MessageRead.model_validate(assistant))


@router.post("/{conversation_id}/messages/stream")
async def stream_message(
    conversation_id: uuid.UUID,
    payload: MessageCreate,
    user: CurrentUser = Depends(get_current_user),
    service: ChatService = Depends(get_chat_service),
):
    # Check ownership before the streaming response starts so 404 remains a normal API error.
    await service.get_conversation(conversation_id, user.id)

    async def events():
        try:
            async for chunk in service.stream_prompt(conversation_id, user.id, payload.content.strip(), payload.language):
                yield f"event: delta\ndata: {json.dumps({'text': chunk})}\n\n"
            yield "event: done\ndata: {}\n\n"
        except AppError as exc:
            yield f"event: error\ndata: {json.dumps({'code': exc.code, 'message': exc.message})}\n\n"

    return StreamingResponse(events(), media_type="text/event-stream", headers={"Cache-Control": "no-cache"})
