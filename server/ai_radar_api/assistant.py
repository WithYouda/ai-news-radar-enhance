from __future__ import annotations

import re

from .config import AppConfig
from .provider import AIProvider
from .radar_data import build_context, rank_context_items


MAX_CITATIONS = 8


def build_ask_messages(question: str, context: str) -> list[dict]:
    return [
        {
            "role": "system",
            "content": (
                "你是 AI News Radar 的阅读助手。只能基于给定上下文回答。"
                "先识别用户问题中的主体、公司、产品或分类，只使用和问题直接相关的上下文。"
                "回答必须包含引用，引用要能对应上下文中的 URL，不能引用无关链接。"
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


def _question_keywords(question: str) -> set[str]:
    generic = {"今天", "今日", "有什么", "哪些", "什么", "消息", "新闻", "更新", "总结", "重要"}
    return {
        part.lower()
        for part in re.findall(r"[\w\u4e00-\u9fff]+", question or "")
        if len(part) > 1 and part.lower() not in generic
    }


def _item_search_text(item: dict) -> str:
    fields = (
        item.get("title"),
        item.get("title_zh"),
        item.get("title_en"),
        item.get("site_name"),
        item.get("source"),
        item.get("url"),
    )
    return " ".join(str(field) for field in fields if field).lower()


def relevant_context_items(items: list[dict], question: str) -> list[dict]:
    ranked_items = rank_context_items(items, question)
    keywords = _question_keywords(question)
    if not keywords:
        return ranked_items
    matched = [item for item in ranked_items if any(keyword in _item_search_text(item) for keyword in keywords)]
    return matched or ranked_items


async def answer_question(
    config: AppConfig,
    question: str,
    items: list[dict],
    provider: AIProvider | None = None,
) -> dict:
    provider = provider or AIProvider(config)
    ranked_items = relevant_context_items(items, question)
    context = build_context(ranked_items, question=question, max_items=config.max_context_items)
    messages = build_ask_messages(question, context)
    answer = await provider.chat(messages, temperature=0.2)
    return {
        "answer": answer,
        "citations": _citations(ranked_items, min(MAX_CITATIONS, config.max_context_items)),
        "model": config.ai_model,
    }
