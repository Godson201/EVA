from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query

from app.api.dependencies import CurrentUser, get_current_user, get_memory_service
from app.schemas.memory import MemoryCreate, MemoryList, MemoryRead, MemoryStatus, MemoryUpdate
from app.services.memory_service import MemoryService

router = APIRouter()


@router.post("", response_model=MemoryRead, status_code=201)
async def create_memory(payload: MemoryCreate, user: CurrentUser = Depends(get_current_user),
                        service: MemoryService = Depends(get_memory_service)):
    memory = await service.create(user.id, payload.category, payload.content, payload.provenance, payload.retention_days)
    await service.session.commit()
    await service.session.refresh(memory)
    return memory


@router.get("", response_model=MemoryList)
async def list_memories(status: MemoryStatus | None = None, offset: int = Query(default=0, ge=0),
                        limit: int = Query(default=20, ge=1, le=100), user: CurrentUser = Depends(get_current_user),
                        service: MemoryService = Depends(get_memory_service)):
    items, total = await service.repository.list_owned(user.id, status, offset, limit)
    return MemoryList(items=items, total=total)


@router.get("/{memory_id}", response_model=MemoryRead)
async def get_memory(memory_id: uuid.UUID, user: CurrentUser = Depends(get_current_user),
                     service: MemoryService = Depends(get_memory_service)):
    return await service.owned(memory_id, user.id)


@router.put("/{memory_id}", response_model=MemoryRead)
async def edit_memory(memory_id: uuid.UUID, payload: MemoryUpdate, user: CurrentUser = Depends(get_current_user),
                      service: MemoryService = Depends(get_memory_service)):
    memory = await service.edit(memory_id, user.id, payload.category, payload.content, payload.provenance, payload.retention_days)
    await service.session.commit()
    await service.session.refresh(memory)
    return memory


@router.post("/{memory_id}/approve", response_model=MemoryRead)
async def approve_memory(memory_id: uuid.UUID, user: CurrentUser = Depends(get_current_user),
                         service: MemoryService = Depends(get_memory_service)):
    memory = await service.approve(memory_id, user.id)
    await service.session.commit()
    await service.session.refresh(memory)
    return memory


@router.post("/{memory_id}/reject", response_model=MemoryRead)
async def reject_memory(memory_id: uuid.UUID, user: CurrentUser = Depends(get_current_user),
                        service: MemoryService = Depends(get_memory_service)):
    memory = await service.reject(memory_id, user.id)
    await service.session.commit()
    await service.session.refresh(memory)
    return memory


@router.delete("/{memory_id}", status_code=204)
async def delete_memory(memory_id: uuid.UUID, user: CurrentUser = Depends(get_current_user),
                        service: MemoryService = Depends(get_memory_service)):
    memory = await service.owned(memory_id, user.id)
    await service.repository.delete(memory)
    await service.session.commit()
