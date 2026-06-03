import json

import httpx

from server.ai_radar_api.config import AppConfig
from server.ai_radar_api.radar_data import build_context, item_identity, load_latest_items_with_source, merge_item_metadata


def _config(tmp_path, data_dir=None, cache_dir=None) -> AppConfig:
    return AppConfig(
        public_base_url="https://withyouda.github.io/ai-news-radar-enhance",
        allowed_origins=["https://withyouda.github.io"],
        admin_password="pass",
        session_secret="session-secret",
        db_path=tmp_path / "radar.db",
        ai_base_url="https://api.example.com/v1",
        ai_api_key="sk-test",
        ai_model="test-model",
        data_dir=data_dir or tmp_path / "data",
        data_cache_dir=cache_dir or tmp_path / "cache",
    )


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


def test_build_context_includes_clean_article_excerpt_when_available():
    items = [
        {
            "title": "OpenAI ships model",
            "url": "https://example.com/a",
            "ai_score": 0.9,
            "site_name": "OpenAI",
            "article_text": "Clean article body with details that were extracted from the original page.",
        },
    ]

    context = build_context(items, question="这篇文章说了什么？", max_items=1)

    assert "正文摘录[1]" in context
    assert "Clean article body with details" in context


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


def test_load_latest_items_prefers_local_data_without_remote_fetch(monkeypatch, tmp_path):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    (data_dir / "latest-24h.json").write_text(
        json.dumps({"items": [{"title": "Local first model news", "url": "https://example.com/local-first"}]}),
        encoding="utf-8",
    )
    config = _config(tmp_path, data_dir=data_dir)
    remote_calls = 0

    def record_remote_fetch(*args, **kwargs):
        nonlocal remote_calls
        remote_calls += 1
        raise httpx.ConnectError("remote should not be fetched when local data exists")

    monkeypatch.setattr("server.ai_radar_api.radar_data.httpx.get", record_remote_fetch)

    items, source = load_latest_items_with_source(config)

    assert remote_calls == 0
    assert source == "local"
    assert items[0]["title"] == "Local first model news"


def test_load_latest_items_can_prefer_remote_public_data_over_stale_local(monkeypatch, tmp_path):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    (data_dir / "latest-24h.json").write_text(
        json.dumps({"items": [{"title": "Stale local news", "url": "https://example.com/local"}]}),
        encoding="utf-8",
    )
    config = AppConfig(
        **{
            **_config(tmp_path, data_dir=data_dir).__dict__,
            "prefer_remote_data": True,
        }
    )

    class Response:
        def raise_for_status(self):
            return None

        def json(self):
            return {"items": [{"title": "Current public news", "url": "https://example.com/remote"}]}

    monkeypatch.setattr("server.ai_radar_api.radar_data.httpx.get", lambda *args, **kwargs: Response())

    items, source = load_latest_items_with_source(config)

    assert source == "remote"
    assert items[0]["title"] == "Current public news"


def test_load_latest_items_uses_cache_before_remote(monkeypatch, tmp_path):
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()
    (cache_dir / "latest-24h.json").write_text(
        json.dumps({"items": [{"title": "Cached model news", "url": "https://example.com/cache"}]}),
        encoding="utf-8",
    )
    config = _config(tmp_path, cache_dir=cache_dir)

    remote_calls = 0

    def record_remote_fetch(*args, **kwargs):
        nonlocal remote_calls
        remote_calls += 1
        raise httpx.ConnectError("remote should not be fetched when cache data exists")

    monkeypatch.setattr("server.ai_radar_api.radar_data.httpx.get", record_remote_fetch)

    items, source = load_latest_items_with_source(config)

    assert remote_calls == 0
    assert source == "cache"
    assert items[0]["title"] == "Cached model news"


def test_load_latest_items_writes_remote_payload_to_cache(monkeypatch, tmp_path):
    config = _config(tmp_path)

    class Response:
        def raise_for_status(self):
            return None

        def json(self):
            return {"items": [{"title": "Remote model news", "url": "https://example.com/remote"}]}

    monkeypatch.setattr("server.ai_radar_api.radar_data.httpx.get", lambda *args, **kwargs: Response())

    items, source = load_latest_items_with_source(config)

    assert source == "remote"
    assert items[0]["title"] == "Remote model news"
    cached_payload = json.loads((config.data_cache_dir / "latest-24h.json").read_text(encoding="utf-8"))
    assert cached_payload["items"][0]["title"] == "Remote model news"
