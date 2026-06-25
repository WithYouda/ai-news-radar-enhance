from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit, urlunsplit

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
VALID_FEEDBACK_ACTIONS = {
    "more_relevant",
    "more_like_this",
    "less_relevant",
    "not_interested",
}
STRONG_FEEDBACK_ACTIONS = {"more_like_this", "not_interested"}
NEGATIVE_FEEDBACK_LABEL_KEYWORDS = (
    ("融资", ("融资", "funding", "capital", "raises", "investment", "startup roundup")),
    ("营销稿", ("营销", "marketing", "sponsored", "vendor blog")),
    ("重复转载", ("重复", "转载", "duplicate", "repost")),
    ("空泛观点", ("空泛", "opinion", "takes", "thought leadership")),
    ("过度学术", ("过度学术", "academic", "paper-only")),
    ("浅层汇总", ("浅层", "汇总", "roundup", "recap")),
)


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


def _url_origin(value: str) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""
    try:
        parsed = urlsplit(raw)
    except ValueError:
        return ""
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return ""
    return urlunsplit((parsed.scheme, parsed.netloc, "", "", ""))


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


def _feedback_item_key(item: dict) -> str:
    for key in ("item_id", "id"):
        value = str(item.get(key) or "").strip()
        if value:
            return value[:180]
    title = str(item.get("title") or item.get("title_zh") or item.get("title_en") or "").strip()
    source = str(item.get("source") or item.get("site_name") or "").strip()
    return f"{source}::{title}"[:180]


def _sanitize_feedback_item(item: Any) -> dict:
    if not isinstance(item, dict):
        raise ValueError("item must be an object")
    title = str(item.get("title") or item.get("title_zh") or item.get("title_en") or "").strip()
    if not title:
        raise ValueError("item.title is required")
    feedback_target = str(item.get("feedback_target") or item.get("target") or item.get("topic") or "").strip()
    matched_targets = _clean_feedback_targets([feedback_target, *(
        item.get("matched_targets") if isinstance(item.get("matched_targets"), list) else []
    )])
    sanitized = {
        "id": str(item.get("item_id") or item.get("id") or "").strip(),
        "title": title[:280],
        "summary": str(item.get("summary") or item.get("description") or "").strip()[:500],
        "site_name": str(item.get("site_name") or "").strip()[:120],
        "source": str(item.get("source") or "").strip()[:160],
        "url": _url_origin(str(item.get("url") or "")),
        "published_at": str(item.get("published_at") or item.get("first_seen_at") or "").strip()[:80],
        "ai_label": str(item.get("ai_label") or "").strip()[:80],
        "ai_signals": [
            str(signal or "").strip()[:80]
            for signal in (item.get("ai_signals") if isinstance(item.get("ai_signals"), list) else [])
            if str(signal or "").strip()
        ][:8],
    }
    if feedback_target and feedback_target not in {"整条新闻", "这条新闻"}:
        sanitized["feedback_target"] = feedback_target[:80]
    if matched_targets:
        sanitized["matched_targets"] = matched_targets
    sanitized["item_key"] = _feedback_item_key({**item, "title": title})
    return sanitized


def _feedback_row_to_dict(row) -> dict:
    item = _json_loads(row["item_json"], {})
    if isinstance(item, dict):
        item.pop("item_key", None)
    draft_suggestion = _json_loads(row["draft_suggestion_json"], None)
    return {
        "id": row["id"],
        "action": row["action"],
        "item_key": row["item_key"],
        "item": item,
        "reason": row["reason"],
        "draft_suggestion": draft_suggestion,
        "created_at": row["created_at"],
    }


def _feedback_semantic_text(item: dict) -> str:
    signals = item.get("ai_signals") if isinstance(item.get("ai_signals"), list) else []
    return " ".join(
        str(value or "").strip().lower()
        for value in [
            item.get("title"),
            item.get("summary"),
            item.get("site_name"),
            item.get("source"),
            item.get("ai_label"),
            *signals,
        ]
        if str(value or "").strip()
    )


def _clean_feedback_targets(values: list[Any]) -> list[str]:
    targets: list[str] = []
    for value in values:
        label = str(value or "").strip()
        if not label or label in {"整条新闻", "这条新闻"} or label in targets:
            continue
        targets.append(label[:80])
        if len(targets) >= 8:
            break
    return targets


