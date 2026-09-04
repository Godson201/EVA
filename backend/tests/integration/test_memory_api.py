from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
import uuid

from fastapi.testclient import TestClient

from app.api.dependencies import CurrentUser, get_current_user, get_memory_service
from app.core.errors import AppError
from app.main import create_app
from app.core.config import Settings

USER_ID = uuid.uuid4()
OTHER_ID = uuid.uuid4()


class FakeSession:
    async def commit(self): pass
    async def refresh(self, item): pass


def memory(user_id=USER_ID, **values):
    now = datetime.now(UTC)
    base = dict(id=uuid.uuid4(), user_id=user_id, category="preference", content="Use Kinyarwanda", status="proposed",
                provenance={"source": "user"}, source_message_id=None, approved_at=None, rejected_at=None,
                expires_at=now + timedelta(days=30), last_used_at=None, created_at=now, updated_at=now)
    base.update(values)
    return SimpleNamespace(**base)


class FakeRepository:
    def __init__(self, service): self.service = service
    async def list_owned(self, user_id, status, offset, limit):
        rows = [m for m in self.service.items.values() if m.user_id == user_id and (not status or m.status == status)]
        return rows[offset:offset + limit], len(rows)
    async def delete(self, item): self.service.items.pop(item.id)


class FakeMemoryService:
    def __init__(self):
        self.items, self.session = {}, FakeSession()
        self.repository = FakeRepository(self)
    async def create(self, user_id, category, content, provenance, retention):
        item = memory(user_id, category=category, content=content, provenance=provenance)
        self.items[item.id] = item
        return item
    async def owned(self, memory_id, user_id):
        item = self.items.get(memory_id)
        if item is None or item.user_id != user_id:
            raise AppError("memory_not_found", "Memory not found", status_code=404)
        return item
    async def approve(self, memory_id, user_id):
        item = await self.owned(memory_id, user_id); item.status = "approved"; item.approved_at = datetime.now(UTC); return item
    async def reject(self, memory_id, user_id):
        item = await self.owned(memory_id, user_id); item.status = "rejected"; item.rejected_at = datetime.now(UTC); return item
    async def edit(self, memory_id, user_id, category, content, provenance, retention):
        item = await self.owned(memory_id, user_id); item.content = content; item.category = category or item.category; item.status = "proposed"; return item


def test_memory_consent_flow_and_permanent_delete():
    service = FakeMemoryService()
    app = create_app(Settings(environment="test", _env_file=None), include_legacy=False)
    app.dependency_overrides[get_current_user] = lambda: CurrentUser(USER_ID, "USER")
    app.dependency_overrides[get_memory_service] = lambda: service
    with TestClient(app) as client:
        created = client.post("/api/v1/memories", json={"category": "preference", "content": "Use Kinyarwanda"})
        assert created.status_code == 201 and created.json()["status"] == "proposed"
        memory_id = created.json()["id"]
        approved = client.post(f"/api/v1/memories/{memory_id}/approve")
        assert approved.status_code == 200 and approved.json()["status"] == "approved"
        assert client.delete(f"/api/v1/memories/{memory_id}").status_code == 204
        assert client.get(f"/api/v1/memories/{memory_id}").status_code == 404


def test_cross_user_memory_is_hidden():
    service = FakeMemoryService()
    private = memory(OTHER_ID)
    service.items[private.id] = private
    app = create_app(Settings(environment="test", _env_file=None), include_legacy=False)
    app.dependency_overrides[get_current_user] = lambda: CurrentUser(USER_ID, "USER")
    app.dependency_overrides[get_memory_service] = lambda: service
    with TestClient(app) as client:
        response = client.get(f"/api/v1/memories/{private.id}")
        assert response.status_code == 404
