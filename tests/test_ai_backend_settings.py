from server.ai_radar_api.db import init_db
from server.ai_radar_api.settings import get_settings, update_settings


def test_settings_default_deep_verification_is_limited(tmp_path):
    db_path = tmp_path / "radar.db"
    init_db(db_path)

    settings = get_settings(db_path)

    assert settings["deep_verification_enabled"] is False
    assert settings["deep_verification_scope"] == "bole_picks_and_topic_top_n"
    assert settings["deep_verification_top_n"] == 3
    assert settings["ask_streaming_enabled"] is False
    assert "ask_system_prompt" in settings
    assert "AI News Radar" in settings["ask_system_prompt"]


def test_update_settings_persists_values(tmp_path):
    db_path = tmp_path / "radar.db"
    init_db(db_path)

    update_settings(db_path, {"deep_verification_enabled": True, "deep_verification_top_n": 2})
    settings = get_settings(db_path)

    assert settings["deep_verification_enabled"] is True
    assert settings["deep_verification_top_n"] == 2


def test_update_settings_persists_ask_system_prompt(tmp_path):
    db_path = tmp_path / "radar.db"
    init_db(db_path)

    update_settings(db_path, {"ask_system_prompt": "你是严格的新闻编辑。"})
    settings = get_settings(db_path)

    assert settings["ask_system_prompt"] == "你是严格的新闻编辑。"


def test_update_settings_persists_ask_streaming_toggle(tmp_path):
    db_path = tmp_path / "radar.db"
    init_db(db_path)

    update_settings(db_path, {"ask_streaming_enabled": True})
    settings = get_settings(db_path)

    assert settings["ask_streaming_enabled"] is True
