from server.ai_radar_api.db import init_db
from server.ai_radar_api.taxonomy import DEFAULT_TAXONOMY, list_taxonomy, seed_default_taxonomy


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
