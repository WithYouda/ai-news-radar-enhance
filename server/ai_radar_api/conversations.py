from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from .db import connect_db


SCOPE_LABELS = {
    "today": "今日",
    "categories": "分类",
    "verification": "核验",
    "settings": "设置",
}


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _json_loads(value: str, fallback):
    try:
        loaded = json.loads(value)
    except json.JSONDecodeError:
        return fallback
    return loaded if isinstance(loaded, type(fallback)) else fallback


def _answer_preview(answer: str, limit: int = 96) -> str:
    compact = " ".join(str(answer or "").split())
    if len(compact) <= limit:
        return compact
    return f"{compact[: limit - 1]}..."


def _conversation_title(title: str | None, answer: str) -> str:
    compact = " ".join(str(title or "").split())
    if compact:
        return compact[:64]
    return _answer_preview(answer, limit=40) or "新的对话"


def build_ask_labels(scope_payload: dict) -> list[str]:
    scope = str(scope_payload.get("scope") or "today")
    question = str(scope_payload.get("question") or "")
    labels = [SCOPE_LABELS.get(scope, scope or "今日")]

    category = str(scope_payload.get("category") or "").strip()
    if category:
        labels.append(f"分类: {category}")

    title = str(scope_payload.get("item_title") or "").strip()
    if title:
        labels.append(f"新闻: {title}")
    elif scope_payload.get("item_id"):
        labels.append("单篇新闻")

    if any(keyword in question for keyword in ("推荐", "哪个", "哪条", "最值得", "突破")):
        labels.append("推荐")
    if any(keyword in question for keyword in ("核验", "真假", "可靠吗", "可信")):
        labels.append("核验")
    if scope_payload.get("parent_conversation_id"):
        labels.append("追问")

    deduped = []
    for label in labels:
        if label and label not in deduped:
            deduped.append(label)
    return deduped


def _row_to_record(row, include_answer: bool = True) -> dict:
    record = {
        "conversation_id": row["conversation_id"],
        "title": row["title"],
        "question": row["question"],
        "scope": row["scope"],
        "scope_payload": _json_loads(row["scope_json"], {}),
        "labels": _json_loads(row["labels_json"], []),
        "citations": _json_loads(row["citations_json"], []),
        "model": row["model"],
        "context_source": row["context_source"],
        "context_item_count": row["context_item_count"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }
    if include_answer:
        record["answer"] = row["answer"]
    else:
        record["answer_preview"] = _answer_preview(row["answer"])
    return record


def _message_rows(conn, conversation_id: str) -> list[dict]:
    rows = conn.execute(
        """
        select role, content, created_at
        from ask_messages
        where conversation_id = ?
        order by id asc
        """,
        (conversation_id,),
    ).fetchall()
    return [
        {"role": row["role"], "content": row["content"], "created_at": row["created_at"]}
        for row in rows
    ]


def store_ask_conversation(
    db_path: str | Path,
    *,
    conversation_id: str | None = None,
    question: str,
    answer: str,
    title: str | None = None,
    scope_payload: dict,
    citations: list[dict],
    model: str,
    context_source: str | None,
    context_item_count: int,
) -> dict:
    now = _now()
    conversation_id = conversation_id or uuid4().hex
    stored_scope = {**scope_payload, "question": question}
    labels = build_ask_labels(stored_scope)
    scope = str(scope_payload.get("scope") or "today")
    display_title = _conversation_title(title, answer)

    with connect_db(db_path) as conn:
        existing = conn.execute(
            "select conversation_id from ask_conversations where conversation_id = ?",
            (conversation_id,),
        ).fetchone()
        is_append = bool(existing)
        if is_append:
            stored_scope["parent_conversation_id"] = conversation_id
            labels = build_ask_labels(stored_scope)
            conn.execute(
                """
                update ask_conversations
                set title = ?, question = ?, answer = ?, scope = ?, scope_json = ?,
                    labels_json = ?, citations_json = ?, model = ?, context_source = ?,
                    context_item_count = ?, updated_at = ?
                where conversation_id = ?
                """,
                (
                    display_title,
                    question,
                    answer,
                    scope,
                    json.dumps(stored_scope, ensure_ascii=False),
                    json.dumps(labels, ensure_ascii=False),
                    json.dumps(citations, ensure_ascii=False),
                    model,
                    context_source,
                    int(context_item_count),
                    now,
                    conversation_id,
                ),
            )
        else:
            conn.execute(
                """
                insert into ask_conversations(
                  conversation_id, title, question, answer, scope, scope_json, labels_json,
                  citations_json, model, context_source, context_item_count, created_at, updated_at
                )
                values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    conversation_id,
                    display_title,
                    question,
                    answer,
                    scope,
                    json.dumps(stored_scope, ensure_ascii=False),
                    json.dumps(labels, ensure_ascii=False),
                    json.dumps(citations, ensure_ascii=False),
                    model,
                    context_source,
                    int(context_item_count),
                    now,
                    now,
                ),
            )
        conn.executemany(
            """
            insert into ask_messages(conversation_id, role, content, created_at)
            values (?, ?, ?, ?)
            """,
            (
                (conversation_id, "user", question, now),
                (conversation_id, "assistant", answer, now),
            ),
        )

    record = get_ask_conversation(db_path, conversation_id)
    if record is None:
        raise RuntimeError("Stored Ask AI conversation could not be read back")
    return record


def list_ask_conversations(db_path: str | Path, limit: int = 50) -> dict:
    with connect_db(db_path) as conn:
        rows = conn.execute(
            """
            select conversation_id, title, question, answer, scope, scope_json, labels_json,
                   citations_json, model, context_source, context_item_count, created_at, updated_at
            from ask_conversations
            order by updated_at desc
            limit ?
            """,
            (int(limit),),
        ).fetchall()
    return {"items": [_row_to_record(row, include_answer=False) for row in rows]}


def get_ask_conversation(db_path: str | Path, conversation_id: str) -> dict | None:
    with connect_db(db_path) as conn:
        row = conn.execute(
            """
            select conversation_id, title, question, answer, scope, scope_json, labels_json,
                   citations_json, model, context_source, context_item_count, created_at, updated_at
            from ask_conversations
            where conversation_id = ?
            """,
            (conversation_id,),
        ).fetchone()
        if not row:
            return None
        record = _row_to_record(row)
        messages = _message_rows(conn, conversation_id)
        if not messages:
            messages = [
                {"role": "user", "content": record["question"], "created_at": record["created_at"]},
                {"role": "assistant", "content": record["answer"], "created_at": record["updated_at"]},
            ]
        record["messages"] = messages
        return record


def delete_ask_conversation(db_path: str | Path, conversation_id: str) -> bool:
    with connect_db(db_path) as conn:
        conn.execute("delete from ask_messages where conversation_id = ?", (conversation_id,))
        cursor = conn.execute("delete from ask_conversations where conversation_id = ?", (conversation_id,))
    return cursor.rowcount > 0
