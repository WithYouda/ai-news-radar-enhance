from pathlib import Path

from server.ai_radar_api.config import AppConfig


def test_config_reads_openai_compatible_env(monkeypatch, tmp_path):
    monkeypatch.setenv("RADAR_PUBLIC_BASE_URL", "https://withyouda.github.io/ai-news-radar-enhance")
    monkeypatch.setenv("RADAR_ALLOWED_ORIGINS", "https://withyouda.github.io,https://example.com")
    monkeypatch.setenv("RADAR_ADMIN_PASSWORD", "secret-pass")
    monkeypatch.setenv("RADAR_SESSION_SECRET", "session-secret")
    monkeypatch.setenv("RADAR_DB_PATH", str(tmp_path / "radar.db"))
    monkeypatch.setenv("AI_BASE_URL", "https://api.example.com/v1")
    monkeypatch.setenv("AI_API_KEY", "sk-test")
    monkeypatch.setenv("AI_MODEL", "test-model")

    config = AppConfig.from_env()

    assert config.public_base_url == "https://withyouda.github.io/ai-news-radar-enhance"
    assert config.allowed_origins == ["https://withyouda.github.io", "https://example.com"]
    assert config.admin_password == "secret-pass"
    assert config.session_secret == "session-secret"
    assert config.db_path == Path(tmp_path / "radar.db")
    assert config.ai_base_url == "https://api.example.com/v1"
    assert config.ai_api_key == "sk-test"
    assert config.ai_model == "test-model"


def test_config_has_safe_defaults(monkeypatch):
    for key in [
        "RADAR_PUBLIC_BASE_URL",
        "RADAR_ALLOWED_ORIGINS",
        "RADAR_ADMIN_PASSWORD",
        "RADAR_SESSION_SECRET",
        "RADAR_DB_PATH",
        "AI_BASE_URL",
        "AI_API_KEY",
        "AI_MODEL",
    ]:
        monkeypatch.delenv(key, raising=False)

    config = AppConfig.from_env()

    assert config.public_base_url == "https://withyouda.github.io/ai-news-radar-enhance"
    assert config.allowed_origins == ["https://withyouda.github.io"]
    assert config.db_path.as_posix().endswith("server/data/radar.db")
    assert config.ai_model == "gpt-4.1-mini"


def test_empty_ai_model_env_uses_default(monkeypatch):
    monkeypatch.setenv("AI_MODEL", "")

    config = AppConfig.from_env()

    assert config.ai_model == "gpt-4.1-mini"
