import sqlite3

from server.ai_radar_api.db import connect_db, init_db


def test_init_db_creates_required_tables(tmp_path):
    db_path = tmp_path / "radar.db"
    init_db(db_path)

    with sqlite3.connect(db_path) as conn:
        tables = {
            row[0]
            for row in conn.execute(
                "select name from sqlite_master where type = 'table'"
            )
        }

    assert {
        "settings",
        "sessions",
        "taxonomy_categories",
        "item_classifications",
        "verification_results",
        "source_scores",
        "ask_conversations",
    }.issubset(tables)


def test_connect_db_uses_row_factory(tmp_path):
    db_path = tmp_path / "radar.db"
    init_db(db_path)
    with connect_db(db_path) as conn:
        conn.execute("insert into settings(key, value_json, updated_at) values (?, ?, ?)", ("x", "1", "now"))
        row = conn.execute("select key from settings where key = ?", ("x",)).fetchone()
    assert row["key"] == "x"
