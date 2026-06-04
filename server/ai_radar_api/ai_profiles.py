from __future__ import annotations

import base64
import hashlib
import json
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from cryptography.fernet import Fernet

from .config import AppConfig
from .db import connect_db


SUPPORTED_PROVIDER_TYPES = {"chat_completions", "responses"}
ENV_PROFILE_ID = "env"


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _cipher(config: AppConfig) -> Fernet:
    key = str(config.encryption_key or "").strip()
    if not key:
        raise ValueError("RADAR_ENCRYPTION_KEY is required to save AI provider secrets")
    derived = base64.urlsafe_b64encode(hashlib.sha256(key.encode("utf-8")).digest())
    return Fernet(derived)


def encrypt_secret(config: AppConfig, value: str) -> str:
    text = str(value or "")
    if not text:
        return ""
    return _cipher(config).encrypt(text.encode("utf-8")).decode("ascii")


def decrypt_secret(config: AppConfig, value: str) -> str:
    text = str(value or "")
    if not text:
        return ""
    return _cipher(config).decrypt(text.encode("ascii")).decode("utf-8")


def _parse_headers_json(value: Any) -> dict[str, str]:
    if value is None or value == "":
        return {}
    if isinstance(value, dict):
        raw = value
    else:
        try:
            raw = json.loads(str(value))
        except json.JSONDecodeError as exc:
            raise ValueError("headers_json must be valid JSON") from exc
    if not isinstance(raw, dict):
        raise ValueError("headers_json must be a JSON object")
    headers = {}
    for key, header_value in raw.items():
        name = str(key or "").strip()
        if not name:
            raise ValueError("headers_json contains an empty header name")
        headers[name] = str(header_value)
    return headers


def _validate_profile(values: dict) -> dict:
    provider_type = str(values.get("type") or "chat_completions").strip().lower().replace("-", "_")
    if provider_type not in SUPPORTED_PROVIDER_TYPES:
        raise ValueError("AI provider type is not supported")
    name = str(values.get("name") or "").strip()
    if not name:
        raise ValueError("AI provider name is required")
    base_url = str(values.get("base_url") or "").strip().rstrip("/")
    if not base_url:
        raise ValueError("AI provider base_url is required")
    model = str(values.get("model") or "").strip()
    if not model:
        raise ValueError("AI provider model is required")
    timeout_seconds = int(values.get("timeout_seconds") or 45)
    timeout_seconds = max(5, min(timeout_seconds, 180))
    return {
        "name": name,
        "type": provider_type,
        "base_url": base_url,
        "model": model,
        "timeout_seconds": timeout_seconds,
        "enabled": bool(values.get("enabled", True)),
    }


def _env_profile(config: AppConfig) -> dict:
    return {
        "id": ENV_PROFILE_ID,
        "name": "环境变量 AI",
        "type": config.ai_api_format or "chat_completions",
        "base_url": config.ai_base_url,
        "model": config.ai_model,
        "has_api_key": bool(config.ai_api_key),
        "headers_preview": [],
        "timeout_seconds": 45,
        "enabled": True,
        "readonly": True,
    }


def _sanitize_row(config: AppConfig, row) -> dict:
    headers = {}
    if row["headers_encrypted"]:
        try:
            headers = _parse_headers_json(decrypt_secret(config, row["headers_encrypted"]))
        except Exception:
            headers = {}
    return {
        "id": row["id"],
        "name": row["name"],
        "type": row["type"],
        "base_url": row["base_url"],
        "model": row["model"],
        "has_api_key": bool(row["api_key_encrypted"]),
        "headers_preview": sorted(headers.keys()),
        "timeout_seconds": int(row["timeout_seconds"]),
        "enabled": bool(row["enabled"]),
        "readonly": False,
    }


def list_ai_profiles(config: AppConfig) -> list[dict]:
    with connect_db(config.db_path) as conn:
        rows = conn.execute(
            """
            select id, name, type, base_url, model, api_key_encrypted, headers_encrypted,
                   timeout_seconds, enabled, created_at, updated_at
            from ai_provider_profiles
            order by updated_at desc
            """
        ).fetchall()
    if not rows:
        return [_env_profile(config)]
    return [_sanitize_row(config, row) for row in rows]


