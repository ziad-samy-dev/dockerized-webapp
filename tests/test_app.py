"""Smoke tests for the Flask application.

The database is intentionally unavailable in CI, so these tests assert that the app
degrades gracefully instead of crashing when PostgreSQL cannot be reached.
"""

from app.app import app


def test_index_returns_200_without_database():
    """The status page must render even when the database is down."""
    client = app.test_client()
    response = client.get("/")
    assert response.status_code == 200
    assert b"dockerized-webapp" in response.data


def test_healthz_reports_liveness():
    client = app.test_client()
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.get_json() == {"status": "ok"}


def test_readyz_reports_database_state():
    """Readiness is either 200 (ready) or 503 (degraded) — never a 500."""
    client = app.test_client()
    response = client.get("/readyz")
    assert response.status_code in (200, 503)
    payload = response.get_json()
    assert payload["status"] in ("ready", "degraded")
    assert "database" in payload


def test_unhealthy_routes_are_not_exposed_by_mistake():
    client = app.test_client()
    assert client.get("/admin").status_code == 404
    assert client.get("/.env").status_code == 404
