from fastapi.testclient import TestClient

from app.main import app

DASHBOARD = "https://guardloop-iota.vercel.app"


def test_the_dashboard_origin_is_allowed():
    response = TestClient(app).get("/health", headers={"Origin": DASHBOARD})
    assert response.headers.get("access-control-allow-origin") == DASHBOARD


def test_local_development_origin_is_allowed():
    response = TestClient(app).get("/health", headers={"Origin": "http://localhost:3000"})
    assert response.headers.get("access-control-allow-origin") == "http://localhost:3000"


def test_an_unknown_origin_gets_no_cors_header():
    response = TestClient(app).get("/health", headers={"Origin": "https://evil.example.com"})
    assert "access-control-allow-origin" not in response.headers


def test_wildcard_is_no_longer_sent():
    response = TestClient(app).get("/health", headers={"Origin": "https://evil.example.com"})
    assert response.headers.get("access-control-allow-origin") != "*"


def test_preflight_allows_the_dashboards_auth_header():
    response = TestClient(app).options(
        "/ingest",
        headers={
            "Origin": DASHBOARD,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "authorization,content-type",
        },
    )
    assert response.status_code == 200
    assert "authorization" in response.headers["access-control-allow-headers"].lower()


def test_preflight_rejects_an_unknown_origin():
    response = TestClient(app).options(
        "/ingest",
        headers={
            "Origin": "https://evil.example.com",
            "Access-Control-Request-Method": "POST",
        },
    )
    assert "access-control-allow-origin" not in response.headers