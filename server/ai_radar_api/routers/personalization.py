from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from ..ai_profiles import get_ai_profile_for_use
from ..config import AppConfig
from ..personalization import (
    confirm_profile_draft,
    disable_personalization,
    get_personalization_status,
    reset_personalization,
    save_profile_draft,
    skip_personalization,
)
from ..provider import AIProvider, AIProviderUnavailable
from ..settings import get_settings


class ProfileDraftRequest(BaseModel):
    profile: Any = Field(default_factory=dict)
    evidence: Any = None


class ProfileInterpretRequest(BaseModel):
    question_id: str
    stage: str = "calibration"
    answer_text: str = ""
    selected_choices: list[str] = Field(default_factory=list)
    history: list[dict[str, Any]] = Field(default_factory=list)


def _unique_labels(values: Any, limit: int = 8) -> list[str]:
    labels: list[str] = []
    seen: set[str] = set()
    if not isinstance(values, list):
        return labels
    for value in values:
        label = str(value or "").strip()
        if not label or label in seen:
            continue
        seen.add(label)
        labels.append(label)
        if len(labels) >= limit:
            break
    return labels


def _json_object_from_text(text: str) -> dict[str, Any]:
    raw = str(text or "").strip()
    if not raw:
        return {}
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        start = raw.find("{")
        end = raw.rfind("}")
        if start < 0 or end <= start:
            return {}
        try:
            payload = json.loads(raw[start : end + 1])
        except json.JSONDecodeError:
            return {}
    return payload if isinstance(payload, dict) else {}


def _interpret_messages(payload: ProfileInterpretRequest) -> list[dict[str, str]]:
    history_json = json.dumps(payload.history[:8], ensure_ascii=False, sort_keys=True)
    selected_json = json.dumps(payload.selected_choices[:12], ensure_ascii=False)
    return [
        {
            "role": "system",
            "content": (
                "你是 AI News Radar 的伯乐画像助手。根据用户当前回答和历史上下文，"
                "提炼短标签并给出自然的下一步追问。只返回 JSON，格式为 "
                '{"labels":["短标签"],"note":"一句判断","follow_up":"一句追问"}。'
                "标签必须来自用户真实表达或可解释的近义总结，不要虚构。"
            ),
        },
        {
            "role": "user",
            "content": (
                f"question_id: {payload.question_id}\n"
                f"stage: {payload.stage}\n"
                f"selected_choices: {selected_json}\n"
                f"answer_text: {payload.answer_text}\n"
                f"history: {history_json}\n"
                "请只返回 JSON。"
            ),
        },
    ]


def build_personalization_router(config: AppConfig, require_session: Callable[..., dict]) -> APIRouter:
    router = APIRouter()

    @router.get("/api/personalization")
    def personalization_status(session: dict = Depends(require_session)) -> dict:
        del session
        return get_personalization_status(config.db_path)

    @router.post("/api/personalization/interpret")
    async def interpret_profile_answer(payload: ProfileInterpretRequest, session: dict = Depends(require_session)) -> dict:
        del session
        if not str(payload.answer_text or "").strip() and not _unique_labels(payload.selected_choices):
            raise HTTPException(status_code=400, detail="answer_text or selected_choices is required")
        settings = get_settings(config.db_path)
        profile = get_ai_profile_for_use(config, str(settings.get("reading_assistant_provider_id") or "env"))
        provider = AIProvider(config, profile=profile)
        try:
            content = await provider.chat(_interpret_messages(payload), temperature=0.1)
        except AIProviderUnavailable as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        parsed = _json_object_from_text(content)
        labels = _unique_labels(parsed.get("labels"))
        if not labels:
            labels = _unique_labels(payload.selected_choices)
        return {
            "labels": labels,
            "note": str(parsed.get("note") or "").strip(),
            "follow_up": str(parsed.get("follow_up") or "").strip(),
            "source": "ai",
        }

    @router.post("/api/personalization/draft")
    def create_profile_draft(payload: ProfileDraftRequest, session: dict = Depends(require_session)) -> dict:
        del session
        try:
            return save_profile_draft(config.db_path, payload.profile, payload.evidence)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @router.post("/api/personalization/confirm")
    def confirm_profile(session: dict = Depends(require_session)) -> dict:
        del session
        try:
            return confirm_profile_draft(config.db_path)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @router.post("/api/personalization/skip")
    def skip_profile_setup(session: dict = Depends(require_session)) -> dict:
        del session
        return skip_personalization(config.db_path)

    @router.post("/api/personalization/reset")
    def reset_profile(session: dict = Depends(require_session)) -> dict:
        del session
        return reset_personalization(config.db_path)

    @router.post("/api/personalization/disable")
    def disable_profile(session: dict = Depends(require_session)) -> dict:
        del session
        return disable_personalization(config.db_path)

    return router
