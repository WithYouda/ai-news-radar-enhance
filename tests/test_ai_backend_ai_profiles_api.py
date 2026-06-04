from fastapi.testclient import TestClient

from server.ai_radar_api.config import AppConfig
from server.ai_radar_api.main import create_app


def _client(tmp_path):
    config = AppConfig(
        public_base_url="https://withyouda.github.io/ai-news-radar-enhance",
        allowed_origins=["https://withyouda.github.io"],
        admin_password="pass",
        session_secret="session-secret",
        db_path=tmp_path / "radar.db",
        ai_base_url="https://env.example.com/v1",
        ai_api_key="sk-env",
        ai_model="env-model",
        encryption_key="test-master-key",
    )
    return TestClient(create_app(config), base_url="https://testserver")


def _login(client):
    res = client.post("/api/auth/login", json={"password": "pass"})
    assert res.status_code == 200


def test_ai_profile_routes_require_login(tmp_path):
    client = _client(tmp_path)

    res = client.get("/api/ai-profiles")

    assert res.status_code == 401


def test_ai_profile_api_never_returns_plaintext_key_or_headers(tmp_path):
    client = _client(tmp_path)
    _login(client)

    res = client.post(
        "/api/ai-profiles",
        json={
            "name": "Reader AI",
            "type": "chat_completions",
            "base_url": "https://api.example.com/v1",
            "model": "gpt-4.1-mini",
            "api_key": "sk-secret",
            "headers_json": '{"X-Test":"secret-header"}',
            "timeout_seconds": 45,
        },
    )

    assert res.status_code == 200
    assert "sk-secret" not in res.text
    assert "secret-header" not in res.text
    payload = res.json()
    assert payload["has_api_key"] is True
    assert payload["headers_preview"] == ["X-Test"]

    listed = client.get("/api/ai-profiles").json()["items"]
    assert listed[0]["id"] == payload["id"]
    assert "sk-secret" not in str(listed)
    assert "secret-header" not in str(listed)


def test_ai_profile_update_with_blank_key_preserves_existing_secret(tmp_path):
    client = _client(tmp_path)
    _login(client)
    created = client.post(
        "/api/ai-profiles",
        json={
            "name": "Reader AI",
            "type": "responses",
            "base_url": "https://api.example.com/v1",
            "model": "old-model",
            "api_key": "sk-old",
            "headers_json": '{"X-Trace":"old-secret"}',
        },
    ).json()

    updated = client.put(
        f"/api/ai-profiles/{created['id']}",
        json={
            "name": "Reader AI Updated",
            "type": "responses",
            "base_url": "https://api.example.com/v1",
            "model": "new-model",
            "api_key": "",
            "headers_json": "",
            "timeout_seconds": 30,
        },
    )

    assert updated.status_code == 200
    assert updated.json()["model"] == "new-model"
    assert updated.json()["has_api_key"] is True
    assert "sk-old" not in updated.text
    assert "old-secret" not in updated.text


def test_ai_profile_delete_removes_profile(tmp_path):
    client = _client(tmp_path)
    _login(client)
    created = client.post(
        "/api/ai-profiles",
        json={
            "name": "Delete AI",
            "type": "chat_completions",
            "base_url": "https://api.example.com/v1",
            "model": "gpt-4.1-mini",
            "api_key": "sk-delete",
        },
    ).json()

    deleted = client.delete(f"/api/ai-profiles/{created['id']}")

    assert deleted.status_code == 200
    assert deleted.json() == {"ok": True}
    assert client.get("/api/ai-profiles").json()["items"][0]["id"] == "env"


def test_ai_profile_api_rejects_invalid_headers_json(tmp_path):
    client = _client(tmp_path)
    _login(client)

    res = client.post(
        "/api/ai-profiles",
        json={
            "name": "Bad",
            "type": "chat_completions",
            "base_url": "https://api.example.com/v1",
            "model": "gpt-4.1-mini",
            "headers_json": "{not-json",
        },
    )

    assert res.status_code == 400
    assert "headers_json" in res.text


def test_ai_profile_test_connection_uses_selected_profile(monkeypatch, tmp_path):
    captured = {}
    client = _client(tmp_path)
    _login(client)
    created = client.post(
        "/api/ai-profiles",
        json={
            "name": "Test AI",
            "type": "chat_completions",
            "base_url": "https://api.example.com/v1",
            "model": "gpt-4.1-mini",
            "api_key": "sk-test",
        },
    ).json()

    async def fake_chat(self, messages, temperature=0.2):
        captured["profile"] = self.profile
        return "ok"

    monkeypatch.setattr("server.ai_radar_api.provider.AIProvider.chat", fake_chat)

    res = client.post(f"/api/ai-profiles/{created['id']}/test")

    assert res.status_code == 200
    assert res.json()["ok"] is True
    assert captured["profile"]["api_key"] == "sk-test"
    assert captured["profile"]["model"] == "gpt-4.1-mini"
