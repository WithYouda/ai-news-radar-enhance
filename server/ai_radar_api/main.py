from __future__ import annotations

import hmac

from fastapi import Cookie, Depends, FastAPI, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from .auth import create_session, delete_session, store_session, validate_session
from .config import AppConfig
from .db import init_db
from .taxonomy import seed_default_taxonomy


SESSION_COOKIE = "radar_session"
SESSION_TTL_SECONDS = 14 * 24 * 60 * 60


class LoginRequest(BaseModel):
    password: str


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

    return app


app = create_app()
