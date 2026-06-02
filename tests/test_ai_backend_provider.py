import anyio
import httpx
import pytest

from server.ai_radar_api.config import AppConfig
from server.ai_radar_api.provider import AIProvider, AIProviderUnavailable


def test_provider_wraps_upstream_http_errors_as_unavailable(monkeypatch, tmp_path):
    config = AppConfig(
        public_base_url="https://withyouda.github.io/ai-news-radar-enhance",
        allowed_origins=["https://withyouda.github.io"],
        admin_password="pass",
        session_secret="session-secret",
        db_path=tmp_path / "radar.db",
        ai_base_url="https://api.example.com/v1",
        ai_api_key="sk-test",
        ai_model="test-model",
    )

    class FakeResponse:
        def raise_for_status(self):
            request = httpx.Request("POST", "https://api.example.com/v1/chat/completions")
            response = httpx.Response(429, request=request)
            raise httpx.HTTPStatusError("rate limited", request=request, response=response)

        def json(self):
            return {}

    class FakeClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def post(self, *args, **kwargs):
            return FakeResponse()

    monkeypatch.setattr("server.ai_radar_api.provider.httpx.AsyncClient", lambda timeout: FakeClient())

    with pytest.raises(AIProviderUnavailable):
        anyio.run(AIProvider(config).chat, [{"role": "user", "content": "hi"}])
