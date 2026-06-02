from fastapi.testclient import TestClient

from server.ai_radar_api.config import AppConfig
from server.ai_radar_api.db import connect_db
from server.ai_radar_api.main import create_app
from server.ai_radar_api.radar_data import item_identity


def make_config(tmp_path):
    return AppConfig(
        public_base_url="https://withyouda.github.io/ai-news-radar-enhance",
        allowed_origins=["https://withyouda.github.io"],
        admin_password="pass",
        session_secret="test-session-secret",
        db_path=tmp_path / "radar.db",
        ai_base_url="https://api.example.com/v1",
        ai_api_key="sk-test",
        ai_model="test-model",
    )


def make_client(tmp_path):
    config = make_config(tmp_path)
    return TestClient(create_app(config), base_url="https://testserver")


def login(client):
    res = client.post("/api/auth/login", json={"password": "pass"})
    assert res.status_code == 200


def test_deep_verify_uses_latest_item_when_body_is_empty(monkeypatch, tmp_path):
    item = {"title": "OpenAI ships model", "url": "https://openai.com/news/a", "ai_score": 0.9}
    item_id = item_identity(item)
    calls = []

    def fake_load_latest_items(config, mode="ai"):
        return [item]

    def fake_fetch_and_verify(item_arg, timeout_seconds=12, deep=False):
        calls.append((item_arg, deep))
        return {
            "status": "verified",
            "authority_score": 90,
            "authority_reason": "test",
            "evidence_links": [item_arg["url"]],
            "deep_verified": deep,
            "model": "rules-v1",
            "verified_at": "2026-06-02T00:00:00+00:00",
        }

    monkeypatch.setattr("server.ai_radar_api.main.load_latest_items", fake_load_latest_items)
    monkeypatch.setattr("server.ai_radar_api.main.fetch_and_verify", fake_fetch_and_verify)

    client = make_client(tmp_path)
    login(client)
    res = client.post(f"/api/verification/{item_id}/deep-verify", json={})

    assert res.status_code == 200
    assert calls[0][0]["url"] == "https://openai.com/news/a"
    assert calls[0][1] is True


def test_verify_uses_classified_url_when_existing_verification_url_is_empty(monkeypatch, tmp_path):
    config = make_config(tmp_path)
    client = TestClient(create_app(config), base_url="https://testserver")
    item_id = "known-item"
    calls = []

    with connect_db(config.db_path) as conn:
        conn.execute(
            """
            insert into verification_results(
              item_id, url, status, authority_score, authority_reason,
              evidence_json, deep_verified, model, verified_at
            )
            values (?, '', 'failed', 0, 'empty url', '[]', 0, 'rules-v1', '2026-06-02T00:00:00+00:00')
            """,
            (item_id,),
        )
        conn.execute(
            """
            insert into item_classifications(
              item_id, url, title_hash, top_category, sub_category, confidence,
              reason, taxonomy_version, model, manual_override_json, classified_at
            )
            values (?, 'https://example.com/source', 'hash', '模型与产品', '模型发布', 0.9,
                    'test', 'default-v1', 'rules-v1', 'null', '2026-06-02T00:00:00+00:00')
            """,
            (item_id,),
        )

    monkeypatch.setattr("server.ai_radar_api.main.load_latest_items", lambda config, mode="ai": [])

    def fake_fetch_and_verify(item_arg, timeout_seconds=12, deep=False):
        calls.append(item_arg)
        return {
            "status": "verified",
            "authority_score": 80,
            "authority_reason": "test",
            "evidence_links": [item_arg["url"]],
            "deep_verified": deep,
            "model": "rules-v1",
            "verified_at": "2026-06-02T00:00:01+00:00",
        }

    monkeypatch.setattr("server.ai_radar_api.main.fetch_and_verify", fake_fetch_and_verify)

    login(client)
    res = client.post(f"/api/verification/{item_id}/verify", json={})

    assert res.status_code == 200
    assert calls[0]["url"] == "https://example.com/source"
