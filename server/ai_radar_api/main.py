from __future__ import annotations

import hashlib
import hmac
import json
from datetime import UTC, datetime

from fastapi import Cookie, Depends, FastAPI, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from .assistant import answer_question
from .auth import create_session, delete_session, store_session, validate_session
from .classifier import classify_item
from .config import AppConfig
from .db import connect_db, init_db
from .radar_data import item_identity, load_latest_items, merge_item_metadata, normalize_public_url
from .settings import get_settings, update_settings
from .taxonomy import list_taxonomy, seed_default_taxonomy
from .provider import AIProviderUnavailable
from .verification import fetch_and_verify


SESSION_COOKIE = "radar_session"
SESSION_TTL_SECONDS = 14 * 24 * 60 * 60


class LoginRequest(BaseModel):
    password: str


class ClassifyRequest(BaseModel):
    items: list[dict]


class VerificationRequest(BaseModel):
    item: dict | None = None


class AskRequest(BaseModel):
    question: str
    scope: str = "today"
    item_id: str | None = None
    category: str | None = None


def create_app(config: AppConfig | None = None) -> FastAPI:
    config = config or AppConfig.from_env()
    init_db(config.db_path)
    seed_default_taxonomy(config.db_path)

    app = FastAPI(title="AI News Radar API")
    app.state.config = config
    app.add_middleware(
        CORSMiddleware,
        allow_origins=config.allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    def require_session(radar_session: str | None = Cookie(default=None, alias=SESSION_COOKIE)) -> dict:
        if not radar_session or not validate_session(config.db_path, radar_session, config.session_secret):
            raise HTTPException(status_code=401, detail="Authentication required")
        return {"authenticated": True}

    @app.get("/health")
    def health() -> dict:
        return {"ok": True}

    @app.post("/api/auth/login")
    def login(payload: LoginRequest, response: Response) -> dict:
        if not config.admin_password or not hmac.compare_digest(payload.password, config.admin_password):
            raise HTTPException(status_code=401, detail="Invalid password")
        session_id = create_session(config)
        store_session(config.db_path, session_id, config.session_secret)
        response.set_cookie(
            SESSION_COOKIE,
            session_id,
            httponly=True,
            secure=True,
            samesite="none",
            max_age=SESSION_TTL_SECONDS,
        )
        return {"ok": True}

    @app.post("/api/auth/logout")
    def logout(response: Response, radar_session: str | None = Cookie(default=None, alias=SESSION_COOKIE)) -> dict:
        if radar_session:
            delete_session(config.db_path, radar_session, config.session_secret)
        response.delete_cookie(SESSION_COOKIE, secure=True, samesite="none")
        return {"ok": True}

    @app.get("/api/me")
    def me(session: dict = Depends(require_session)) -> dict:
        return session

    @app.get("/api/taxonomy")
    def taxonomy() -> dict:
        return {"categories": list_taxonomy(config.db_path)}

    @app.post("/api/classify")
    def classify(payload: ClassifyRequest, session: dict = Depends(require_session)) -> dict:
        del session
        response_items = []
        classified_at = datetime.now(UTC).isoformat()
        taxonomy_rows = list_taxonomy(config.db_path)
        with connect_db(config.db_path) as conn:
            for item in payload.items:
                result = classify_item(item, taxonomy_rows)
                item_id = item_identity(item)
                title = str(item.get("title") or "")
                url = normalize_public_url(str(item.get("url") or ""))
                conn.execute(
                    """
                    insert into item_classifications(
                      item_id, url, title_hash, top_category, sub_category, confidence,
                      reason, taxonomy_version, model, manual_override_json, classified_at
                    )
                    values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    on conflict(item_id) do update set
                      url = excluded.url,
                      title_hash = excluded.title_hash,
                      top_category = excluded.top_category,
                      sub_category = excluded.sub_category,
                      confidence = excluded.confidence,
                      reason = excluded.reason,
                      taxonomy_version = excluded.taxonomy_version,
                      model = excluded.model,
                      classified_at = excluded.classified_at
                    """,
                    (
                        item_id,
                        url,
                        hashlib.sha1(title.encode("utf-8")).hexdigest(),
                        result["top_category"],
                        result["sub_category"],
                        result["confidence"],
                        result["reason"],
                        "default-v1",
                        result["model"],
                        json.dumps(None),
                        classified_at,
                    ),
                )
                response_items.append({"item_id": item_id, **result})
        return {"items": response_items}

    @app.get("/api/verification/items")
    def verification_items(session: dict = Depends(require_session)) -> dict:
        del session
        with connect_db(config.db_path) as conn:
            rows = conn.execute(
                """
                select item_id, url, status, authority_score, authority_reason,
                       evidence_json, deep_verified, manual_score, manual_note,
                       model, verified_at
                from verification_results
                order by verified_at desc
                """
            ).fetchall()
        verification_by_id = {
            row["item_id"]: {
                "item_id": row["item_id"],
                "url": row["url"],
                "status": row["status"],
                "authority_score": row["authority_score"],
                "authority_reason": row["authority_reason"],
                "evidence_links": json.loads(row["evidence_json"]),
                "deep_verified": bool(row["deep_verified"]),
                "manual_score": row["manual_score"],
                "manual_note": row["manual_note"],
                "model": row["model"],
                "verified_at": row["verified_at"],
            }
            for row in rows
        }
        try:
            items = load_latest_items(config)
        except Exception:
            items = []
        merged_items = [
            merge_item_metadata(item, None, verification_by_id.get(item_identity(item)))
            for item in items[: config.max_context_items]
        ]
        return {"items": merged_items, "verified_items": list(verification_by_id.values())}

    def store_verification_result(item_id: str, item: dict, result: dict) -> dict:
        url = normalize_public_url(str(item.get("url") or result.get("url") or ""))
        with connect_db(config.db_path) as conn:
            conn.execute(
                """
                insert into verification_results(
                  item_id, url, status, authority_score, authority_reason,
                  evidence_json, deep_verified, manual_score, manual_note, model, verified_at
                )
                values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                on conflict(item_id) do update set
                  url = excluded.url,
                  status = excluded.status,
                  authority_score = excluded.authority_score,
                  authority_reason = excluded.authority_reason,
                  evidence_json = excluded.evidence_json,
                  deep_verified = excluded.deep_verified,
                  model = excluded.model,
                  verified_at = excluded.verified_at
                """,
                (
                    item_id,
                    url,
                    result["status"],
                    result["authority_score"],
                    result["authority_reason"],
                    json.dumps(result.get("evidence_links", []), ensure_ascii=False),
                    1 if result.get("deep_verified") else 0,
                    None,
                    None,
                    result["model"],
                    result["verified_at"],
                ),
            )
        return {"item_id": item_id, **result}

    def find_verification_item(item_id: str, payload: VerificationRequest | None) -> dict:
        if payload and payload.item:
            return payload.item
        try:
            items = load_latest_items(config)
        except Exception:
            items = []
        for item in items:
            if item_identity(item) == item_id or str(item.get("id") or "") == item_id:
                return item
        with connect_db(config.db_path) as conn:
            row = conn.execute(
                """
                select url from verification_results where item_id = ? and coalesce(url, '') <> ''
                union
                select url from item_classifications where item_id = ? and coalesce(url, '') <> ''
                limit 1
                """,
                (item_id, item_id),
            ).fetchone()
        if row and row["url"]:
            return {"url": row["url"]}
        raise HTTPException(status_code=404, detail="Item not found for verification")

    @app.post("/api/verification/{item_id}/verify")
    def verify_item(item_id: str, payload: VerificationRequest | None = None, session: dict = Depends(require_session)) -> dict:
        del session
        item = find_verification_item(item_id, payload)
        result = fetch_and_verify(item, deep=False)
        return store_verification_result(item_id, item, result)

    @app.post("/api/verification/{item_id}/deep-verify")
    def deep_verify_item(
        item_id: str,
        payload: VerificationRequest | None = None,
        session: dict = Depends(require_session),
    ) -> dict:
        del session
        item = find_verification_item(item_id, payload)
        result = fetch_and_verify(item, deep=True)
        result["deep_verified"] = True
        return store_verification_result(item_id, item, result)

    @app.post("/api/ask")
    async def ask(payload: AskRequest, session: dict = Depends(require_session)) -> dict:
        del session
        try:
            items = load_latest_items(config, mode="ai")
        except Exception:
            items = []
        if payload.item_id:
            items = [item for item in items if item_identity(item) == payload.item_id or str(item.get("id") or "") == payload.item_id]
        if payload.category:
            items = [
                item
                for item in items
                if item.get("top_category") == payload.category or item.get("ai_label") == payload.category
            ]
        try:
            return await answer_question(config, payload.question, items)
        except AIProviderUnavailable as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc

    @app.get("/api/settings")
    def read_settings(session: dict = Depends(require_session)) -> dict:
        del session
        return get_settings(config.db_path)

    @app.put("/api/settings")
    def write_settings(payload: dict, session: dict = Depends(require_session)) -> dict:
        del session
        try:
            return update_settings(config.db_path, payload)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    return app


app = create_app()
