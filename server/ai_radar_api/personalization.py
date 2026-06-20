from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .db import connect_db, init_db


STATE_NOT_STARTED = "not_started"
STATE_SKIPPED = "skipped"
STATE_DRAFT_PENDING = "draft_pending"
STATE_CONFIRMED = "confirmed"
VALID_STATES = {
    STATE_NOT_STARTED,
    STATE_SKIPPED,
    STATE_DRAFT_PENDING,
    STATE_CONFIRMED,
}

DEFAULT_BEHAVIOR_PREFERENCES = {
    "summary_depth": "concise",
    "verification_strictness": "standard",
}


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _json_loads(value: str | None, fallback: Any) -> Any:
    if not value:
        return fallback
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return fallback


def _json_dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def _default_status() -> dict:
    return {
        "state": STATE_NOT_STARTED,
        "enabled": False,
        "active_profile": None,
        "draft_profile": None,
        "capabilities": _capabilities(),
        "updated_at": None,
    }


def _capabilities() -> dict:
    return {
        "draft_confirmation_required": True,
        "can_skip": True,
        "can_reset": True,
        "can_disable": True,
    }


def _status_from_row(row) -> dict:
    if row is None:
        return _default_status()
    active_profile = _json_loads(row["active_profile_json"], None)
    draft_profile = _json_loads(row["draft_profile_json"], None)
    if active_profile:
        active_profile.setdefault("version", row["version"])
        if row["confirmed_at"]:
            active_profile.setdefault("confirmed_at", row["confirmed_at"])
    if draft_profile:
        draft_profile.setdefault("evidence", _json_loads(row["evidence_json"], {}))
    return {
        "state": row["state"],
        "enabled": bool(row["enabled"]),
        "active_profile": active_profile,
        "draft_profile": draft_profile,
        "capabilities": _capabilities(),
        "updated_at": row["updated_at"],
    }


def _fetch_state(conn):
    return conn.execute(
        """
        select state, enabled, active_profile_json, draft_profile_json,
               evidence_json, version, updated_at, confirmed_at
        from personalization_state
        where id = 1
        """
    ).fetchone()


def get_personalization_status(db_path: str | Path) -> dict:
    init_db(db_path)
    with connect_db(db_path) as conn:
        row = _fetch_state(conn)
    return _status_from_row(row)


def _validate_interest_list(profile: dict, key: str) -> list[dict]:
    raw_items = profile.get(key, [])
    if not isinstance(raw_items, list):
        raise ValueError(f"profile.{key} must be a list")
    items = []
    for index, raw_item in enumerate(raw_items):
        if not isinstance(raw_item, dict):
            raise ValueError(f"profile.{key}[{index}] must be an object")
        label = str(raw_item.get("label") or "").strip()
        if not label:
            raise ValueError(f"profile.{key}[{index}].label is required")
        try:
            weight = float(raw_item.get("weight", 0))
        except (TypeError, ValueError) as exc:
            raise ValueError(f"profile.{key}[{index}].weight must be numeric") from exc
        if weight < 0 or weight > 1:
            raise ValueError(f"profile.{key}[{index}].weight must be between 0 and 1")
        items.append(
            {
                "label": label,
                "weight": weight,
                "source": str(raw_item.get("source") or "").strip() or "user",
            }
        )
    return items


def _validate_source_preferences(profile: dict) -> list[dict]:
    raw_items = profile.get("source_preferences", [])
    if not isinstance(raw_items, list):
        raise ValueError("profile.source_preferences must be a list")
    items = []
    for index, raw_item in enumerate(raw_items):
        if not isinstance(raw_item, dict):
            raise ValueError(f"profile.source_preferences[{index}] must be an object")
        source = str(raw_item.get("source") or "").strip()
        if not source:
            raise ValueError(f"profile.source_preferences[{index}].source is required")
        try:
            weight = float(raw_item.get("weight", 0))
        except (TypeError, ValueError) as exc:
            raise ValueError(f"profile.source_preferences[{index}].weight must be numeric") from exc
        if weight < -1 or weight > 1:
            raise ValueError(f"profile.source_preferences[{index}].weight must be between -1 and 1")
        items.append({"source": source, "weight": weight})
    return items


def validate_profile(profile: dict) -> dict:
    if not isinstance(profile, dict):
        raise ValueError("profile must be an object")
    behavior = profile.get("behavior_preferences", {})
    if behavior is None:
        behavior = {}
    if not isinstance(behavior, dict):
        raise ValueError("profile.behavior_preferences must be an object")
    merged_behavior = dict(DEFAULT_BEHAVIOR_PREFERENCES)
    merged_behavior.update({str(key): value for key, value in behavior.items()})
    return {
        "positive_interests": _validate_interest_list(profile, "positive_interests"),
        "negative_interests": _validate_interest_list(profile, "negative_interests"),
        "source_preferences": _validate_source_preferences(profile),
        "behavior_preferences": merged_behavior,
    }


