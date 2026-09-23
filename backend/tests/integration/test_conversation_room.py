import uuid

from fastapi.testclient import TestClient

from app.api.dependencies import get_current_user
from app.core.config import Settings
from app.main import create_app


async def fake_user():
    return type("User", (), {"id": uuid.uuid4(), "is_active": True})()


def test_two_people_exchange_a_translated_room_message_without_guest_account():
    app = create_app(
        Settings(environment="test", secret_key="conversation-test-secret", _env_file=None),
        include_legacy=False,
    )
    app.dependency_overrides[get_current_user] = fake_user
    with TestClient(app) as client:
        created = client.post("/api/v1/calls/rooms", json={"language": "en"})
        assert created.status_code == 200
        host_grant = created.json()
        info = client.get(f"/api/v1/calls/rooms/{host_grant['code']}")
        assert info.status_code == 200
        joined = client.post(
            f"/api/v1/calls/rooms/{host_grant['code']}/join",
            json={"language": "en"},
        )
        assert joined.status_code == 200

        with client.websocket_connect(
            f"/api/v1/calls/rooms/ws?ticket={host_grant['ticket']}"
        ) as host:
            assert host.receive_json()["type"] == "room_ready"
            assert host.receive_json()["type"] == "presence"
            with client.websocket_connect(
                f"/api/v1/calls/rooms/ws?ticket={joined.json()['ticket']}"
            ) as guest:
                assert guest.receive_json()["type"] == "room_ready"
                assert host.receive_json()["guest_connected"] is True
                assert guest.receive_json()["guest_connected"] is True
                host.send_json({"type": "text_turn", "text": "Hello there"})
                assert host.receive_json()["pending"] is True
                assert guest.receive_json()["pending"] is True
                host_message = host.receive_json()
                guest_message = guest.receive_json()
                assert host_message["original_text"] == "Hello there"
                assert guest_message["translated_text"] == "Hello there"
