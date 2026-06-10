from __future__ import annotations

from collections.abc import Callable

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from ..ai_profiles import delete_ai_profile, get_ai_profile_for_use, list_ai_profiles, save_ai_profile
from ..config import AppConfig
from ..provider import AIProvider, AIProviderUnavailable


class AIProfileRequest(BaseModel):
    id: str | None = None
    name: str
    type: str = "chat_completions"
    base_url: str
    model: str
    api_key: str = ""
    headers_json: str = ""
    timeout_seconds: int = 45
    enabled: bool = True


def build_ai_profiles_router(config: AppConfig, require_session: Callable[..., dict]) -> APIRouter:
    router = APIRouter()

    @router.get("/api/ai-profiles")
    def ai_profiles(session: dict = Depends(require_session)) -> dict:
        del session
        return {"items": list_ai_profiles(config)}

    @router.post("/api/ai-profiles")
    def create_ai_profile(payload: AIProfileRequest, session: dict = Depends(require_session)) -> dict:
        del session
        try:
            return save_ai_profile(config, payload.model_dump())
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @router.put("/api/ai-profiles/{profile_id}")
    def update_ai_profile(profile_id: str, payload: AIProfileRequest, session: dict = Depends(require_session)) -> dict:
        del session
        try:
            return save_ai_profile(config, {**payload.model_dump(), "id": profile_id})
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @router.delete("/api/ai-profiles/{profile_id}")
    def remove_ai_profile(profile_id: str, session: dict = Depends(require_session)) -> dict:
        del session
        if not delete_ai_profile(config, profile_id):
            raise HTTPException(status_code=404, detail="AI profile not found")
        return {"ok": True}

    @router.post("/api/ai-profiles/{profile_id}/test")
    async def test_ai_profile(profile_id: str, session: dict = Depends(require_session)) -> dict:
        del session
        profile = get_ai_profile_for_use(config, profile_id)
        if profile is None:
            raise HTTPException(status_code=404, detail="AI profile not found")
        try:
            await AIProvider(config, profile=profile).chat(
                [
                    {"role": "system", "content": "You are testing an AI provider connection."},
                    {"role": "user", "content": "Reply with ok."},
                ],
                temperature=0,
            )
        except AIProviderUnavailable as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        return {"ok": True, "model": profile.get("model") or config.ai_model}

    return router
