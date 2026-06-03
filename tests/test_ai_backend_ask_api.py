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

    def fake_load_latest_items_with_source(config, mode="ai"):
        return (
            [
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
            ],
            "local",
        )

    async def fake_answer_question(config, question, items, system_prompt=None):
        captured["items"] = items
        return {"answer": "ok", "citations": [], "model": config.ai_model}

    monkeypatch.setattr("server.ai_radar_api.main.load_latest_items_with_source", fake_load_latest_items_with_source)
    monkeypatch.setattr("server.ai_radar_api.main.answer_question", fake_answer_question)

    client = make_client(tmp_path)
    login(client)
    res = client.post("/api/ask", json={"question": "哪条最突破？", "scope": "categories", "category": "模型与产品"})

    assert res.status_code == 200
    assert [item["url"] for item in captured["items"]] == ["https://example.com/model"]
    assert res.json()["context_item_count"] == 1
    assert res.json()["context_source"] == "local"


def test_ask_persists_history_with_labels(monkeypatch, tmp_path):
    def fake_load_latest_items_with_source(config, mode="ai"):
        return (
            [
                {
                    "title": "New model release",
                    "url": "https://example.com/model",
                    "ai_label": "model_release",
                    "ai_score": 0.9,
                },
            ],
            "local",
        )

    async def fake_answer_question(config, question, items, system_prompt=None):
        return {
            "answer": "最值得关注的是 New model release。",
            "title": "模型发布重点",
            "citations": [{"title": "New model release", "url": "https://example.com/model"}],
            "model": config.ai_model,
        }

    monkeypatch.setattr("server.ai_radar_api.main.load_latest_items_with_source", fake_load_latest_items_with_source)
    monkeypatch.setattr("server.ai_radar_api.main.answer_question", fake_answer_question)

    client = make_client(tmp_path)
    login(client)

    ask_res = client.post("/api/ask", json={"question": "今天哪个最突破？", "scope": "categories", "category": "模型与产品"})

    assert ask_res.status_code == 200
    ask_payload = ask_res.json()
    assert ask_payload["history_saved"] is True
    assert ask_payload["conversation_id"]

    history_res = client.get("/api/ask/history")
    assert history_res.status_code == 200
    history_item = history_res.json()["items"][0]
    assert history_item["conversation_id"] == ask_payload["conversation_id"]
    assert history_item["title"] == "模型发布重点"
    assert history_item["question"] == "今天哪个最突破？"
    assert history_item["labels"] == ["分类", "分类: 模型与产品", "推荐"]
    assert history_item["answer_preview"] == "最值得关注的是 New model release。"

    detail_res = client.get(f"/api/ask/history/{ask_payload['conversation_id']}")
    assert detail_res.status_code == 200
    assert detail_res.json()["answer"] == "最值得关注的是 New model release。"
    assert [message["role"] for message in detail_res.json()["messages"]] == ["user", "assistant"]

    delete_res = client.delete(f"/api/ask/history/{ask_payload['conversation_id']}")
    assert delete_res.status_code == 200
    assert delete_res.json() == {"ok": True}
    assert client.get("/api/ask/history").json()["items"] == []


def test_ask_appends_existing_conversation_and_sends_history_to_ai(monkeypatch, tmp_path):
    captured = []

    def fake_load_latest_items_with_source(config, mode="ai"):
        return ([{"title": "OpenAI API update", "url": "https://example.com/api", "ai_score": 0.9}], "local")

    async def fake_answer_question(config, question, items, conversation_messages=None, system_prompt=None):
        captured.append({"question": question, "messages": conversation_messages or []})
        return {
            "answer": f"回答：{question}",
            "title": "OpenAI API 追问",
            "citations": [],
            "model": config.ai_model,
        }

    monkeypatch.setattr("server.ai_radar_api.main.load_latest_items_with_source", fake_load_latest_items_with_source)
    monkeypatch.setattr("server.ai_radar_api.main.answer_question", fake_answer_question)

    client = make_client(tmp_path)
    login(client)

    first_res = client.post("/api/ask", json={"question": "今天 OpenAI 有什么？", "scope": "today"})
    conversation_id = first_res.json()["conversation_id"]
    second_res = client.post(
        "/api/ask",
        json={"question": "它和 API 有关系吗？", "scope": "today", "conversation_id": conversation_id},
    )

    assert second_res.status_code == 200
    assert second_res.json()["conversation_id"] == conversation_id
    assert captured[1]["messages"] == [
        {"role": "user", "content": "今天 OpenAI 有什么？"},
        {"role": "assistant", "content": "回答：今天 OpenAI 有什么？"},
    ]
    history = client.get("/api/ask/history").json()["items"]
    assert len(history) == 1
    detail = client.get(f"/api/ask/history/{conversation_id}").json()
    assert [message["content"] for message in detail["messages"]] == [
        "今天 OpenAI 有什么？",
        "回答：今天 OpenAI 有什么？",
        "它和 API 有关系吗？",
        "回答：它和 API 有关系吗？",
    ]
