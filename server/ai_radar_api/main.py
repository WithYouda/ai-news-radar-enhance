from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime

from fastapi import Cookie, Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse, StreamingResponse
from pydantic import BaseModel

from .article_reader import fetch_cached_article_for_request, fetch_clean_article, find_news_item, sync_article_aliases_from_local_data
from .ai_profiles import get_ai_profile_for_use
from .assistant import answer_question, finalize_streaming_answer, prepare_streaming_answer, translate_clean_text
from .auth import validate_session
from .classifier import classify_item
from .config import AppConfig
from .conversations import (
    append_ask_assistant_response,
    delete_ask_conversation,
    delete_ask_message,
    get_ask_conversation,
    list_ask_conversations,
    replace_ask_message,
    store_ask_conversation,
    update_ask_message,
)
from .db import connect_db, init_db
from .radar_data import item_identity, load_latest_items, load_latest_items_with_source, merge_item_metadata, normalize_public_url
from .routers.ai_profiles import build_ai_profiles_router
from .routers.auth import SESSION_COOKIE, build_auth_router
from .settings import get_settings, update_settings
from .taxonomy import list_taxonomy, seed_default_taxonomy
from .provider import AIProvider, AIProviderUnavailable
from .verification import fetch_and_verify


LEGACY_TOP_CATEGORY_BY_LABEL = {
    "ai_general": "模型与产品",
    "model_release": "模型与产品",
    "ai_product_update": "模型与产品",
    "agent_workflow": "Agent 与工作流",
    "developer_tool": "开发者工具",
    "developer_tooling": "开发者工具",
    "infrastructure": "算力与基础设施",
    "infra_compute": "算力与基础设施",
    "ai_tech": "研究与评测",
    "research_paper": "研究与评测",
    "robotics": "研究与评测",
    "industry_business": "公司与行业",
}


class ClassifyRequest(BaseModel):
    items: list[dict]


class VerificationRequest(BaseModel):
    item: dict | None = None


class AskRequest(BaseModel):
    question: str
    scope: str = "today"
    item_id: str | None = None
    category: str | None = None
    conversation_id: str | None = None


class AskMessageUpdateRequest(BaseModel):
    content: str


class TranslateRequest(BaseModel):
    text: str
    source_language: str = "auto"


def item_matches_category(item: dict, category: str) -> bool:
    labels = {
        str(item.get("top_category") or ""),
        str(item.get("sub_category") or ""),
        str(item.get("ai_label") or ""),
        LEGACY_TOP_CATEGORY_BY_LABEL.get(str(item.get("ai_label") or ""), ""),
    }
    return category in labels


