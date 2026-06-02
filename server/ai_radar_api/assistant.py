from __future__ import annotations

from .config import AppConfig
from .provider import AIProvider
from .radar_data import build_context


def build_ask_messages(question: str, context: str) -> list[dict]:
    return [
        {
            "role": "system",
            "content": (
                "你是 AI News Radar 的阅读助手。只能基于给定上下文回答。"
                "回答必须包含引用，引用要能对应上下文中的 URL。"
                "如果证据不足或不知道，请明确说不知道或信息不足。"
            ),
        },
        {
            "role": "user",
            "content": f"问题：{question}\n\n上下文：\n{context}",
        },
    ]


def _citations(items: list[dict], max_items: int) -> list[dict]:
    citations = []
    for item in items[:max_items]:
        url = item.get("url")
        if not url:
            continue
        citations.append({"title": item.get("title") or item.get("title_zh") or "Untitled", "url": url})
    return citations


async def answer_question(
    config: AppConfig,
    question: str,
    items: list[dict],
    provider: AIProvider | None = None,
) -> dict:
    provider = provider or AIProvider(config)
    context = build_context(items, question=question, max_items=config.max_context_items)
    messages = build_ask_messages(question, context)
    answer = await provider.chat(messages, temperature=0.2)
    return {
        "answer": answer,
        "citations": _citations(items, config.max_context_items),
        "model": config.ai_model,
    }
