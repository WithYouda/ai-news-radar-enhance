from __future__ import annotations

import json
import re

from .config import AppConfig
from .provider import AIProvider
from .radar_data import build_context, rank_context_items


def format_conversation_history(conversation_messages: list[dict] | None) -> str:
    lines = []
    for message in conversation_messages or []:
        role = message.get("role")
        content = str(message.get("content") or "").strip()
        if not content:
            continue
        label = "用户" if role == "user" else "助手" if role == "assistant" else ""
        if label:
            lines.append(f"{label}：{content}")
    return "\n".join(lines[-12:])


def build_ask_messages(question: str, context: str, conversation_messages: list[dict] | None = None) -> list[dict]:
    messages = [
        {
            "role": "system",
            "content": (
                "你是 AI News Radar 的阅读助手。只能基于给定上下文回答。"
                "先识别用户问题中的主体、公司、产品或分类，只使用和问题直接相关的上下文。"
                "可以使用历史对话回答关于本对话的问题，也可以用历史对话理解追问里的指代。"
                "不要在回答末尾追加链接列表、推荐链接或无关链接。"
                "如果证据不足或不知道，请明确说不知道或信息不足。"
                "回答必须是 JSON 对象，字段为 title 和 answer。"
                "title 是 8 到 18 个中文字符的对话标题，由你根据本轮回答生成，不要照抄用户问题。"
                "answer 可以使用 Markdown。"
            ),
        },
    ]
    for message in conversation_messages or []:
        role = message.get("role")
        content = str(message.get("content") or "").strip()
        if role in {"user", "assistant"} and content:
            messages.append({"role": role, "content": content})
    history = format_conversation_history(conversation_messages)
    history_block = f"\n\n历史对话：\n{history}" if history else ""
    messages.append(
        {
            "role": "user",
            "content": f"问题：{question}{history_block}\n\n新闻上下文：\n{context}",
        }
    )
    return messages


def _strip_json_fence(text: str) -> str:
    stripped = text.strip()
    match = re.fullmatch(r"```(?:json)?\s*(.*?)\s*```", stripped, flags=re.S)
    return match.group(1).strip() if match else stripped


def _fallback_title(answer: str) -> str:
    lines = []
    for raw in str(answer or "").splitlines():
        line = re.sub(r"^\s{0,3}#{1,6}\s*", "", raw).strip()
        line = re.sub(r"^\s*[-*+]\s+", "", line).strip()
        line = re.sub(r"^\s*\d+[.)]\s+", "", line).strip()
        line = re.sub(r"[*_`>\[\]()]+", "", line).strip()
        if line:
            lines.append(line)
        if len(lines) >= 2:
            break
    title = " - ".join(lines) if lines else "新的 AI 对话"
    return title[:64]


def parse_answer_payload(raw: str) -> tuple[str, str]:
    stripped = _strip_json_fence(raw)
    try:
        payload = json.loads(stripped)
    except json.JSONDecodeError:
        return raw, _fallback_title(raw)
    if not isinstance(payload, dict):
        return raw, _fallback_title(raw)
    answer = str(payload.get("answer") or "").strip() or raw
    title = str(payload.get("title") or "").strip() or _fallback_title(answer)
    return answer, title[:64]


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
    conversation_messages: list[dict] | None = None,
) -> dict:
    provider = provider or AIProvider(config)
    ranked_items = relevant_context_items(items, question)
    context = build_context(ranked_items, question=question, max_items=config.max_context_items)
    messages = build_ask_messages(question, context, conversation_messages=conversation_messages)
    raw_answer = await provider.chat(messages, temperature=0.2)
    answer, title = parse_answer_payload(raw_answer)
    return {
        "answer": answer,
        "title": title,
        "citations": [],
        "model": config.ai_model,
    }