def create_app(config: AppConfig | None = None) -> FastAPI:
    config = config or AppConfig.from_env()
    init_db(config.db_path)
    seed_default_taxonomy(config.db_path)
    sync_article_aliases_from_local_data(config)

    app = FastAPI(title="AI News Radar API")
    app.state.config = config
    app.add_middleware(
        CORSMiddleware,
        allow_origins=config.allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(build_auth_router(config))

    def require_session(radar_session: str | None = Cookie(default=None, alias=SESSION_COOKIE)) -> dict:
        if not radar_session or not validate_session(config.db_path, radar_session, config.session_secret):
            raise HTTPException(status_code=401, detail="Authentication required")
        return {"authenticated": True}

    app.include_router(build_ai_profiles_router(config, require_session))

    def scoped_ask_items(scope_payload: dict) -> tuple[list[dict], str | None]:
        items, context_source = load_latest_items_with_source(config, mode="ai")
        item_id = scope_payload.get("item_id")
        category = scope_payload.get("category")
        if item_id:
            items = [
                item
                for item in items
                if item_identity(item) == item_id or str(item.get("id") or "") == item_id
            ]
        if category:
            items = [item for item in items if item_matches_category(item, str(category))]
        return items, context_source

    def attach_clean_article_context(scope_payload: dict, items: list[dict]) -> list[dict]:
        if not scope_payload.get("item_id") or len(items) != 1:
            return items
        item = items[0]
        try:
            article = fetch_clean_article(config, item)
        except Exception:
            return items
        text = str(article.get("text") or "").strip()
        if not text:
            return items
        enriched = dict(item)
        enriched["article_title"] = article.get("title") or item.get("title")
        enriched["article_text"] = text
        enriched["article_access_status"] = article.get("access_status") or "open"
        return [enriched]

    def reading_assistant_provider(settings: dict | None = None) -> AIProvider:
        settings = settings or get_settings(config.db_path)
        profile = get_ai_profile_for_use(config, str(settings.get("reading_assistant_provider_id") or "env"))
        return AIProvider(config, profile=profile)

    def translation_provider(settings: dict | None = None) -> AIProvider:
        settings = settings or get_settings(config.db_path)
        if settings.get("translation_provider_mode") != "ai":
            raise ValueError("AI translation is not enabled")
        profile_id = str(settings.get("translation_provider_id") or "env")
        profile = get_ai_profile_for_use(config, profile_id)
        if profile is None:
            raise ValueError("AI translation provider is not available")
        return AIProvider(config, profile=profile)

    @app.get("/", include_in_schema=False)
    def root() -> RedirectResponse:
        return RedirectResponse(config.public_base_url)

    @app.get("/health")
    def health() -> dict:
        return {"ok": True}

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

    @app.get("/api/read/{item_id}")
    def read_article(item_id: str) -> dict:
        try:
            cached_article = fetch_cached_article_for_request(config, item_id)
            if cached_article is not None:
                return cached_article
            item = find_news_item(config, item_id)
            if item is None:
                raise HTTPException(status_code=404, detail="News item not found")
            return fetch_clean_article(config, item)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        except HTTPException:
            raise
        except Exception as exc:
            raise HTTPException(status_code=502, detail=f"文章读取失败: {exc}") from exc

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

    def verification_storage_id(route_item_id: str, payload: VerificationRequest | None, item: dict) -> str:
        if payload and payload.item:
            return item_identity(item)
        return route_item_id

    @app.post("/api/verification/{item_id:path}/verify")
    def verify_item(item_id: str, payload: VerificationRequest | None = None, session: dict = Depends(require_session)) -> dict:
        del session
        item = find_verification_item(item_id, payload)
        result = fetch_and_verify(item, deep=False)
        return store_verification_result(verification_storage_id(item_id, payload, item), item, result)

    @app.post("/api/verification/{item_id:path}/deep-verify")
    def deep_verify_item(
        item_id: str,
        payload: VerificationRequest | None = None,
        session: dict = Depends(require_session),
    ) -> dict:
        del session
        item = find_verification_item(item_id, payload)
        result = fetch_and_verify(item, deep=True)
        result["deep_verified"] = True
        return store_verification_result(verification_storage_id(item_id, payload, item), item, result)

    async def run_ask_payload(payload: AskRequest) -> dict:
        try:
            scope_payload = {
                "scope": payload.scope,
                "category": payload.category,
                "item_id": payload.item_id,
            }
            items, context_source = scoped_ask_items(scope_payload)
            items = attach_clean_article_context(scope_payload, items)
        except Exception as exc:
            raise HTTPException(status_code=503, detail=f"后端无法加载新闻数据: {exc}") from exc
        try:
            existing_conversation = get_ask_conversation(config.db_path, payload.conversation_id) if payload.conversation_id else None
            conversation_messages = [
                {"role": message.get("role"), "content": message.get("content")}
                for message in (existing_conversation or {}).get("messages", [])
                if message.get("role") in {"user", "assistant"} and message.get("content")
            ]
            settings = get_settings(config.db_path)
            ask_system_prompt = str(settings.get("ask_system_prompt") or "")
            provider = reading_assistant_provider(settings)
            if conversation_messages:
                result = await answer_question(
                    config,
                    payload.question,
                    items,
                    conversation_messages=conversation_messages,
                    system_prompt=ask_system_prompt,
                    provider=provider,
                )
            else:
                result = await answer_question(
                    config,
                    payload.question,
                    items,
                    system_prompt=ask_system_prompt,
                    provider=provider,
                )
            result["context_item_count"] = len(items)
            result["context_source"] = context_source
            if payload.item_id and items:
                scope_payload["item_title"] = items[0].get("title") or items[0].get("title_zh") or items[0].get("title_en")
            try:
                conversation = store_ask_conversation(
                    config.db_path,
                    conversation_id=payload.conversation_id if existing_conversation else None,
                    question=payload.question,
                    answer=str(result.get("answer") or ""),
                    title=str(result.get("title") or ""),
                    scope_payload=scope_payload,
                    citations=list(result.get("citations") or []),
                    model=str(result.get("model") or config.ai_model),
                    context_source=context_source,
                    context_item_count=len(items),
                )
                result["history_saved"] = True
                result["conversation_id"] = conversation["conversation_id"]
                result["messages"] = conversation.get("messages", [])
                result["title"] = conversation.get("title") or result.get("title")
            except Exception:
                result["history_saved"] = False
            return result
        except AIProviderUnavailable as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc

    def sse_event(event: str, data: dict) -> str:
        return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False, separators=(',', ':'))}\n\n"

    @app.post("/api/ask")
    async def ask(payload: AskRequest, session: dict = Depends(require_session)) -> dict:
        del session
        return await run_ask_payload(payload)

    @app.post("/api/ask/stream")
    async def ask_stream(payload: AskRequest, session: dict = Depends(require_session)) -> StreamingResponse:
        del session
        try:
            scope_payload = {
                "scope": payload.scope,
                "category": payload.category,
                "item_id": payload.item_id,
            }
            items, context_source = scoped_ask_items(scope_payload)
            items = attach_clean_article_context(scope_payload, items)
        except Exception as exc:
            raise HTTPException(status_code=503, detail=f"后端无法加载新闻数据: {exc}") from exc

        existing_conversation = get_ask_conversation(config.db_path, payload.conversation_id) if payload.conversation_id else None
        conversation_messages = [
            {"role": message.get("role"), "content": message.get("content")}
            for message in (existing_conversation or {}).get("messages", [])
            if message.get("role") in {"user", "assistant"} and message.get("content")
        ]
        settings = get_settings(config.db_path)
        ask_system_prompt = str(settings.get("ask_system_prompt") or "")
        provider = reading_assistant_provider(settings)
        messages, ranked_items = prepare_streaming_answer(
            config,
            payload.question,
            items,
            conversation_messages=conversation_messages,
            system_prompt=ask_system_prompt,
        )
        if payload.item_id and items:
            scope_payload["item_title"] = items[0].get("title") or items[0].get("title_zh") or items[0].get("title_en")

        async def events():
            answer_parts: list[str] = []
            try:
                async for chunk in provider.stream_chat(messages, temperature=0.2):
                    text = str(chunk or "")
                    if not text:
                        continue
                    answer_parts.append(text)
                    yield sse_event("delta", {"text": text})
            except AIProviderUnavailable as exc:
                yield sse_event("error", {"message": str(exc)})
                return
            result = finalize_streaming_answer(config, "".join(answer_parts), ranked_items)
            result["context_item_count"] = len(items)
            result["context_source"] = context_source
            try:
                conversation = store_ask_conversation(
                    config.db_path,
                    conversation_id=payload.conversation_id if existing_conversation else None,
                    question=payload.question,
                    answer=str(result.get("answer") or ""),
                    title=str(result.get("title") or ""),
                    scope_payload=scope_payload,
                    citations=list(result.get("citations") or []),
                    model=str(result.get("model") or config.ai_model),
                    context_source=context_source,
                    context_item_count=len(items),
                )
                result["history_saved"] = True
                result["conversation_id"] = conversation["conversation_id"]
                result["messages"] = conversation.get("messages", [])
                result["title"] = conversation.get("title") or result.get("title")
            except Exception:
                result["history_saved"] = False
            yield sse_event("done", result)

        return StreamingResponse(events(), media_type="text/event-stream")

    @app.post("/api/translate")
    async def translate(payload: TranslateRequest, session: dict = Depends(require_session)) -> dict:
        del session
        text = payload.text.strip()
        if not text:
            raise HTTPException(status_code=400, detail="No cleaned text to translate")
        try:
            provider = translation_provider(get_settings(config.db_path))
            translation = await translate_clean_text(config, text, source_language=payload.source_language, provider=provider)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except AIProviderUnavailable as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        return {"translation": translation, "model": provider.profile.get("model") or config.ai_model}

    @app.get("/api/ask/history")
    def ask_history(session: dict = Depends(require_session)) -> dict:
        del session
        return list_ask_conversations(config.db_path)

    @app.get("/api/ask/history/{conversation_id}")
    def ask_history_detail(conversation_id: str, session: dict = Depends(require_session)) -> dict:
        del session
        record = get_ask_conversation(config.db_path, conversation_id)
        if record is None:
            raise HTTPException(status_code=404, detail="Conversation not found")
        return record

    @app.delete("/api/ask/history/{conversation_id}")
    def delete_ask_history(conversation_id: str, session: dict = Depends(require_session)) -> dict:
        del session
        if not delete_ask_conversation(config.db_path, conversation_id):
            raise HTTPException(status_code=404, detail="Conversation not found")
        return {"ok": True}

    @app.put("/api/ask/history/{conversation_id}/messages/{message_id}")
    async def edit_ask_history_message(
        conversation_id: str,
        message_id: int,
        payload: AskMessageUpdateRequest,
        session: dict = Depends(require_session),
    ) -> dict:
        del session
        existing = get_ask_conversation(config.db_path, conversation_id)
        if existing is None:
            raise HTTPException(status_code=404, detail="Conversation not found")
        messages = list(existing.get("messages") or [])
        target_index = next((index for index, message in enumerate(messages) if message.get("id") == message_id), -1)
        if target_index < 0:
            raise HTTPException(status_code=404, detail="Message not found")
        if messages[target_index].get("role") != "user":
            raise HTTPException(status_code=400, detail="Only user messages can be edited")
        scope_payload = existing.get("scope_payload") or {}
        try:
            items, context_source = scoped_ask_items(scope_payload)
            items = attach_clean_article_context(scope_payload, items)
        except Exception as exc:
            raise HTTPException(status_code=503, detail=f"后端无法加载新闻数据: {exc}") from exc
        previous_messages = [
            {"role": message.get("role"), "content": message.get("content")}
            for message in messages[:target_index]
            if message.get("role") in {"user", "assistant"} and message.get("content")
        ]
        settings = get_settings(config.db_path)
        ask_system_prompt = str(settings.get("ask_system_prompt") or "")
        try:
            result = await answer_question(
                config,
                payload.content,
                items,
                conversation_messages=previous_messages,
                system_prompt=ask_system_prompt,
                provider=reading_assistant_provider(settings),
            )
        except AIProviderUnavailable as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        try:
            record = update_ask_message(config.db_path, conversation_id, message_id, payload.content)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        if record is None:
            raise HTTPException(status_code=404, detail="Message not found")
        updated = append_ask_assistant_response(
            config.db_path,
            conversation_id,
            answer=str(result.get("answer") or ""),
            citations=list(result.get("citations") or []),
            model=str(result.get("model") or config.ai_model),
            context_source=context_source,
            context_item_count=len(items),
        )
        if updated is None:
            raise HTTPException(status_code=404, detail="Conversation not found")
        return updated

    @app.delete("/api/ask/history/{conversation_id}/messages/{message_id}")
    def delete_ask_history_message(conversation_id: str, message_id: int, session: dict = Depends(require_session)) -> dict:
        del session
        record = delete_ask_message(config.db_path, conversation_id, message_id)
        if record is None:
            raise HTTPException(status_code=404, detail="Message not found")
        return record

    @app.post("/api/ask/history/{conversation_id}/messages/{message_id}/regenerate")
    async def regenerate_ask_history_message(conversation_id: str, message_id: int, session: dict = Depends(require_session)) -> dict:
        del session
        record = get_ask_conversation(config.db_path, conversation_id)
        if record is None:
            raise HTTPException(status_code=404, detail="Conversation not found")
        messages = list(record.get("messages") or [])
        target_index = next((index for index, message in enumerate(messages) if message.get("id") == message_id), -1)
        if target_index < 0:
            raise HTTPException(status_code=404, detail="Message not found")
        target = messages[target_index]
        if target.get("role") != "assistant":
            raise HTTPException(status_code=400, detail="Only assistant messages can be regenerated")
        user_index = next(
            (index for index in range(target_index - 1, -1, -1) if messages[index].get("role") == "user"),
            -1,
        )
        if user_index < 0:
            raise HTTPException(status_code=400, detail="No user message found for regeneration")
        scope_payload = record.get("scope_payload") or {}
        try:
            items, context_source = scoped_ask_items(scope_payload)
            items = attach_clean_article_context(scope_payload, items)
        except Exception as exc:
            raise HTTPException(status_code=503, detail=f"后端无法加载新闻数据: {exc}") from exc
        previous_messages = [
            {"role": message.get("role"), "content": message.get("content")}
            for message in messages[:user_index]
            if message.get("role") in {"user", "assistant"} and message.get("content")
        ]
        question = str(messages[user_index].get("content") or "")
        settings = get_settings(config.db_path)
        ask_system_prompt = str(settings.get("ask_system_prompt") or "")
        try:
            result = await answer_question(
                config,
                question,
                items,
                conversation_messages=previous_messages,
                system_prompt=ask_system_prompt,
                provider=reading_assistant_provider(settings),
            )
        except AIProviderUnavailable as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        updated = replace_ask_message(config.db_path, conversation_id, message_id, str(result.get("answer") or ""))
        if updated is None:
            raise HTTPException(status_code=404, detail="Message not found")
        updated["context_source"] = context_source
        updated["context_item_count"] = len(items)
        return updated

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
