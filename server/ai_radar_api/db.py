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
