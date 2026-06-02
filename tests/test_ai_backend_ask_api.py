from fastapi.testclient import TestClient

from server.ai_radar_api.config import AppConfig
from server.ai_radar_api.main import create_app


def make_client(tmp_path):
    config = AppConfig(
        public_base_url="https://withyouda.github.io/ai-news-radar-enhance",
        allowed_origins=["https://withyouda.github.io"],
        admin_password="pass",
        session_secret="test-session-secret",
        db_path=tmp_path / "radar.db",
        ai_base_url="https://api.example.com/v1",
        ai_api_key="sk-test",
        ai_model="test-model",
    )
    return TestClient(create_app(config), base_url="https://testserver")


def login(client):
    res = client.post("/api/auth/login", json={"password": "pass"})
    assert res.status_code == 200


def test_ask_category_scope_matches_legacy_ai_labels(monkeypatch, tmp_path):
    captured = {}

    def fake_load_latest_items(config, mode="ai"):
        return [
            {
                "title": "New model release",
                "url": "https://example.com/model",
                "ai_label": "model_release",
                "ai_score": 0.9,
            },
            {
                "title": "Coding tool update",
                "url": "https://example.com/tool",
                "ai_label": "developer_tool",
                "ai_score": 0.8,
            },
        ]

    async def fake_answer_question(config, question, items):
        captured["items"] = items
        return {"answer": "ok", "citations": [], "model": config.ai_model}

    monkeypatch.setattr("server.ai_radar_api.main.load_latest_items", fake_load_latest_items)
    monkeypatch.setattr("server.ai_radar_api.main.answer_question", fake_answer_question)

    client = make_client(tmp_path)
    login(client)
    res = client.post("/api/ask", json={"question": "哪条最突破？", "scope": "categories", "category": "模型与产品"})

    assert res.status_code == 200
    assert [item["url"] for item in captured["items"]] == ["https://example.com/model"]
