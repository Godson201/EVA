import asyncio
import uuid
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest
from jose import jwt

from app.core.config import Settings
from app.core.errors import AppError
from app.services.auth_service import AuthService


class Session:
    def __init__(self, scalar_value=None): self.scalar_value, self.added, self.commits = scalar_value, [], 0
    def add(self, value): self.added.append(value)
    async def flush(self):
        for item in self.added:
            if item.id is None: item.id = uuid.uuid4()
    async def scalar(self, query): return self.scalar_value
    async def execute(self, query): return None
    async def commit(self): self.commits += 1


def test_access_token_uses_uuid_subject_and_short_expiry():
    settings = Settings(environment="test", secret_key="test-secret", _env_file=None)
    service = AuthService(Session(), settings)
    user = SimpleNamespace(id=uuid.uuid4(), role="USER")
    payload = jwt.decode(service._access(user), settings.secret_key, algorithms=["HS256"])
    assert payload["sub"] == str(user.id)
    assert payload["role"] == "USER"


def test_refresh_token_reuse_revokes_family():
    token = SimpleNamespace(revoked_at=datetime.now(UTC), family_id=uuid.uuid4(), expires_at=datetime.now(UTC) + timedelta(days=1))
    session = Session(token)
    service = AuthService(session, Settings(environment="test", _env_file=None))
    with pytest.raises(AppError) as error:
        asyncio.run(service.rotate("already-used"))
    assert error.value.code == "refresh_token_reused"
    assert session.commits == 1
