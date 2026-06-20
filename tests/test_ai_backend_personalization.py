from fastapi.testclient import TestClient

from server.ai_radar_api.config import AppConfig
from server.ai_radar_api.db import connect_db, init_db
from server.ai_radar_api.main import create_app
from server.ai_radar_api.personalization import (
    confirm_profile_draft,
    disable_personalization,
    get_personalization_status,
    reset_personalization,
    save_profile_draft,
    skip_personalization,
)


def _client(tmp_path):
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
    return TestClient(create_app(config), base_url="https://testserver")


def _login(client):
    res = client.post("/api/auth/login", json={"password": "pass"})
    assert res.status_code == 200


def _draft_profile():
    return {
        "positive_interests": [
            {"label": "Agent 产品化", "weight": 0.9, "source": "user"},
            {"label": "开发者工具", "weight": 0.5, "source": "ai"},
        ],
        "negative_interests": [
            {"label": "纯融资快讯", "weight": 0.7, "source": "user"},
        ],
        "source_preferences": [
            {"source": "OpenAI News", "weight": 0.8},
        ],
        "behavior_preferences": {
            "summary_depth": "concise",
            "verification_strictness": "standard",
        },
    }


def test_personalization_status_defaults_to_not_started(tmp_path):
    status = get_personalization_status(tmp_path / "radar.db")

    assert status["state"] == "not_started"
    assert status["enabled"] is False
    assert status["active_profile"] is None
    assert status["draft_profile"] is None
    assert status["capabilities"]["draft_confirmation_required"] is True


def test_personalization_routes_require_login(tmp_path):
    client = _client(tmp_path)

    assert client.get("/api/personalization").status_code == 401
    assert client.post("/api/personalization/interpret", json={"question_id": "attention_goal", "answer_text": "Agent"}).status_code == 401
    assert client.post("/api/personalization/draft", json={"profile": _draft_profile()}).status_code == 401
    assert client.post("/api/personalization/confirm").status_code == 401
    assert client.post("/api/personalization/skip").status_code == 401
    assert client.post("/api/personalization/reset").status_code == 401
    assert client.post("/api/personalization/disable").status_code == 401


def test_save_profile_draft_does_not_mutate_active_profile(tmp_path):
    db_path = tmp_path / "radar.db"

    status = save_profile_draft(
        db_path,
        _draft_profile(),
        evidence={"source": "workbench", "answers": ["更关心可落地工具"]},
    )

    assert status["state"] == "draft_pending"
    assert status["enabled"] is False
    assert status["active_profile"] is None
    assert status["draft_profile"]["positive_interests"][0]["label"] == "Agent 产品化"
    assert status["draft_profile"]["evidence"]["source"] == "workbench"


def test_confirming_draft_promotes_it_to_active_profile(tmp_path):
    client = _client(tmp_path)
    _login(client)

    draft_res = client.post(
        "/api/personalization/draft",
        json={"profile": _draft_profile(), "evidence": {"source": "workbench"}},
    )
    assert draft_res.status_code == 200

    confirmed = client.post("/api/personalization/confirm")

    assert confirmed.status_code == 200
    payload = confirmed.json()
    assert payload["state"] == "confirmed"
    assert payload["enabled"] is True
    assert payload["draft_profile"] is None
    assert payload["active_profile"]["positive_interests"][0]["label"] == "Agent 产品化"
    assert payload["active_profile"]["confirmed_at"]
    assert payload["active_profile"]["version"] == 1


def test_skip_is_reversible_and_does_not_create_profile(tmp_path):
    client = _client(tmp_path)
    _login(client)

    skipped = client.post("/api/personalization/skip")
    reopened = client.post(
        "/api/personalization/draft",
        json={"profile": _draft_profile(), "evidence": {"source": "settings"}},
    )

    assert skipped.status_code == 200
    assert skipped.json()["state"] == "skipped"
    assert skipped.json()["active_profile"] is None
    assert reopened.status_code == 200
    assert reopened.json()["state"] == "draft_pending"
    assert reopened.json()["draft_profile"]["evidence"]["source"] == "settings"


def test_disable_keeps_profile_but_turns_personalization_off(tmp_path):
    client = _client(tmp_path)
    _login(client)
    client.post("/api/personalization/draft", json={"profile": _draft_profile()})
    client.post("/api/personalization/confirm")

    disabled = client.post("/api/personalization/disable")

    assert disabled.status_code == 200
    assert disabled.json()["state"] == "confirmed"
    assert disabled.json()["enabled"] is False
    assert disabled.json()["active_profile"]["positive_interests"][0]["label"] == "Agent 产品化"


def test_skip_after_confirm_preserves_active_profile_but_disables_it(tmp_path):
    db_path = tmp_path / "radar.db"
    save_profile_draft(db_path, _draft_profile(), evidence={"source": "workbench"})

    confirm_profile_draft(db_path)

    skipped = skip_personalization(db_path)

    assert skipped["state"] == "skipped"
    assert skipped["enabled"] is False
    assert skipped["active_profile"]["positive_interests"][0]["label"] == "Agent 产品化"
    assert skipped["draft_profile"] is None