def _validate_evidence(evidence: dict | None) -> dict:
    if evidence is None:
        return {}
    if not isinstance(evidence, dict):
        raise ValueError("evidence must be an object")
    return evidence


def save_profile_draft(db_path: str | Path, profile: dict, evidence: dict | None = None) -> dict:
    init_db(db_path)
    normalized = validate_profile(profile)
    normalized["drafted_at"] = _now()
    evidence_payload = _validate_evidence(evidence)
    updated_at = _now()
    with connect_db(db_path) as conn:
        row = _fetch_state(conn)
        active_profile_json = row["active_profile_json"] if row else None
        version = int(row["version"]) if row else 0
        conn.execute(
            """
            insert into personalization_state(
              id, state, enabled, active_profile_json, draft_profile_json,
              evidence_json, version, created_at, updated_at, confirmed_at
            )
            values (1, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            on conflict(id) do update set
              state = excluded.state,
              enabled = excluded.enabled,
              active_profile_json = excluded.active_profile_json,
              draft_profile_json = excluded.draft_profile_json,
              evidence_json = excluded.evidence_json,
              version = excluded.version,
              updated_at = excluded.updated_at,
              confirmed_at = excluded.confirmed_at
            """,
            (
                STATE_DRAFT_PENDING,
                0,
                active_profile_json,
                _json_dumps(normalized),
                _json_dumps(evidence_payload),
                version,
                updated_at,
                updated_at,
                row["confirmed_at"] if row else None,
            ),
        )
        return _status_from_row(_fetch_state(conn))


def confirm_profile_draft(db_path: str | Path) -> dict:
    init_db(db_path)
    updated_at = _now()
    with connect_db(db_path) as conn:
        row = _fetch_state(conn)
        if row is None or not row["draft_profile_json"]:
            raise ValueError("profile draft is required before confirmation")
        version = int(row["version"]) + 1
        active_profile = _json_loads(row["draft_profile_json"], {})
        active_profile["version"] = version
        active_profile["confirmed_at"] = updated_at
        conn.execute(
            """
            update personalization_state
            set state = ?,
                enabled = 1,
                active_profile_json = ?,
                draft_profile_json = null,
                evidence_json = '{}',
                version = ?,
                updated_at = ?,
                confirmed_at = ?
            where id = 1
            """,
            (
                STATE_CONFIRMED,
                _json_dumps(active_profile),
                version,
                updated_at,
                updated_at,
            ),
        )
        return _status_from_row(_fetch_state(conn))


def skip_personalization(db_path: str | Path) -> dict:
    init_db(db_path)
    updated_at = _now()
    with connect_db(db_path) as conn:
        row = _fetch_state(conn)
        active_profile_json = row["active_profile_json"] if row else None
        version = int(row["version"]) if row else 0
        conn.execute(
            """
            insert into personalization_state(
              id, state, enabled, active_profile_json, draft_profile_json,
              evidence_json, version, created_at, updated_at, confirmed_at
            )
            values (1, ?, 0, ?, null, '{}', ?, ?, ?, ?)
            on conflict(id) do update set
              state = excluded.state,
              enabled = 0,
              draft_profile_json = null,
              evidence_json = '{}',
              updated_at = excluded.updated_at
            """,
            (
                STATE_SKIPPED,
                active_profile_json,
                version,
                updated_at,
                updated_at,
                row["confirmed_at"] if row else None,
            ),
        )
        return _status_from_row(_fetch_state(conn))


def reset_personalization(db_path: str | Path) -> dict:
    init_db(db_path)
    updated_at = _now()
    with connect_db(db_path) as conn:
        conn.execute(
            """
            insert into personalization_state(
              id, state, enabled, active_profile_json, draft_profile_json,
              evidence_json, version, created_at, updated_at, confirmed_at
            )
            values (1, ?, 0, null, null, '{}', 0, ?, ?, null)
            on conflict(id) do update set
              state = excluded.state,
              enabled = 0,
              active_profile_json = null,
              draft_profile_json = null,
              evidence_json = '{}',
              version = 0,
              updated_at = excluded.updated_at,
              confirmed_at = null
            """,
            (STATE_NOT_STARTED, updated_at, updated_at),
        )
        return _status_from_row(_fetch_state(conn))


def disable_personalization(db_path: str | Path) -> dict:
    init_db(db_path)
    updated_at = _now()
    with connect_db(db_path) as conn:
        row = _fetch_state(conn)
        if row is None:
            return reset_personalization(db_path)
        conn.execute(
            """
            update personalization_state
            set enabled = 0,
                updated_at = ?
            where id = 1
            """,
            (updated_at,),
        )
        return _status_from_row(_fetch_state(conn))
