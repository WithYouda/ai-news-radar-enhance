from server.ai_radar_api.config import AppConfig


def test_auth_router_exposes_auth_routes(tmp_path):
    from server.ai_radar_api.routers.auth import build_auth_router

    config = AppConfig(
        public_base_url="https://example.com/radar",
        allowed_origins=["https://example.com"],
        admin_password="pass",
        session_secret="test-secret",
        db_path=tmp_path / "radar.db",
        ai_base_url="https://api.example.com/v1",
        ai_api_key="sk-test",
        ai_model="test-model",
    )

    router = build_auth_router(config)
    routes = {(route.path, next(iter(route.methods))) for route in router.routes}

    assert ("/api/auth/login", "POST") in routes
    assert ("/api/auth/logout", "POST") in routes
    assert ("/api/me", "GET") in routes


def test_ai_profiles_router_exposes_profile_routes(tmp_path):
    from server.ai_radar_api.routers.ai_profiles import build_ai_profiles_router

    config = AppConfig(
        public_base_url="https://example.com/radar",
        allowed_origins=["https://example.com"],
        admin_password="pass",
        session_secret="test-secret",
        db_path=tmp_path / "radar.db",
        ai_base_url="https://api.example.com/v1",
        ai_api_key="sk-test",
        ai_model="test-model",
    )

    def allow_session() -> dict:
        return {"authenticated": True}

    router = build_ai_profiles_router(config, allow_session)
    routes = {(route.path, next(iter(route.methods))) for route in router.routes}

    assert ("/api/ai-profiles", "GET") in routes
    assert ("/api/ai-profiles", "POST") in routes
    assert ("/api/ai-profiles/{profile_id}", "PUT") in routes
    assert ("/api/ai-profiles/{profile_id}", "DELETE") in routes
    assert ("/api/ai-profiles/{profile_id}/test", "POST") in routes
