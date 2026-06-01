from __future__ import annotations

import hashlib
import hmac
import secrets
from datetime import UTC, datetime, timedelta
from pathlib import Path

from .config import AppConfig
from .db import connect_db


def create_session(config: AppConfig) -> str:
    return secrets.token_urlsafe(32)


def hash_session(session_id: str, secret: str) -> str:
    return hmac.new(secret.encode("utf-8"), session_id.encode("utf-8"), hashlib.sha256).hexdigest()


def store_session(db_path: Path, session_id: str, secret: str, ttl_hours: int = 24 * 14) -> None:
    now = datetime.now(UTC)
    expires_at = now + timedelta(hours=ttl_hours)
    with connect_db(db_path) as conn:
        conn.execute(
            """
            insert into sessions(session_id_hash, expires_at, created_at)
            values (?, ?, ?)
            on conflict(session_id_hash) do update set
              expires_at = excluded.expires_at
            """,
            (hash_session(session_id, secret), expires_at.isoformat(), now.isoformat()),
        )


def validate_session(db_path: Path, session_id: str, secret: str) -> bool:
    session_hash = hash_session(session_id, secret)
    with connect_db(db_path) as conn:
        row = conn.execute(
            "select expires_at from sessions where session_id_hash = ?",
            (session_hash,),
        ).fetchone()
    if row is None:
        return False
    expires_at = datetime.fromisoformat(row["expires_at"])
    return expires_at > datetime.now(UTC)


def delete_session(db_path: Path, session_id: str, secret: str) -> None:
    with connect_db(db_path) as conn:
        conn.execute(
            "delete from sessions where session_id_hash = ?",
            (hash_session(session_id, secret),),
        )
