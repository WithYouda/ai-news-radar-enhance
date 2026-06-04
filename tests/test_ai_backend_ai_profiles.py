import json

import pytest

from server.ai_radar_api.ai_profiles import (
    delete_ai_profile,
    get_ai_profile_for_use,
    list_ai_profiles,
    save_ai_profile,
)
from server.ai_radar_api.config import AppConfig
from server.ai_radar_api.db import connect_db, init_db


def _config(tmp_path, encryption_key="test-master-key"):
    return AppConfig(
        public_base_url="https://withyouda.github.io/ai-news-radar-enhance",
        allowed_origins=["https://withyouda.github.io"],
        admin_password="pass",
        session_secret="session-secret",
        db_path=tmp_path / "radar.db",
        ai_base_url="https://env.example.com/v1",
        ai_api_key="sk-env",
        ai_model="env-model",
        encryption_key=encryption_key,
    )


def _raw_profile(config, profile_id):
    with connect_db(config.db_path) as conn:
        return conn.execute("select * from ai_provider_profiles where id = ?", (profile_id,)).fetchone()


def test_profile_secrets_are_encrypted_and_sanitized(tmp_path):
    config = _config(tmp_path)
    init_db(config.db_path)

    saved = save_ai_profile(
        config,
        {
            "name": "Translation AI",
            "type": "chat_completions",
            "base_url": "https://api.example.com/v1",
            "model": "gpt-4.1-mini",
            "api_key": "sk-secret",
            "headers_json": json.dumps({"X-Test": "secret-header"}),
            "timeout_seconds": 45,
        },
    )

    raw = _raw_profile(config, saved["id"])
    assert raw is not None
    assert "sk-secret" not in raw["api_key_encrypted"]
    assert "secret-header" not in raw["headers_encrypted"]

    public = list_ai_profiles(config)
    assert public == [
        {
            "id": saved["id"],
            "name": "Translation AI",
            "type": "chat_completions",
            "base_url": "https://api.example.com/v1",
            "model": "gpt-4.1-mini",
            "has_api_key": True,
            "headers_preview": ["X-Test"],
            "timeout_seconds": 45,
            "enabled": True,
            "readonly": False,
        }
    ]
    assert "api_key" not in public[0]
    assert "headers_json" not in public[0]


def test_missing_encryption_key_rejects_new_secret(tmp_path):
    config = _config(tmp_path, encryption_key="")
    init_db(config.db_path)

    with pytest.raises(ValueError, match="RADAR_ENCRYPTION_KEY"):
        save_ai_profile(
            config,
            {
                "name": "Bad",
                "type": "chat_completions",
                "base_url": "https://api.example.com/v1",
                "model": "gpt-4.1-mini",
                "api_key": "sk-secret",
            },
        )


def test_update_profile_with_blank_key_preserves_existing_key(tmp_path):
    config = _config(tmp_path)
    init_db(config.db_path)
    saved = save_ai_profile(
        config,
        {
            "name": "Reader AI",
            "type": "responses",
            "base_url": "https://api.example.com/v1",
            "model": "old-model",
            "api_key": "sk-old",
            "headers_json": json.dumps({"X-Trace": "old-secret"}),
        },
    )

    updated = save_ai_profile(
        config,
        {
            "id": saved["id"],
            "name": "Reader AI Updated",
            "type": "responses",
            "base_url": "https://api.example.com/v1",
            "model": "new-model",
            "api_key": "",
            "headers_json": "",
            "timeout_seconds": 30,
        },
    )

    profile = get_ai_profile_for_use(config, updated["id"])
    assert profile["api_key"] == "sk-old"
    assert profile["headers"] == {"X-Trace": "old-secret"}
    assert profile["model"] == "new-model"
    assert profile["timeout_seconds"] == 30


def test_invalid_headers_json_is_rejected(tmp_path):
    config = _config(tmp_path)
    init_db(config.db_path)

    with pytest.raises(ValueError, match="headers_json"):
        save_ai_profile(
            config,
            {
                "name": "Bad Headers",
                "type": "chat_completions",
                "base_url": "https://api.example.com/v1",
                "model": "gpt-4.1-mini",
                "headers_json": "{not-json",
            },
        )


def test_environment_profile_is_available_when_no_stored_profiles(tmp_path):
    config = _config(tmp_path)
    init_db(config.db_path)

    profiles = list_ai_profiles(config)

    assert profiles == [
        {
            "id": "env",
            "name": "环境变量 AI",
            "type": "chat_completions",
            "base_url": "https://env.example.com/v1",
            "model": "env-model",
            "has_api_key": True,
            "headers_preview": [],
            "timeout_seconds": 45,
            "enabled": True,
            "readonly": True,
        }
    ]


def test_delete_profile_removes_stored_secret(tmp_path):
    config = _config(tmp_path)
    init_db(config.db_path)
    saved = save_ai_profile(
        config,
        {
            "name": "Delete Me",
            "type": "chat_completions",
            "base_url": "https://api.example.com/v1",
            "model": "gpt-4.1-mini",
            "api_key": "sk-delete",
        },
    )

    assert delete_ai_profile(config, saved["id"]) is True
    assert get_ai_profile_for_use(config, saved["id"]) is None
