import uuid
from fastapi.testclient import TestClient

from app.api.dependencies import CurrentUser, get_current_user
from app.core.config import Settings
from app.db.session import get_session
from app.main import create_app


class Session: pass


async def fake_session(): yield Session()


def test_voice_disclosure_and_required_consent():
    settings = Settings(environment="test", _env_file=None)
    app = create_app(settings, include_legacy=False)
    app.dependency_overrides[get_current_user] = lambda: CurrentUser(uuid.uuid4(), "USER")
    app.dependency_overrides[get_session] = fake_session
    with TestClient(app) as client:
        disclosure = client.get("/api/v1/voices/consent")
        assert disclosure.status_code == 200
        assert disclosure.json()["version"] == settings.voice_consent_version
        response = client.post("/api/v1/voices", data={"name":"Mine","language":"en","purpose":"Read my notes",
            "consent_version":settings.voice_consent_version,"ownership_confirmed":"false",
            "single_speaker_confirmed":"true","responsible_use_confirmed":"true"},
            files={"file":("voice.wav",b"RIFFinvalid","audio/wav")})
        assert response.status_code == 422
        assert response.json()["error"]["code"] == "voice_consent_required"
