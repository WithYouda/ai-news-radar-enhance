import json
import subprocess
import sys
from pathlib import Path

from scripts import audit_ai_relevance


def test_audit_report_includes_score_buckets(tmp_path):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    latest = {
        "generated_at": "2026-06-19T00:00:00Z",
        "topic_filter": "ai_relevance_scoring_v0_5",
        "ai_relevance_threshold": 0.65,
        "items_ai": [
            {"title": "OpenAI release", "ai_score": 0.91, "ai_label": "model_release", "site_id": "official_ai"}
        ],
    }
    latest_all = {
        "items_all_raw": [
            {
                "title": "OpenAI release",
                "ai_score": 0.91,
                "ai_label": "model_release",
                "ai_is_related": True,
                "site_id": "official_ai",
                "source": "OpenAI",
            },
            {
                "title": "VLA robot paper",
                "ai_relevance_score": 0.61,
                "ai_label": "robotics",
                "ai_is_related": False,
                "site_id": "opmlrss",
                "source": "arxiv",
            },
            {
                "title": "Retail update",
                "ai_relevance_score": 0.11,
                "ai_label": "not_ai",
                "ai_is_related": False,
                "site_id": "buzzing",
                "source": "retail",
            },
        ]
    }
    (data_dir / "latest-24h.json").write_text(json.dumps(latest), encoding="utf-8")
    (data_dir / "latest-24h-all.json").write_text(json.dumps(latest_all), encoding="utf-8")
    output = tmp_path / "audit.md"

    assert audit_ai_relevance.main(["--data-dir", str(data_dir), "--output", str(output)]) == 0

    text = output.read_text(encoding="utf-8")
    assert "## Score buckets" in text
    assert "| 0.90-1.00 | 1 |" in text
    assert "| 0.60-0.69 | 1 |" in text
    assert "review-band items (0.45 <= score < threshold): `1`" in text


def test_audit_script_runs_when_invoked_by_path(tmp_path):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    (data_dir / "latest-24h.json").write_text(
        json.dumps(
            {
                "generated_at": "2026-06-19T00:00:00Z",
                "topic_filter": "ai_relevance_scoring_v0_5",
                "ai_relevance_threshold": 0.65,
                "items_ai": [],
            }
        ),
        encoding="utf-8",
    )
    (data_dir / "latest-24h-all.json").write_text(json.dumps({"items_all_raw": []}), encoding="utf-8")
    output = tmp_path / "audit.md"

    result = subprocess.run(
        [
            sys.executable,
            "scripts/audit_ai_relevance.py",
            "--data-dir",
            str(data_dir),
            "--output",
            str(output),
        ],
        check=False,
        cwd=Path(__file__).resolve().parents[1],
        text=True,
        capture_output=True,
    )

    assert result.returncode == 0, result.stderr
    assert output.exists()
