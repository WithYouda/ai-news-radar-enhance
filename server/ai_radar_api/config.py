from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def _csv(value: str) -> list[str]:
    return [part.strip().rstrip("/") for part in value.split(",") if part.strip()]


@dataclass(frozen=True)
class AppConfig:
    public_base_url: str
    allowed_origins: list[str]
    admin_password: str
    session_secret: str
    db_path: Path
    ai_base_url: str
    ai_api_key: str
    ai_model: str
    ai_api_format: str = "chat_completions"
    max_context_items: int = 40
    deep_verify_top_n: int = 3
    data_dir: Path = Path("data")
    data_cache_dir: Path = Path("server/data/cache")

    @classmethod
    def from_env(cls) -> "AppConfig":
        public_base_url = os.getenv(
            "RADAR_PUBLIC_BASE_URL",
            "https://withyouda.github.io/ai-news-radar-enhance",
        ).rstrip("/")
        allowed_origins = _csv(os.getenv("RADAR_ALLOWED_ORIGINS", "https://withyouda.github.io"))
        return cls(
            public_base_url=public_base_url,
            allowed_origins=allowed_origins,
            admin_password=os.getenv("RADAR_ADMIN_PASSWORD", ""),
            session_secret=os.getenv("RADAR_SESSION_SECRET", ""),
            db_path=Path(os.getenv("RADAR_DB_PATH", "server/data/radar.db")),
            ai_base_url=os.getenv("AI_BASE_URL", "").rstrip("/"),
            ai_api_key=os.getenv("AI_API_KEY", ""),
            ai_model=os.getenv("AI_MODEL") or "gpt-4.1-mini",
            ai_api_format=(os.getenv("AI_API_FORMAT") or "chat_completions").strip().lower().replace("-", "_"),
            max_context_items=int(os.getenv("RADAR_MAX_CONTEXT_ITEMS", "40")),
            deep_verify_top_n=int(os.getenv("RADAR_DEEP_VERIFY_TOP_N", "3")),
            data_dir=Path(os.getenv("RADAR_DATA_DIR", "data")),
            data_cache_dir=Path(os.getenv("RADAR_DATA_CACHE_DIR", "server/data/cache")),
        )
