"""Minimal Flask app used to demonstrate containerization with Docker Compose."""

import os

import psycopg2
from flask import Flask, jsonify, render_template

app = Flask(__name__)

DB_CONFIG = {
    "dbname": os.getenv("POSTGRES_DB", "webapp"),
    "user": os.getenv("POSTGRES_USER", "webapp"),
    "password": os.getenv("POSTGRES_PASSWORD", "webapp"),
    "host": os.getenv("POSTGRES_HOST", "db"),
    "port": os.getenv("POSTGRES_PORT", "5432"),
}


def db_status():
    """Return (reachable, details) without ever crashing the request."""
    try:
        conn = psycopg2.connect(**DB_CONFIG, connect_timeout=3)
        with conn.cursor() as cur:
            cur.execute("SELECT version();")
            version = cur.fetchone()[0]
        conn.close()
        return True, version.split(",")[0]
    except (psycopg2.OperationalError, psycopg2.Error) as exc:
        return False, str(exc).split("\n")[0]


@app.route("/")
def index():
    connected, detail = db_status()
    return render_template(
        "index.html",
        db_connected=connected,
        db_detail=detail,
        hostname=os.getenv("HOSTNAME", "unknown"),
        environment=os.getenv("APP_ENV", "development"),
    )


@app.route("/healthz")
def healthz():
    """Liveness endpoint used by Docker HEALTHCHECK and load balancers."""
    return jsonify(status="ok"), 200


@app.route("/readyz")
def readyz():
    """Readiness endpoint: only 200 when the app can reach its database."""
    connected, detail = db_status()
    payload = {"status": "ready" if connected else "degraded", "database": detail}
    return jsonify(payload), 200 if connected else 503


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)))
