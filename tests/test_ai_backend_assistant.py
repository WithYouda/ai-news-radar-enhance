import anyio

from server.ai_radar_api.assistant import answer_question, build_ask_messages
from server.ai_radar_api.config import AppConfig


def test_build_ask_messages_avoids_unrelated_link_lists():
    messages = build_ask_messages(
        question="总结今天最重要的两条",
        context="[1] OpenAI ships model | OpenAI | https://example.com/a",
    )
    text = "\n".join(m["content"] for m in messages)
    assert "引用" in text
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


def test_build_ask_messages_embeds_history_in_current_prompt():
    messages = build_ask_messages(
        "我第一个问题是什么？",
        "[1] OpenAI API update | OpenAI | https://example.com/api",
        conversation_messages=[
            {"role": "user", "content": "今天 OpenAI 有什么？"},
            {"role": "assistant", "content": "OpenAI 发布了模型更新。"},
        ],
    )

    current_prompt = messages[-1]["content"]
    assert "历史对话" in current_prompt
    assert "用户：今天 OpenAI 有什么？" in current_prompt
    assert "助手：OpenAI 发布了模型更新。" in current_prompt
    assert "可以使用历史对话回答关于本对话的问题" in "\n".join(message["content"] for message in messages)


def test_build_ask_messages_uses_custom_system_prompt_with_protocol():
    messages = build_ask_messages(
        "总结今天",
        "[1] A | Source | https://a.com",
        system_prompt="你是一个严格的 AI 新闻编辑，只给结论。",
    )

    system_text = messages[0]["content"]
    assert "严格的 AI 新闻编辑" in system_text
    assert "回答必须是 JSON 对象" in system_text
    assert "引用" in system_text


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
    assert result["citations"] == [{"title": "OpenAI ships model", "url": "https://example.com/a", "source": "OpenAI"}]


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

    assert [citation["title"] for citation in result["citations"]] == [
        "OpenAI releases model",
        "OpenAI updates API",
    ]


def test_single_article_context_and_citations_include_original_url_once(tmp_path):
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
    url = "https://example.com/article"
    items = [
        {
            "title": "Single article",
            "url": url,
            "site_name": "Example",
            "article_text": f"The cleaned article body mentions the original page {url} inside copied boilerplate.",
        }
    ]

    class FakeProvider:
        async def chat(self, messages, temperature=0.2):
            prompt = "\n".join(message["content"] for message in messages)
            assert prompt.count(url) == 1
            return '{"title":"单篇总结","answer":"总结正文"}'

    result = anyio.run(answer_question, config, "总结这篇文章", items, FakeProvider())

    assert result["citations"] == [{"title": "Single article", "url": url, "source": "Example"}]
