from server.ai_radar_api.db import init_db
from server.ai_radar_api.config import AppConfig
from server.ai_radar_api.main import create_app
from server.ai_radar_api.taxonomy import DEFAULT_TAXONOMY, list_taxonomy, seed_default_taxonomy
from fastapi.testclient import TestClient


def test_seed_default_taxonomy_contains_seven_top_level_categories(tmp_path):
    db_path = tmp_path / "radar.db"
    init_db(db_path)
    seed_default_taxonomy(db_path)

    taxonomy = list_taxonomy(db_path)

    assert [row["label"] for row in taxonomy if row["parent_id"] is None] == [
        "模型与产品",
        "Agent 与工作流",
        "开发者工具",
        "开源与项目",
        "研究与评测",
        "公司与行业",
        "算力与基础设施",
    ]
    assert any(row["label"] == "MCP / 插件生态" for row in taxonomy)
    assert DEFAULT_TAXONOMY[0]["children"][0]["label"] == "模型发布"


def test_taxonomy_endpoint_is_public(tmp_path):
    config = AppConfig(
        public_base_url="https://withyouda.github.io/ai-news-radar-enhance",
        allowed_origins=["https://withyouda.github.io"],
        admin_password="pass",
        session_secret="test-session-secret",
        db_path=tmp_path / "radar.db",
        ai_base_url="https://api.example.com/v1",
        ai_api_key="sk-test",
        ai_model="test-model",
    )
    client = TestClient(create_app(config), base_url="https://testserver")

    res = client.get("/api/taxonomy")

    assert res.status_code == 200
    assert any(row["label"] == "模型与产品" for row in res.json()["categories"])
