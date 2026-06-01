from fastapi.testclient import TestClient

from server.ai_radar_api.config import AppConfig
from server.ai_radar_api.main import create_app


def make_client(tmp_path, password="pass"):
    config = AppConfig(
        public_base_url="https://withyouda.github.io/ai-news-radar-enhance",
        allowed_origins=["https://withyouda.github.io"],
        admin_password=password,
        session_secret="test-session-secret",
        db_path=tmp_path / "radar.db",
        ai_base_url="https://api.example.com/v1",
        ai_api_key="sk-test",
        ai_model="test-model",
    )
    return TestClient(create_app(config))


def test_health_is_public(tmp_path):
    client = make_client(tmp_path)
    res = client.get("/health")
    assert res.status_code == 200
    assert res.json()["ok"] is True


def test_login_rejects_wrong_password(tmp_path):
    client = make_client(tmp_path)
    res = client.post("/api/auth/login", json={"password": "wrong"})
    assert res.status_code == 401


def test_login_sets_secure_httponly_cookie(tmp_path):
    client = make_client(tmp_path)
    res = client.post("/api/auth/login", json={"password": "pass"})
    assert res.status_code == 200
    cookie = res.headers["set-cookie"]
    assert "radar_session=" in cookie
    assert "HttpOnly" in cookie
    assert "SameSite=none" in cookie
    assert "Secure" in cookie


def test_me_requires_session(tmp_path):
    client = make_client(tmp_path)
    assert client.get("/api/me").status_code == 401
