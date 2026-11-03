# dockerized-webapp

A small three-service web application packaged with **Docker** and orchestrated with
**Docker Compose**: a Flask API, a PostgreSQL database, and an Nginx reverse proxy
terminating all inbound traffic.

![CI](https://github.com/ziad-samy-dev/dockerized-webapp/actions/workflows/ci.yml/badge.svg)

---

## Architecture

```
                       ┌──────────────────────────────────────────────┐
   Browser ── :80 ───▶ │  nginx  (nginx:1.27-alpine)                 │
                       │  gzip · security headers · proxy headers    │
                       └───────────────────┬──────────────────────────┘
                                           │ proxy_pass → app:5000
                       ┌───────────────────▼──────────────────────────┐
                       │  app  (python:3.12-slim, non-root user)     │
                       │  Flask + Gunicorn · /healthz · /readyz      │
                       └───────────────────┬──────────────────────────┘
                                           │ TCP 5432 (private network)
                       ┌───────────────────▼──────────────────────────┐
                       │  db  (postgres:16-alpine)                   │
                       │  named volume db_data · pg_isready health   │
                       └──────────────────────────────────────────────┘

   Only `nginx` publishes a host port. `app` and `db` stay on the
   internal Compose network and are unreachable from outside.
```

## Tech stack

| Layer    | Tool                                            |
| -------- | ----------------------------------------------- |
| Runtime  | Docker (multi-stage build), Docker Compose      |
| App      | Python 3.12, Flask, Gunicorn                    |
| Database | PostgreSQL 16                                   |
| Proxy    | Nginx                                           |
| Quality  | Ruff, Pytest, Trivy (via GitHub Actions)        |

## Getting started

```bash
git clone https://github.com/ziad-samy-dev/dockerized-webapp.git
cd dockerized-webapp

cp .env.example .env        # then edit the password

docker compose up --build
# open http://localhost
```

Tear everything down while keeping the database data:

```bash
docker compose down            # stop and remove containers
docker compose down -v         # also remove the db_data volume
```

## Health checks

| Endpoint   | Meaning                                                |
| ---------- | ------------------------------------------------------ |
| `/healthz` | Liveness — is the process up? Used by `HEALTHCHECK`.   |
| `/readyz`  | Readiness — returns `200` only when PostgreSQL responds. |

```bash
curl -i http://localhost/healthz
curl -i http://localhost/readyz
docker compose ps        # watch the health status column
```

## Project structure

```
dockerized-webapp/
├── app/
│   ├── app.py                 # Flask routes + DB connectivity check
│   ├── templates/index.html   # server-rendered status page
│   └── requirements.txt       # pinned, reproducible dependencies
├── tests/test_app.py          # Pytest smoke tests (degraded-mode assertions)
├── nginx/default.conf         # reverse proxy configuration
├── Dockerfile                 # multi-stage build, non-root runtime
├── docker-compose.yml         # app + db + nginx, health-gated startup
├── pyproject.toml             # Ruff + Pytest configuration
├── requirements-dev.txt       # lint and test dependencies only
├── .env.example               # documented configuration
├── .dockerignore              # keeps secrets and junk out of the image
└── .github/workflows/ci.yml   # lint → test → build → Trivy scan
```

## Design decisions

- **Multi-stage build** — the builder stage installs dependencies into a venv, so the
  final image contains no compilers, caches or build tooling.
- **Non-root user** (`appuser`, UID 10001) — the runtime process never needs root.
- **Only the proxy publishes a port** — `app` and `db` are reachable only on the
  internal Compose network, which limits the attack surface.
- **Health-gated startup** — `app` waits for `db` to pass `pg_isready`, so the first
  request does not race the database.
- **Secrets stay in `.env`** — git-ignored, documented in `.env.example`, never baked
  into an image layer (`.dockerignore` excludes it).

## What I learned

- Ordering services with `depends_on: condition: service_healthy` instead of a sleep.
- The difference between liveness and readiness probes and why both matter.
- Why `.dockerignore` is a security control, not just a build-time optimisation.
- How image size and attack surface drop when the build toolchain stays in stage 1.

## CI/CD

Every push to `main` runs two jobs on GitHub Actions:

1. **Lint & test** — `ruff check`, then `pytest` on Python 3.12 with pip caching.
2. **Build image & Trivy scan** — builds the multi-stage image and scans it for
   HIGH/CRITICAL OS and library vulnerabilities, ignoring findings with no fix
   available.

The status badge at the top of this file reflects the latest run.

## Roadmap

- [x] Add CI: Ruff → Pytest → image build → Trivy scan (GitHub Actions)
- [ ] Gate the pipeline on the Trivy report (`exit-code: 1`) and triage findings
- [ ] Publish the image to Docker Hub / GHCR
- [ ] Push `db_data` to a managed database and run Compose in a remote environment
- [ ] Add Prometheus metrics and a Grafana dashboard

## License

MIT — see [LICENSE](LICENSE).
