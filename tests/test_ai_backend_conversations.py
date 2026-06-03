from server.ai_radar_api.conversations import (
    build_ask_labels,
    delete_ask_conversation,
    get_ask_conversation,
    list_ask_conversations,
    store_ask_conversation,
)
from server.ai_radar_api.db import connect_db, init_db


def test_build_ask_labels_adds_scope_category_and_intent_labels():
    labels = build_ask_labels(
        {
            "scope": "categories",
            "category": "模型与产品",
            "question": "今天这类型新闻哪个最具有突破性？",
        }
    )

    assert labels == ["分类", "分类: 模型与产品", "推荐"]


def test_store_and_list_ask_conversations(tmp_path):
    db_path = tmp_path / "radar.db"
    init_db(db_path)

    stored = store_ask_conversation(
        db_path,
        question="今天这类型新闻哪个最具有突破性？",
        answer="最值得关注的是新模型发布。",
        scope_payload={"scope": "categories", "category": "模型与产品"},
        citations=[{"title": "New model", "url": "https://example.com/model"}],
        model="test-model",
        context_source="local",
        context_item_count=12,
    )

    history = list_ask_conversations(db_path)

    assert history["items"][0]["conversation_id"] == stored["conversation_id"]
    assert history["items"][0]["title"] == "最值得关注的是新模型发布。"
    assert history["items"][0]["answer_preview"] == "最值得关注的是新模型发布。"
    assert history["items"][0]["labels"] == ["分类", "分类: 模型与产品", "推荐"]
    assert history["items"][0]["context_item_count"] == 12


def test_get_ask_conversation_returns_full_record(tmp_path):
    db_path = tmp_path / "radar.db"
    init_db(db_path)
    stored = store_ask_conversation(
        db_path,
        question="解释这条新闻",
        answer="这条新闻说明 API 更新。",
        scope_payload={"scope": "today"},
        citations=[{"title": "API update", "url": "https://example.com/api"}],
        model="test-model",
        context_source="cache",
        context_item_count=3,
    )

    record = get_ask_conversation(db_path, stored["conversation_id"])

    assert record["question"] == "解释这条新闻"
    assert record["answer"] == "这条新闻说明 API 更新。"
    assert record["messages"] == [
        {"role": "user", "content": "解释这条新闻", "created_at": record["messages"][0]["created_at"]},
        {"role": "assistant", "content": "这条新闻说明 API 更新。", "created_at": record["messages"][1]["created_at"]},
    ]
    assert record["citations"] == [{"title": "API update", "url": "https://example.com/api"}]
    assert record["labels"] == ["今日"]


def test_store_ask_conversation_appends_turn_to_existing_thread(tmp_path):
    db_path = tmp_path / "radar.db"
    init_db(db_path)
    first = store_ask_conversation(
        db_path,
        question="今天 OpenAI 有什么？",
        answer="OpenAI 发布了模型更新。",
        title="OpenAI 模型更新",
        scope_payload={"scope": "today"},
        citations=[],
        model="test-model",
        context_source="local",
        context_item_count=4,
    )

    second = store_ask_conversation(
        db_path,
        conversation_id=first["conversation_id"],
        question="它和 API 有关系吗？",
        answer="有，主要影响 API 使用。",
        title="OpenAI API 影响",
        scope_payload={"scope": "today"},
        citations=[],
        model="test-model",
        context_source="local",
        context_item_count=4,
    )

    history = list_ask_conversations(db_path)
    record = get_ask_conversation(db_path, first["conversation_id"])

    assert second["conversation_id"] == first["conversation_id"]
    assert [item["conversation_id"] for item in history["items"]] == [first["conversation_id"]]
    assert history["items"][0]["title"] == "OpenAI API 影响"
    assert record["question"] == "它和 API 有关系吗？"
    assert record["answer"] == "有，主要影响 API 使用。"
    assert [message["role"] for message in record["messages"]] == ["user", "assistant", "user", "assistant"]
    assert [message["content"] for message in record["messages"]] == [
        "今天 OpenAI 有什么？",
        "OpenAI 发布了模型更新。",
        "它和 API 有关系吗？",
        "有，主要影响 API 使用。",
    ]


def test_delete_ask_conversation_removes_record(tmp_path):
    db_path = tmp_path / "radar.db"
    init_db(db_path)
    stored = store_ask_conversation(
        db_path,
        question="删除这条",
        answer="可以删除。",
        scope_payload={"scope": "today"},
        citations=[],
        model="test-model",
        context_source="local",
        context_item_count=1,
    )

    assert delete_ask_conversation(db_path, stored["conversation_id"]) is True
    assert get_ask_conversation(db_path, stored["conversation_id"]) is None
    assert delete_ask_conversation(db_path, stored["conversation_id"]) is False
    with connect_db(db_path) as conn:
        count = conn.execute("select count(*) from ask_messages where conversation_id = ?", (stored["conversation_id"],)).fetchone()[0]
    assert count == 0