def get_ai_profile_for_use(config: AppConfig, profile_id: str | None) -> dict | None:
    if not profile_id or profile_id == ENV_PROFILE_ID:
        if not config.ai_base_url or not config.ai_api_key:
            return None
        return {
            "id": ENV_PROFILE_ID,
            "name": "环境变量 AI",
            "type": config.ai_api_format or "chat_completions",
            "base_url": config.ai_base_url,
            "api_key": config.ai_api_key,
            "model": config.ai_model,
            "headers": {},
            "timeout_seconds": 45,
        }
    with connect_db(config.db_path) as conn:
        row = conn.execute(
            """
            select id, name, type, base_url, model, api_key_encrypted, headers_encrypted,
                   timeout_seconds, enabled
            from ai_provider_profiles
            where id = ?
            """,
            (profile_id,),
        ).fetchone()
    if row is None or not row["enabled"]:
        return None
    headers = _parse_headers_json(decrypt_secret(config, row["headers_encrypted"])) if row["headers_encrypted"] else {}
    api_key = decrypt_secret(config, row["api_key_encrypted"]) if row["api_key_encrypted"] else ""
    return {
        "id": row["id"],
        "name": row["name"],
        "type": row["type"],
        "base_url": row["base_url"],
        "api_key": api_key,
        "model": row["model"],
        "headers": headers,
        "timeout_seconds": int(row["timeout_seconds"]),
    }


def save_ai_profile(config: AppConfig, values: dict) -> dict:
    profile = _validate_profile(values)
    profile_id = str(values.get("id") or uuid.uuid4().hex)
    now = _now()
    headers_json = values.get("headers_json")
    headers = _parse_headers_json(headers_json)
    api_key = str(values.get("api_key") or "")

    existing = None
    with connect_db(config.db_path) as conn:
        existing = conn.execute(
            "select api_key_encrypted, headers_encrypted, created_at from ai_provider_profiles where id = ?",
            (profile_id,),
        ).fetchone()

    if api_key:
        api_key_encrypted = encrypt_secret(config, api_key)
    elif existing:
        api_key_encrypted = existing["api_key_encrypted"]
    else:
        api_key_encrypted = ""

    if headers:
        headers_encrypted = encrypt_secret(config, json.dumps(headers, ensure_ascii=False, sort_keys=True))
    elif existing:
        headers_encrypted = existing["headers_encrypted"]
    else:
        headers_encrypted = ""

    created_at = existing["created_at"] if existing else now
    with connect_db(config.db_path) as conn:
        conn.execute(
            """
            insert into ai_provider_profiles(
              id, name, type, base_url, model, api_key_encrypted, headers_encrypted,
              timeout_seconds, enabled, created_at, updated_at
            )
            values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            on conflict(id) do update set
              name = excluded.name,
              type = excluded.type,
              base_url = excluded.base_url,
              model = excluded.model,
              api_key_encrypted = excluded.api_key_encrypted,
              headers_encrypted = excluded.headers_encrypted,
              timeout_seconds = excluded.timeout_seconds,
              enabled = excluded.enabled,
              updated_at = excluded.updated_at
            """,
            (
                profile_id,
                profile["name"],
                profile["type"],
                profile["base_url"],
                profile["model"],
                api_key_encrypted,
                headers_encrypted,
                profile["timeout_seconds"],
                1 if profile["enabled"] else 0,
                created_at,
                now,
            ),
        )
    with connect_db(config.db_path) as conn:
        row = conn.execute(
            """
            select id, name, type, base_url, model, api_key_encrypted, headers_encrypted,
                   timeout_seconds, enabled, created_at, updated_at
            from ai_provider_profiles
            where id = ?
            """,
            (profile_id,),
        ).fetchone()
    return _sanitize_row(config, row)


def delete_ai_profile(config: AppConfig, profile_id: str) -> bool:
    if profile_id == ENV_PROFILE_ID:
        return False
    with connect_db(config.db_path) as conn:
        cursor = conn.execute("delete from ai_provider_profiles where id = ?", (profile_id,))
        return cursor.rowcount > 0
