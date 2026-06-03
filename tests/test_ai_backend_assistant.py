import anyio

from server.ai_radar_api.assistant import answer_question, build_ask_messages
from server.ai_radar_api.config import AppConfig


def test_build_ask_messages_avoids_unrelated_link_lists():
    messages = build_ask_messages(
        question="总结今天最重要的两条",
        context="[1] OpenAI ships model | OpenAI | https://example.com/a",
    )
    text = "\n".join(m["content"] for m in messages)
    assert "不要在回答末尾追加链接列表" in text
    assert "无关链接" in text
    assert "不知道" in text or "不足" in text
    assert "https://example.com/a" in text


def test_build_ask_messages_keeps_user_question():
    messages = build_ask_messages("这条有一手来源吗？", "[1] A | Source | https://a.com")
    assert messages[-1]["role"] == "user"
    assert "这条有一手来源吗" in messages[-1]["content"]


def test_build_ask_messages_includes_previous_thread_turns():
    messages = build_ask_messages(
        "它和 API 有关系吗？",
        "[1] OpenAI API update | OpenAI | https://example.com/api",
        conversation_messages=[
            {"role": "user", "content": "今天 OpenAI 有什么？"},
            {"role": "assistant", "content": "OpenAI 发布了模型更新。"},
        ],
    )

    assert messages[1:3] == [
        {"role": "user", "content": "今天 OpenAI 有什么？"},
        {"role": "assistant", "content": "OpenAI 发布了模型更新。"},
    ]
    assert "它和 API 有关系吗" in messages[-1]["content"]


def test_answer_question_does_not_return_final_link_recommendations(tmp_path):
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
    items = [
        {"title": "Low signal", "url": "https://example.com/b", "ai_score": 0.1, "site_name": "Blog"},
        {"title": "OpenAI ships model", "url": "https://example.com/a", "ai_score": 0.9, "site_name": "OpenAI"},
    ]

    class FakeProvider:
        async def chat(self, messages, temperature=0.2):
            return '{"title":"OpenAI 重点","answer":"answer"}'

    result = anyio.run(answer_question, config, "OpenAI?", items, FakeProvider())

    assert result["answer"] == "answer"
    assert result["title"] == "OpenAI 重点"
    assert result["citations"] == []


def test_answer_question_falls_back_when_provider_returns_plain_markdown(tmp_path):
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

    class FakeProvider:
        async def chat(self, messages, temperature=0.2):
            return "## 重点\n\n- API 更新"

    result = anyio.run(answer_question, config, "OpenAI?", [], FakeProvider())

    assert result["answer"] == "## 重点\n\n- API 更新"
    assert result["title"] == "重点 - API 更新"


def test_answer_question_filters_citations_to_question_matches(tmp_path):
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
    items = [
        {"title": "OpenAI releases model", "url": "https://example.com/openai-model", "site_name": "OpenAI"},
        {"title": "OpenAI updates API", "url": "https://example.com/openai-api", "site_name": "OpenAI"},
        {"title": "Anthropic launches feature", "url": "https://example.com/anthropic", "site_name": "Anthropic"},
        {"title": "Google releases tool", "url": "https://example.com/google", "site_name": "Google"},
    ]

    class FakeProvider:
        async def chat(self, messages, temperature=0.2):
            joined = "\n".join(message["content"] for message in messages)
            assert "OpenAI releases model" in joined
            assert "OpenAI updates API" in joined
            assert "Anthropic launches feature" not in joined
            return "answer"

    result = anyio.run(answer_question, config, "今天 OpenAI 有什么新消息？", items, FakeProvider())

    assert result["citations"] == []
