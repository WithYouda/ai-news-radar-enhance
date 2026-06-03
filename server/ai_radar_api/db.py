from __future__ import annotations

import sqlite3
from pathlib import Path


SCHEMA = """
create table if not exists settings (
  key text primary key,
  value_json text not null,
  updated_at text not null
);

create table if not exists sessions (
  session_id_hash text primary key,
  expires_at text not null,
  created_at text not null
);

create table if not exists taxonomy_categories (
  id text primary key,
  label text not null,
  parent_id text,
  priority integer not null default 0,
  enabled integer not null default 1,
  rule_hints_json text not null default '[]',
  updated_at text not null
);

create table if not exists item_classifications (
  item_id text primary key,
  url text not null,
  title_hash text not null,
  top_category text not null,
  sub_category text,
  confidence real not null,
  reason text not null,
  taxonomy_version text not null,
  model text not null,
  manual_override_json text,
  classified_at text not null
);

create table if not exists verification_results (
  item_id text primary key,
  url text not null,
  status text not null,
  authority_score integer not null,
  authority_reason text not null,
  evidence_json text not null,
  deep_verified integer not null default 0,
  manual_score integer,
  manual_note text,
  model text not null,
  verified_at text not null
);

create table if not exists source_scores (
  source_id text primary key,
  source_name text not null,
  base_score integer not null default 50,
  ai_score integer,
  manual_score integer,
  reason text,
  updated_at text not null
);

create table if not exists ask_conversations (
  conversation_id text primary key,
  title text not null default '新的对话',
  question text not null,
  answer text not null,
  scope text not null,
  scope_json text not null,
  labels_json text not null,
  citations_json text not null,
  model text not null,
  context_source text,
  context_item_count integer not null default 0,
  created_at text not null,
  updated_at text not null
);

create table if not exists ask_messages (
  id integer primary key autoincrement,
  conversation_id text not null,
  role text not null,
  content text not null,
  created_at text not null,
  foreign key(conversation_id) references ask_conversations(conversation_id) on delete cascade
);

create index if not exists idx_ask_messages_conversation_id
on ask_messages(conversation_id, id);

create table if not exists article_cache (
  item_id text primary key,
  url text not null,
  final_url text not null,
  title text not null,
  site_name text,
  byline text,
  published_at text,
  excerpt text not null,
  text text not null,
  content_html text not null,
  fetched_at text not null
);

create index if not exists idx_article_cache_fetched_at
on article_cache(fetched_at);
"""


def connect_db(db_path: str | Path) -> sqlite3.Connection:
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(db_path: str | Path) -> None:
    with connect_db(db_path) as conn:
        conn.executescript(SCHEMA)
        columns = {
            row["name"]
            for row in conn.execute("pragma table_info(ask_conversations)").fetchall()
        }
        if "title" not in columns:
            conn.execute("alter table ask_conversations add column title text not null default '新的对话'")