def test_disable_empty_state_returns_not_started(tmp_path):
    status = disable_personalization(tmp_path / "radar.db")

    assert status["state"] == "not_started"
    assert status["enabled"] is False
    assert status["active_profile"] is None


def test_reset_clears_active_and_draft_profiles(tmp_path):
    db_path = tmp_path / "radar.db"
    save_profile_draft(db_path, _draft_profile(), evidence={"source": "workbench"})

    status = reset_personalization(db_path)

    assert status["state"] == "not_started"
    assert status["enabled"] is False
    assert status["active_profile"] is None
    assert status["draft_profile"] is None


def test_save_draft_rejects_non_object_evidence(tmp_path):
    client = _client(tmp_path)
    _login(client)

    res = client.post(
        "/api/personalization/draft",
        json={"profile": _draft_profile(), "evidence": ["not", "object"]},
    )

    assert res.status_code == 400
    assert "evidence" in res.text
    assert client.get("/api/personalization").json()["state"] == "not_started"


def test_rejects_invalid_profile_shape_without_persisting(tmp_path):
    client = _client(tmp_path)
    _login(client)

    res = client.post(
        "/api/personalization/draft",
        json={
            "profile": {
                "positive_interests": [{"label": "", "weight": 2}],
                "negative_interests": "nope",
            }
        },
    )

    assert res.status_code == 400
    assert "profile" in res.text
    assert client.get("/api/personalization").json()["state"] == "not_started"


def test_confirm_without_draft_is_rejected(tmp_path):
    client = _client(tmp_path)
    _login(client)

    res = client.post("/api/personalization/confirm")

    assert res.status_code == 400
    assert "draft" in res.text.lower()


def test_init_db_migrates_existing_database_with_personalization_table(tmp_path):
    db_path = tmp_path / "radar.db"
    with connect_db(db_path) as conn:
        conn.execute(
            """
            create table settings (
              key text primary key,
              value_json text not null,
              updated_at text not null
            )
            """
        )

    init_db(db_path)

    status = get_personalization_status(db_path)
    assert status["state"] == "not_started"


def test_interpret_profile_answer_calls_ai_with_history_and_returns_structured_labels(tmp_path, monkeypatch):
    client = _client(tmp_path)
    _login(client)
    calls = []

    async def fake_chat(self, messages, temperature=0.2):
        calls.append({"messages": messages, "temperature": temperature})
        return """
        {
          "labels": ["企业知识库落地", "Agent 工作流", "企业知识库落地"],
          "note": "更关心能落地的企业内部知识库和工作流。",
          "follow_up": "你更想看产品实践还是工程方案？"
        }
        """

    monkeypatch.setattr("server.ai_radar_api.provider.AIProvider.chat", fake_chat)

    res = client.post(
        "/api/personalization/interpret",
        json={
            "question_id": "ai_domains",
            "stage": "calibration",
            "answer_text": "我更关心企业内部知识库真正落地",
            "selected_choices": ["Agent"],
            "history": [
                {
                    "question_id": "attention_goal",
                    "question_title": "先选你的 AI 新闻重心。",
                    "choices": ["产品与工具"],
                    "text": "不要融资快讯",
                    "ai_labels": ["产品与工具"],
                }
            ],
        },
    )

    assert res.status_code == 200
    payload = res.json()
    assert payload["labels"] == ["企业知识库落地", "Agent 工作流"]
    assert payload["note"] == "更关心能落地的企业内部知识库和工作流。"
    assert payload["follow_up"] == "你更想看产品实践还是工程方案？"
    assert payload["source"] == "ai"
    assert calls
    prompt = "\n".join(message["content"] for message in calls[0]["messages"])
    assert "attention_goal" in prompt
    assert "不要融资快讯" in prompt
    assert "我更关心企业内部知识库真正落地" in prompt
    assert "只返回 JSON" in prompt


def test_interpret_profile_answer_rejects_empty_signal_without_calling_ai(tmp_path, monkeypatch):
    client = _client(tmp_path)
    _login(client)
    called = False

    async def fake_chat(self, messages, temperature=0.2):
        nonlocal called
        called = True
        return "{}"

    monkeypatch.setattr("server.ai_radar_api.provider.AIProvider.chat", fake_chat)

    res = client.post(
        "/api/personalization/interpret",
        json={"question_id": "attention_goal", "stage": "calibration", "answer_text": " ", "selected_choices": []},
    )

    assert res.status_code == 400
    assert called is False


def test_interpret_profile_answer_reports_provider_unavailable(tmp_path, monkeypatch):
    client = _client(tmp_path)
    _login(client)

    async def fake_chat(self, messages, temperature=0.2):
        from server.ai_radar_api.provider import AIProviderUnavailable

        raise AIProviderUnavailable("model unavailable")

    monkeypatch.setattr("server.ai_radar_api.provider.AIProvider.chat", fake_chat)

    res = client.post(
        "/api/personalization/interpret",
        json={
            "question_id": "attention_goal",
            "stage": "calibration",
            "answer_text": "企业内部知识库落地",
            "selected_choices": [],
            "history": [],
        },
    )

    assert res.status_code == 503
    assert "model unavailable" in res.text
