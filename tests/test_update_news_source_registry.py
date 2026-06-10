from datetime import datetime, timezone

from scripts import update_news
from scripts.update_news import RawItem


EXPECTED_BUILT_IN_SOURCE_IDS = [
    "official_ai",
    "aibreakfast",
    "followbuilders",
    "techurls",
    "buzzing",
    "iris",
    "bestblogs",
    "tophub",
    "zeli",
    "aihubtoday",
    "aibase",
    "aihot",
    "newsnow",
]


def test_built_in_source_task_registry_has_stable_unique_ids():
    site_ids = [task.site_id for task in update_news.BUILT_IN_SOURCE_TASKS]

    assert site_ids == EXPECTED_BUILT_IN_SOURCE_IDS
    assert len(site_ids) == len(set(site_ids))


def test_collect_all_reads_source_task_registry(monkeypatch):
    now = datetime(2026, 5, 3, 1, 0, tzinfo=timezone.utc)
    session = object()
    calls = []

    def fake_fetch(received_session, received_now):
        calls.append((received_session, received_now))
        return [
            RawItem(
                site_id="fake",
                site_name="Fake",
                source="Fake Source",
                title="Fake AI update",
                url="https://example.com/fake",
                published_at=received_now,
                meta={},
            )
        ]

    monkeypatch.setattr(
        update_news,
        "BUILT_IN_SOURCE_TASKS",
        (update_news.SourceTask("fake", "Fake", fake_fetch),),
    )

    items, statuses = update_news.collect_all(session, now)

    assert calls == [(session, now)]
    assert [item.site_id for item in items] == ["fake"]
    assert statuses == [
        {
            "site_id": "fake",
            "site_name": "Fake",
            "ok": True,
            "item_count": 1,
            "duration_ms": statuses[0]["duration_ms"],
            "error": None,
        }
    ]
