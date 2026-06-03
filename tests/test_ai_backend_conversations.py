from server.ai_radar_api.conversations import (
    build_ask_labels,
    delete_ask_conversation,
    delete_ask_message,
    get_ask_conversation,
    list_ask_conversations,
    store_ask_conversation,
    update_ask_message,
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
        {"id": record["messages"][0]["id"], "role": "user", "content": "解释这条新闻", "created_at": record["messages"][0]["created_at"]},
        {"id": record["messages"][1]["id"], "role": "assistant", "content": "这条新闻说明 API 更新。", "created_at": record["messages"][1]["created_at"]},
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
    assert history["items"][0]["title"] == "OpenAI 模型更新"
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


def test_update_user_message_truncates_following_thread(tmp_path):
    db_path = tmp_path / "radar.db"
    init_db(db_path)
    first = store_ask_conversation(
        db_path,
        question="第一问",
        answer="第一答",
        title="原始标题",
        scope_payload={"scope": "today"},
        citations=[],
        model="test-model",
        context_source="local",
        context_item_count=1,
    )
    store_ask_conversation(
        db_path,
        conversation_id=first["conversation_id"],
        question="第二问",
        answer="第二答",
        title="不应改标题",
        scope_payload={"scope": "today"},
        citations=[],
        model="test-model",
        context_source="local",
        context_item_count=1,
    )
    first_user_id = get_ask_conversation(db_path, first["conversation_id"])["messages"][0]["id"]

    updated = update_ask_message(db_path, first["conversation_id"], first_user_id, "编辑后的第一问")

    assert updated is not None
    assert updated["title"] == "原始标题"
    assert updated["question"] == "编辑后的第一问"
    assert updated["answer"] == ""
    assert [(m["role"], m["content"]) for m in updated["messages"]] == [("user", "编辑后的第一问")]


def test_delete_message_truncates_from_selected_message(tmp_path):
    db_path = tmp_path / "radar.db"
    init_db(db_path)
    stored = store_ask_conversation(
        db_path,
        question="第一问",
        answer="第一答",
        scope_payload={"scope": "today"},
        citations=[],
        model="test-model",
        context_source="local",
        context_item_count=1,
    )
    store_ask_conversation(
        db_path,
        conversation_id=stored["conversation_id"],
        question="第二问",
        answer="第二答",
        scope_payload={"scope": "today"},
        citations=[],
        model="test-model",
        context_source="local",
        context_item_count=1,
    )
    first_assistant_id = get_ask_conversation(db_path, stored["conversation_id"])["messages"][1]["id"]

    updated = delete_ask_message(db_path, stored["conversation_id"], first_assistant_id)

    assert updated is not None
    assert updated["question"] == "第一问"
    assert updated["answer"] == ""
    assert [(m["role"], m["content"]) for m in updated["messages"]] == [("user", "第一问")]