def _feedback_suggestion_labels(action: str, item: dict) -> list[str]:
    matched_targets = item.get("matched_targets") if isinstance(item.get("matched_targets"), list) else []
    targets = _clean_feedback_targets(matched_targets)
    if targets:
        return targets[:3]
    return [_feedback_suggestion_label(action, item)]


def _feedback_suggestion_label(action: str, item: dict) -> str:
    feedback_target = str(item.get("feedback_target") or "").strip()
    if feedback_target:
        return feedback_target[:80]
    text = _feedback_semantic_text(item)
    if action == "not_interested":
        for label, keywords in NEGATIVE_FEEDBACK_LABEL_KEYWORDS:
            if any(keyword.lower() in text for keyword in keywords):
                return label
    signals = item.get("ai_signals") if isinstance(item.get("ai_signals"), list) else []
    for signal in signals:
        label = str(signal or "").strip()
        if label:
            return label[:80]
    ai_label = str(item.get("ai_label") or "").strip()
    if ai_label:
        return ai_label[:80]
    return str(item.get("title") or "").strip()[:80]


def _build_feedback_draft_suggestion(conn, action: str, item: dict, created_at: str) -> dict | None:
    if action not in STRONG_FEEDBACK_ACTIONS:
        return None
    count = conn.execute(
        """
        select count(*) as count
        from personalization_feedback
        where action = ?
        """,
        (action,),
    ).fetchone()["count"]
    if count < 2:
        return None
    interest_key = "positive_interests" if action == "more_like_this" else "negative_interests"
    labels = _feedback_suggestion_labels(action, item)
    return {
        "state": "draft_suggestion",
        "profile_patch": {
            interest_key: [
                {
                    "label": label,
                    "weight": 0.65 if action == "more_like_this" else 0.75,
                    "source": "feedback",
                }
                for label in labels
            ]
        },
        "evidence": {
            "source": "feedback",
            "feedback_count": count,
            "action": action,
            "labels": labels,
            "item_title": item["title"],
            "created_at": created_at,
        },
    }


def list_recommendation_feedback(db_path: str | Path, limit: int = 20) -> dict:
    init_db(db_path)
    safe_limit = max(1, min(100, int(limit or 20)))
    with connect_db(db_path) as conn:
        rows = conn.execute(
            """
            select id, action, item_key, item_json, reason, draft_suggestion_json, created_at
            from personalization_feedback
            order by datetime(created_at) desc, id desc
            limit ?
            """,
            (safe_limit,),
        ).fetchall()
    return {"items": [_feedback_row_to_dict(row) for row in rows]}


def record_recommendation_feedback(db_path: str | Path, action: str, item: Any, reason: str = "") -> dict:
    normalized_action = str(action or "").strip()
    if normalized_action not in VALID_FEEDBACK_ACTIONS:
        raise ValueError("action must be one of: " + ", ".join(sorted(VALID_FEEDBACK_ACTIONS)))
    sanitized_item = _sanitize_feedback_item(item)
    item_key = sanitized_item["item_key"]
    created_at = _now()
    reason_text = str(reason or "").strip()[:500]
    init_db(db_path)
    with connect_db(db_path) as conn:
        cursor = conn.execute(
            """
            insert into personalization_feedback(action, item_key, item_json, reason, draft_suggestion_json, created_at)
            values (?, ?, ?, ?, null, ?)
            """,
            (
                normalized_action,
                item_key,
                _json_dumps(sanitized_item),
                reason_text,
                created_at,
            ),
        )
        feedback_id = cursor.lastrowid
        suggestion = _build_feedback_draft_suggestion(conn, normalized_action, sanitized_item, created_at)
        if suggestion:
            conn.execute(
                """
                update personalization_feedback
                set draft_suggestion_json = ?
                where id = ?
                """,
                (_json_dumps(suggestion), feedback_id),
            )
        row = conn.execute(
            """
            select id, action, item_key, item_json, reason, draft_suggestion_json, created_at
            from personalization_feedback
            where id = ?
            """,
            (feedback_id,),
        ).fetchone()
    return {"feedback": _feedback_row_to_dict(row), "draft_suggestion": suggestion}


def delete_recommendation_feedback(db_path: str | Path, feedback_id: int) -> bool:
    init_db(db_path)
    with connect_db(db_path) as conn:
        cursor = conn.execute(
            "delete from personalization_feedback where id = ?",
            (feedback_id,),
        )
        return cursor.rowcount > 0
