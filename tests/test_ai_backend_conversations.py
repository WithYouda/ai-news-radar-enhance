from server.ai_radar_api.conversations import (
    build_ask_labels,
    get_ask_conversation,
    list_ask_conversations,
    store_ask_conversation,
)
from server.ai_radar_api.db import init_db


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
    assert record["citations"] == [{"title": "API update", "url": "https://example.com/api"}]
    assert record["labels"] == ["今日"]
