import uuid
import pytest

from fastapi.testclient import TestClient

from app.api.v1.endpoints.calls import registry
from app.core.config import Settings
from app.db.session import get_session
from app.main import create_app
from app.services.call_service import CallTicketService


class Session:
    def add(self, item): self.item = item
    async def flush(self):
        if self.item.id is None: self.item.id = uuid.uuid4()
    async def commit(self): pass
    async def get(self, model, item_id): return type("User", (), {"id": item_id, "is_active": True})()


session = Session()
async def fake_session(): yield session


def test_authenticated_call_heartbeat_and_clean_end():
    settings = Settings(environment="test", secret_key="websocket-test-secret", _env_file=None)
    user_id = uuid.uuid4(); ticket = CallTicketService.issue(user_id, settings)
    app = create_app(settings, include_legacy=False); app.dependency_overrides[get_session] = fake_session
    with TestClient(app) as client:
        with client.websocket_connect(f"/api/v1/calls/ws?ticket={ticket}") as socket:
            ready = socket.receive_json(); assert ready["type"] == "session_ready"
            call_id = uuid.UUID(ready["session_id"]); assert registry.owns(call_id, user_id)
            socket.send_json({"type":"heartbeat"}); assert socket.receive_json()["type"] == "heartbeat"
            socket.send_json({"type":"end_call"}); summary = socket.receive_json(); assert summary["type"] == "call_summary"
    assert not registry.owns(call_id, user_id)


def test_invalid_ticket_is_rejected():
    app = create_app(Settings(environment="test", _env_file=None), include_legacy=False)
    app.dependency_overrides[get_session] = fake_session
    with TestClient(app) as client:
        with pytest.raises(Exception):
            with client.websocket_connect("/api/v1/calls/ws?ticket=invalid"):
                pass
