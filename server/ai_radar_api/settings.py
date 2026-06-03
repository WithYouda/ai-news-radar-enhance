from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from .db import connect_db
from .assistant import DEFAULT_ASK_SYSTEM_PROMPT


SETTINGS_KEY = "app_settings"
DEFAULT_SETTINGS = {
    "deep_verification_enabled": False,
    "deep_verification_scope": "bole_picks_and_topic_top_n",
    "deep_verification_top_n": 3,
    "mobile_default_view": "today",
    "ask_system_prompt": DEFAULT_ASK_SYSTEM_PROMPT,
}
VALID_DEEP_VERIFICATION_SCOPES = {"bole_picks_and_topic_top_n"}


def get_settings(db_path: str | Path) -> dict:
    with connect_db(db_path) as conn:
        row = conn.execute("select value_json from settings where key = ?", (SETTINGS_KEY,)).fetchone()
    if row is None:
        return dict(DEFAULT_SETTINGS)
    try:
        stored = json.loads(row["value_json"])
    except json.JSONDecodeError:
        stored = {}
    settings = dict(DEFAULT_SETTINGS)
    if isinstance(stored, dict):
        settings.update(stored)
    return settings


def update_settings(db_path: str | Path, values: dict) -> dict:
    merged = get_settings(db_path)
    merged.update(values)
    if merged["deep_verification_scope"] not in VALID_DEEP_VERIFICATION_SCOPES:
        raise ValueError("deep_verification_scope is not supported in V1")
    merged["deep_verification_top_n"] = int(merged["deep_verification_top_n"])
    merged["deep_verification_enabled"] = bool(merged["deep_verification_enabled"])
    merged["ask_system_prompt"] = str(merged.get("ask_system_prompt") or DEFAULT_ASK_SYSTEM_PROMPT).strip()
    with connect_db(db_path) as conn:
        conn.execute(
            """
            insert into settings(key, value_json, updated_at)
            values (?, ?, ?)
            on conflict(key) do update set
              value_json = excluded.value_json,
              updated_at = excluded.updated_at
            """,
            (SETTINGS_KEY, json.dumps(merged, ensure_ascii=False), datetime.now(UTC).isoformat()),
        )
    return merged
