from server.ai_radar_api.radar_data import build_context, item_identity, merge_item_metadata


def test_item_identity_prefers_stable_url():
    a = item_identity({"title": "A", "url": "https://example.com/a?utm_source=x"})
    b = item_identity({"title": "Different", "url": "https://example.com/a"})
    assert a == b


def test_build_context_limits_and_cites_items():
    items = [
        {"title": "OpenAI ships model", "url": "https://example.com/a", "ai_score": 0.9, "site_name": "OpenAI"},
        {"title": "Low signal", "url": "https://example.com/b", "ai_score": 0.1, "site_name": "Blog"},
    ]
    context = build_context(items, question="OpenAI?", max_items=1)
    assert "[1] OpenAI ships model" in context
    assert "https://example.com/a" in context
    assert "Low signal" not in context


def test_merge_item_metadata_adds_classification_and_verification():
    item = {"title": "A", "url": "https://example.com/a"}
    merged = merge_item_metadata(
        item,
        classification={"top_category": "模型与产品", "sub_category": "模型发布"},
        verification={"authority_score": 88, "status": "verified"},
    )
    assert merged["top_category"] == "模型与产品"
    assert merged["sub_category"] == "模型发布"
    assert merged["authority_score"] == 88
