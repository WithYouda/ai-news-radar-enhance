import json
from datetime import datetime, timezone

from scripts import update_news
from scripts.update_news import NEWS_PAYLOAD_SCHEMA_VERSION, RawItem


def test_main_writes_schema_version_to_public_json_outputs(monkeypatch, tmp_path):
    now = datetime(2026, 5, 3, 1, 0, tzinfo=timezone.utc)
    output_dir = tmp_path / "data"

    monkeypatch.setattr(update_news, "utc_now", lambda: now)
    monkeypatch.setattr(update_news, "create_session", lambda: object())
    monkeypatch.setattr(
        update_news,
        "collect_all",
        lambda session, now: (
            [
                RawItem(
                    site_id="official_ai",
                    site_name="Official AI Updates",
                    source="OpenAI News",
                    title="OpenAI releases a new AI model",
                    url="https://example.com/openai-model",
                    published_at=now,
                    meta={},
                )
            ],
            [
                {
                    "site_id": "official_ai",
                    "site_name": "Official AI Updates",
                    "ok": True,
                    "item_count": 1,
                    "duration_ms": 0,
                    "error": None,
                }
            ],
        ),
    )
    monkeypatch.setattr(
        update_news,
        "maybe_fetch_agentmail_digest",
        lambda session, generated_at, after, window_hours: (
            None,
            {
                "enabled": False,
                "ok": None,
                "item_count": 0,
                "privacy": "metadata_only_no_body",
                "published_by_default": False,
            },
        ),
    )
    monkeypatch.setattr(update_news, "maybe_fetch_x_api_updates", lambda session, now: ([], {"enabled": False}))
    monkeypatch.setattr(
        update_news,
        "add_bilingual_fields",
        lambda latest_items, latest_items_all, session, title_cache, max_new_translations: (
            latest_items,
            latest_items_all,
            title_cache,
        ),
    )
    monkeypatch.setattr(
        update_news,
        "fetch_waytoagi_recent_7d",
        lambda session, now, root_url: {
            "generated_at": update_news.iso(now),
            "timezone": "Asia/Shanghai",
            "root_url": root_url,
            "history_url": None,
            "window_days": 7,
            "count_7d": 0,
            "updates_7d": [],
        },
    )
    monkeypatch.setattr("sys.argv", ["update_news.py", "--output-dir", str(output_dir)])

    assert update_news.main() == 0

    for filename in [
        "latest-24h.json",
        "latest-24h-all.json",
        "archive.json",
        "source-status.json",
        "waytoagi-7d.json",
    ]:
        payload = json.loads((output_dir / filename).read_text(encoding="utf-8"))
        assert payload["schema_version"] == NEWS_PAYLOAD_SCHEMA_VERSION
