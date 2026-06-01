from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from .db import connect_db


DEFAULT_TAXONOMY = [
    {
        "id": "models-products",
        "label": "模型与产品",
        "children": [
            {"id": "models-products/model-release", "label": "模型发布"},
            {"id": "models-products/product-features", "label": "产品功能"},
            {"id": "models-products/api-platform", "label": "API / 平台更新"},
            {"id": "models-products/multimodal", "label": "多模态能力"},
            {"id": "models-products/pricing-access", "label": "价格 / 访问权限"},
            {"id": "models-products/safety-policy", "label": "安全 / 策略更新"},
        ],
    },
    {
        "id": "agents-workflows",
        "label": "Agent 与工作流",
        "children": [
            {"id": "agents-workflows/agent-frameworks", "label": "Agent 框架"},
            {"id": "agents-workflows/tool-calling", "label": "工具调用 / Function Calling"},
            {"id": "agents-workflows/mcp-plugins", "label": "MCP / 插件生态"},
            {"id": "agents-workflows/browser-computer-control", "label": "浏览器 / 电脑控制"},
            {"id": "agents-workflows/multi-agent", "label": "多 Agent 协作"},
            {"id": "agents-workflows/automation", "label": "自动化工作流"},
        ],
    },
    {
        "id": "developer-tools",
        "label": "开发者工具",
        "children": [
            {"id": "developer-tools/ide-coding-assistants", "label": "IDE / 编程助手"},
            {"id": "developer-tools/sdk-api-tools", "label": "SDK / API 工具"},
            {"id": "developer-tools/rag-data-tools", "label": "RAG / 数据工具"},
            {"id": "developer-tools/deploy-ops", "label": "部署 / 运维"},
            {"id": "developer-tools/eval-monitoring", "label": "评测 / 监控"},
            {"id": "developer-tools/security-permissions", "label": "安全 / 权限"},
        ],
    },
    {
        "id": "open-source-projects",
        "label": "开源与项目",
        "children": [
            {"id": "open-source-projects/open-models", "label": "开源模型"},
            {"id": "open-source-projects/open-tools", "label": "开源工具"},
            {"id": "open-source-projects/github-projects", "label": "GitHub 项目"},
            {"id": "open-source-projects/frameworks-libraries", "label": "框架 / 库"},
            {"id": "open-source-projects/datasets", "label": "数据集"},
            {"id": "open-source-projects/demos-apps", "label": "Demo / 应用样例"},
        ],
    },
    {
        "id": "research-evaluation",
        "label": "研究与评测",
        "children": [
            {"id": "research-evaluation/papers", "label": "论文"},
            {"id": "research-evaluation/benchmarks", "label": "Benchmark"},
            {"id": "research-evaluation/model-evaluation", "label": "模型评测"},
            {"id": "research-evaluation/technical-reports", "label": "技术报告"},
            {"id": "research-evaluation/alignment-safety", "label": "对齐 / 安全研究"},
            {"id": "research-evaluation/robotics-embodied-ai", "label": "机器人 / 具身智能"},
        ],
    },
    {
        "id": "company-industry",
        "label": "公司与行业",
        "children": [
            {"id": "company-industry/funding-acquisitions", "label": "融资 / 收购"},
            {"id": "company-industry/partnership-ecosystem", "label": "合作 / 生态"},
            {"id": "company-industry/commercialization", "label": "商业化"},
            {"id": "company-industry/regulation-policy", "label": "监管 / 政策"},
            {"id": "company-industry/org-talent", "label": "组织 / 人才"},
            {"id": "company-industry/market-adoption", "label": "市场采用"},
        ],
    },
    {
        "id": "compute-infrastructure",
        "label": "算力与基础设施",
        "children": [
            {"id": "compute-infrastructure/gpu-chips", "label": "GPU / 芯片"},
            {"id": "compute-infrastructure/inference-services", "label": "推理服务"},
            {"id": "compute-infrastructure/training-infra", "label": "训练基础设施"},
            {"id": "compute-infrastructure/cloud-platforms", "label": "云平台"},
            {"id": "compute-infrastructure/data-center-energy", "label": "数据中心 / 能源"},
            {"id": "compute-infrastructure/local-edge-models", "label": "本地模型 / 边缘设备"},
        ],
    },
]


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _row_to_dict(row) -> dict:
    return {
        "id": row["id"],
        "label": row["label"],
        "parent_id": row["parent_id"],
        "priority": row["priority"],
        "enabled": bool(row["enabled"]),
        "rule_hints": json.loads(row["rule_hints_json"]),
        "updated_at": row["updated_at"],
    }


def seed_default_taxonomy(db_path: str | Path) -> None:
    timestamp = _now()
    with connect_db(db_path) as conn:
        for top_priority, category in enumerate(DEFAULT_TAXONOMY):
            conn.execute(
                """
                insert into taxonomy_categories(
                  id, label, parent_id, priority, enabled, rule_hints_json, updated_at
                )
                values (?, ?, ?, ?, ?, ?, ?)
                on conflict(id) do update set
                  label = excluded.label,
                  parent_id = excluded.parent_id,
                  priority = excluded.priority,
                  enabled = excluded.enabled,
                  rule_hints_json = excluded.rule_hints_json,
                  updated_at = excluded.updated_at
                """,
                (category["id"], category["label"], None, top_priority, 1, "[]", timestamp),
            )
            for child_priority, child in enumerate(category["children"]):
                conn.execute(
                    """
                    insert into taxonomy_categories(
                      id, label, parent_id, priority, enabled, rule_hints_json, updated_at
                    )
                    values (?, ?, ?, ?, ?, ?, ?)
                    on conflict(id) do update set
                      label = excluded.label,
                      parent_id = excluded.parent_id,
                      priority = excluded.priority,
                      enabled = excluded.enabled,
                      rule_hints_json = excluded.rule_hints_json,
                      updated_at = excluded.updated_at
                    """,
                    (child["id"], child["label"], category["id"], child_priority, 1, "[]", timestamp),
                )


def list_taxonomy(db_path: str | Path) -> list[dict]:
    with connect_db(db_path) as conn:
        rows = conn.execute(
            """
            select id, label, parent_id, priority, enabled, rule_hints_json, updated_at
            from taxonomy_categories
            order by
              case when parent_id is null then 0 else 1 end,
              priority,
              id
            """
        ).fetchall()
    return [_row_to_dict(row) for row in rows]
