from server.ai_radar_api.assistant import build_ask_messages


def test_build_ask_messages_requires_citations():
    messages = build_ask_messages(
        question="总结今天最重要的两条",
        context="[1] OpenAI ships model | OpenAI | https://example.com/a",
    )
    text = "\n".join(m["content"] for m in messages)
    assert "引用" in text
    assert "不知道" in text or "不足" in text
    assert "https://example.com/a" in text


def test_build_ask_messages_keeps_user_question():
    messages = build_ask_messages("这条有一手来源吗？", "[1] A | Source | https://a.com")
    assert messages[-1]["role"] == "user"
    assert "这条有一手来源吗" in messages[-1]["content"]
