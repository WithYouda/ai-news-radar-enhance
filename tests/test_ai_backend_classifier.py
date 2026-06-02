from server.ai_radar_api.classifier import classify_item
from server.ai_radar_api.taxonomy import DEFAULT_TAXONOMY


def test_classifies_model_release():
    result = classify_item(
        {"title": "OpenAI releases GPT-5 API and pricing", "source": "OpenAI News"},
        DEFAULT_TAXONOMY,
    )
    assert result["top_category"] == "模型与产品"
    assert result["sub_category"] in {"模型发布", "API / 平台更新", "价格 / 访问权限"}
    assert result["confidence"] >= 0.6


def test_classifies_mcp_agent_workflow():
    result = classify_item(
        {"title": "New MCP plugin lets agents call browser tools", "source": "GitHub"},
        DEFAULT_TAXONOMY,
    )
    assert result["top_category"] == "Agent 与工作流"
    assert result["sub_category"] == "MCP / 插件生态"


def test_falls_back_to_developer_tools():
    result = classify_item(
        {"title": "New SDK adds tracing and monitoring for RAG apps", "source": "Blog"},
        DEFAULT_TAXONOMY,
    )
    assert result["top_category"] == "开发者工具"


def test_classifier_does_not_emit_categories_outside_taxonomy():
    taxonomy = [
        {
            "id": "research-evaluation",
            "label": "研究与评测",
            "children": [{"id": "research-evaluation/papers", "label": "论文"}],
        }
    ]
    result = classify_item({"title": "OpenAI releases GPT-5 API", "source": "OpenAI News"}, taxonomy)

    assert result["top_category"] == "研究与评测"
    assert result["sub_category"] == "论文"
