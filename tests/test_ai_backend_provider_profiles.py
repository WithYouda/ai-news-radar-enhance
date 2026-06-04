import asyncio

from server.ai_radar_api.config import AppConfig
from server.ai_radar_api.provider import AIProvider


def _config(tmp_path):
    return AppConfig(
        public_base_url="https://withyouda.github.io/ai-news-radar-enhance",
        allowed_origins=["https://withyouda.github.io"],
        admin_password="pass",
        session_secret="session-secret",
        db_path=tmp_path / "radar.db",
        ai_base_url="https://env.example.com/v1",
        ai_api_key="sk-env",
        ai_model="env-model",
        ai_api_format="chat_completions",
    )


class FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


class FakeAsyncClient:
    calls = []

    def __init__(self, timeout=45):
        self.timeout = timeout

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def post(self, url, headers=None, json=None):
        self.calls.append({"url": url, "headers": headers or {}, "json": json or {}, "timeout": self.timeout})
        if url.endswith("/responses"):
            return FakeResponse({"output_text": "profile response"})
        return FakeResponse({"choices": [{"message": {"content": "profile chat"}}]})


def test_ai_provider_uses_profile_base_url_key_model_headers_and_timeout(monkeypatch, tmp_path):
    FakeAsyncClient.calls = []
    monkeypatch.setattr("server.ai_radar_api.provider.httpx.AsyncClient", FakeAsyncClient)
    provider = AIProvider(
        _config(tmp_path),
        profile={
            "type": "chat_completions",
            "base_url": "https://profile.example/v1",
            "api_key": "sk-profile",
            "model": "profile-model",
            "headers": {"X-Extra": "value"},
            "timeout_seconds": 12,
        },
    )

    result = asyncio.run(provider.chat([{"role": "user", "content": "hello"}], temperature=0))

    assert result == "profile chat"
    call = FakeAsyncClient.calls[0]
    assert call["url"] == "https://profile.example/v1/chat/completions"
    assert call["headers"]["Authorization"] == "Bearer sk-profile"
    assert call["headers"]["X-Extra"] == "value"
    assert call["json"]["model"] == "profile-model"
    assert call["timeout"] == 12


def test_ai_provider_supports_profile_responses_format(monkeypatch, tmp_path):
    FakeAsyncClient.calls = []
    monkeypatch.setattr("server.ai_radar_api.provider.httpx.AsyncClient", FakeAsyncClient)
    provider = AIProvider(
        _config(tmp_path),
        profile={
            "type": "responses",
            "base_url": "https://profile.example/v1",
            "api_key": "sk-profile",
            "model": "response-model",
            "headers": {},
        },
    )

    result = asyncio.run(provider.chat([{"role": "user", "content": "hello"}], temperature=0))

    assert result == "profile response"
    call = FakeAsyncClient.calls[0]
    assert call["url"] == "https://profile.example/v1/responses"
    assert call["json"]["model"] == "response-model"
    assert call["json"]["input"][0]["content"] == "hello"


def test_ai_provider_still_uses_env_config_without_profile(monkeypatch, tmp_path):
    FakeAsyncClient.calls = []
    monkeypatch.setattr("server.ai_radar_api.provider.httpx.AsyncClient", FakeAsyncClient)
    provider = AIProvider(_config(tmp_path))

    result = asyncio.run(provider.chat([{"role": "user", "content": "hello"}], temperature=0))

    assert result == "profile chat"
    call = FakeAsyncClient.calls[0]
    assert call["url"] == "https://env.example.com/v1/chat/completions"
    assert call["headers"]["Authorization"] == "Bearer sk-env"
    assert call["json"]["model"] == "env-model"
