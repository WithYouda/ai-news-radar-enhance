from __future__ import annotations

import hashlib
import hmac
import json
from datetime import UTC, datetime

from fastapi import Cookie, Depends, FastAPI, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from .auth import create_session, delete_session, store_session, validate_session
from .classifier import classify_item
from .config import AppConfig
from .db import connect_db, init_db
from .radar_data import item_identity, normalize_public_url
from .taxonomy import DEFAULT_TAXONOMY, seed_default_taxonomy


SESSION_COOKIE = "radar_session"
SESSION_TTL_SECONDS = 14 * 24 * 60 * 60


class LoginRequest(BaseModel):
    password: str


class ClassifyRequest(BaseModel):
    items: list[dict]


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

    @app.post("/api/classify")
    def classify(payload: ClassifyRequest, session: dict = Depends(require_session)) -> dict:
        del session
        response_items = []
        classified_at = datetime.now(UTC).isoformat()
        with connect_db(config.db_path) as conn:
            for item in payload.items:
                result = classify_item(item, DEFAULT_TAXONOMY)
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

    return app


app = create_app()
