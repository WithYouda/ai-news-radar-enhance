from __future__ import annotations

import re


RULES = {
    "模型与产品": {
        "模型发布": ("model", "gpt", "claude", "gemini", "llama", "deepseek", "release", "releases", "发布"),
        "产品功能": ("feature", "features", "product", "app", "功能", "产品"),
        "API / 平台更新": ("api", "platform", "endpoint", "sdk", "developer platform", "平台"),
        "多模态能力": ("multimodal", "vision", "audio", "video", "image", "多模态", "语音", "视觉"),
        "价格 / 访问权限": ("pricing", "price", "subscription", "access", "rate limit", "价格", "订阅", "权限"),
        "安全 / 策略更新": ("safety", "policy", "guardrail", "alignment", "安全", "策略"),
    },
    "Agent 与工作流": {
        "Agent 框架": ("agent", "agents", "framework", "langgraph", "autogen", "框架"),
        "工具调用 / Function Calling": ("tool calling", "function calling", "function", "tools", "工具调用"),
        "MCP / 插件生态": ("mcp", "plugin", "plugins", "插件"),
        "浏览器 / 电脑控制": ("browser", "computer control", "desktop", "浏览器", "电脑控制"),
        "多 Agent 协作": ("multi-agent", "multi agent", "swarm", "多 agent", "协作"),
        "自动化工作流": ("workflow", "automation", "automate", "工作流", "自动化"),
    },
    "开发者工具": {
        "IDE / 编程助手": ("ide", "coding", "code", "codex", "copilot", "编程"),
        "SDK / API 工具": ("sdk", "api", "client", "library", "工具"),
        "RAG / 数据工具": ("rag", "retrieval", "vector", "embedding", "data", "数据"),
        "部署 / 运维": ("deploy", "deployment", "ops", "infra", "运维", "部署"),
        "评测 / 监控": ("eval", "evaluation", "monitoring", "tracing", "observability", "评测", "监控"),
        "安全 / 权限": ("security", "permission", "auth", "安全", "权限"),
    },
    "开源与项目": {
        "开源模型": ("open model", "weights", "开源模型"),
        "开源工具": ("open source tool", "oss", "开源工具"),
        "GitHub 项目": ("github", "repo", "repository", "项目"),
        "框架 / 库": ("framework", "library", "框架", "库"),
        "数据集": ("dataset", "datasets", "数据集"),
        "Demo / 应用样例": ("demo", "sample", "example", "应用样例"),
    },
    "研究与评测": {
        "论文": ("paper", "arxiv", "论文"),
        "Benchmark": ("benchmark", "bench", "leaderboard"),
        "模型评测": ("model evaluation", "eval", "评测"),
        "技术报告": ("technical report", "report", "技术报告"),
        "对齐 / 安全研究": ("alignment", "safety research", "对齐", "安全研究"),
        "机器人 / 具身智能": ("robot", "robotics", "embodied", "具身", "机器人"),
    },
    "公司与行业": {
        "融资 / 收购": ("funding", "acquisition", "raises", "融资", "收购"),
        "合作 / 生态": ("partner", "partnership", "ecosystem", "合作", "生态"),
        "商业化": ("revenue", "business", "commercial", "商业化"),
        "监管 / 政策": ("regulation", "policy", "law", "监管", "政策"),
        "组织 / 人才": ("hire", "team", "talent", "组织", "人才"),
        "市场采用": ("adoption", "customer", "enterprise", "采用"),
    },
    "算力与基础设施": {
        "GPU / 芯片": ("gpu", "chip", "nvidia", "amd", "芯片"),
        "推理服务": ("inference", "serving", "推理"),
        "训练基础设施": ("training", "cluster", "训练"),
        "云平台": ("cloud", "云"),
        "数据中心 / 能源": ("data center", "energy", "数据中心", "能源"),
        "本地模型 / 边缘设备": ("local model", "edge", "device", "本地", "边缘"),
    },
}


def _text(item: dict) -> str:
    fields = (item.get("title"), item.get("source"), item.get("site_name"), item.get("summary"))
    return " ".join(str(field) for field in fields if field).lower()


def _keyword_hits(text: str, keywords: tuple[str, ...]) -> list[str]:
    hits = []
    for keyword in keywords:
        pattern = re.escape(keyword.lower())
        if re.search(pattern, text):
            hits.append(keyword)
    return hits


def classify_item(item: dict, taxonomy: list[dict]) -> dict:
    text = _text(item)
    best = ("开发者工具", "SDK / API 工具", 0, [])
    for top_category, sub_rules in RULES.items():
        for sub_category, keywords in sub_rules.items():
            hits = _keyword_hits(text, keywords)
            score = len(hits)
            if top_category == "Agent 与工作流" and sub_category == "MCP / 插件生态" and "mcp" in hits:
                score += 3
            if score > best[2]:
                best = (top_category, sub_category, score, hits)

    top_category, sub_category, score, hits = best
    if score == 0:
        hits = ["fallback"]
    confidence = min(0.95, 0.45 + 0.15 * max(score, 1))
    return {
        "top_category": top_category,
        "sub_category": sub_category,
        "confidence": confidence,
        "reason": f"matched keywords: {', '.join(hits)}",
        "model": "rules-v1",
    }
