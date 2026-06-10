from datetime import datetime, timezone
from types import SimpleNamespace

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


def test_fetch_iris_fetches_subfeeds_with_timeout_before_parsing(monkeypatch):
    now = datetime(2026, 6, 10, 12, 0, tzinfo=timezone.utc)
    root_url = "https://iris.findtruman.io/web/info_flow"
    feed_url = "https://feeds.example.com/ai.xml"
    feed_bytes = b"<rss><channel><title>Parsed Feed</title></channel></rss>"
    calls = []
    parse_inputs = []

    class FakeResponse:
        def __init__(self, text="", content=b""):
            self.text = text
            self.content = content

        def raise_for_status(self):
            return None

    class FakeSession:
        def get(self, url, timeout):
            calls.append((url, timeout))
            if url == root_url:
                return FakeResponse(
                    text=f"const feeds = [{{name: 'Iris AI', url: '{feed_url}'}}];",
                )
            if url == feed_url:
                return FakeResponse(content=feed_bytes)
            raise AssertionError(f"unexpected URL: {url}")

    class FakeFeedparser:
        def parse(self, payload):
            parse_inputs.append(payload)
            return SimpleNamespace(
                feed={"title": "Parsed Feed"},
                entries=[
                    {
                        "title": "Iris AI launch",
                        "link": "https://example.com/iris-ai-launch",
                        "published": "Wed, 10 Jun 2026 11:00:00 GMT",
                    }
                ],
            )

    monkeypatch.setattr(update_news, "feedparser", FakeFeedparser())

    items = update_news.fetch_iris(FakeSession(), now)

    assert calls == [(root_url, 30), (feed_url, 30)]
    assert parse_inputs == [feed_bytes]
    assert len(items) == 1
    assert items[0].source == "Iris AI"
    assert items[0].title == "Iris AI launch"


def test_fetch_iris_skips_timed_out_subfeed_and_continues(monkeypatch):
    now = datetime(2026, 6, 10, 12, 0, tzinfo=timezone.utc)
    root_url = "https://iris.findtruman.io/web/info_flow"
    slow_feed_url = "https://feeds.example.com/slow.xml"
    ok_feed_url = "https://feeds.example.com/ok.xml"
    ok_feed_bytes = b"<rss><channel><title>OK Feed</title></channel></rss>"
    calls = []
    parse_inputs = []

    class FakeResponse:
        def __init__(self, text="", content=b""):
            self.text = text
            self.content = content

        def raise_for_status(self):
            return None

    class FakeSession:
        def get(self, url, timeout):
            calls.append((url, timeout))
            if url == root_url:
                return FakeResponse(
                    text=(
                        "const feeds = ["
                        f"{{name: 'Slow Feed', url: '{slow_feed_url}'}},"
                        f"{{name: 'OK Feed', url: '{ok_feed_url}'}}"
                        "];"
                    ),
                )
            if url == slow_feed_url:
                raise TimeoutError("subfeed timed out")
            if url == ok_feed_url:
                return FakeResponse(content=ok_feed_bytes)
            raise AssertionError(f"unexpected URL: {url}")

    class FakeFeedparser:
        def parse(self, payload):
            parse_inputs.append(payload)
            return SimpleNamespace(
                feed={"title": "OK Feed"},
                entries=[
                    {
                        "title": "Recovered Iris item",
                        "link": "https://example.com/recovered",
                        "published": "Wed, 10 Jun 2026 11:30:00 GMT",
                    }
                ],
            )

    monkeypatch.setattr(update_news, "feedparser", FakeFeedparser())

    items = update_news.fetch_iris(FakeSession(), now)

    assert calls == [(root_url, 30), (slow_feed_url, 30), (ok_feed_url, 30)]
    assert parse_inputs == [ok_feed_bytes]
    assert len(items) == 1
    assert items[0].source == "OK Feed"
    assert items[0].title == "Recovered Iris item"
