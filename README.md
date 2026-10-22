# Berlin Stats

REST API over two public datasets from the Berlin police website:

- **Police reports** (*Polizeimeldungen*) – full text, district, timestamp
- **Registered demonstrations** (*Versammlungen & Aufzüge*) – date, time, topic, location, route

A background job scrapes both sources once a day, stores only new records in PostgreSQL and exposes them via a searchable API.

```
berlin.de ──scrape (daily)──▶ FastAPI app ──▶ PostgreSQL
                                  ▲
                    search / update endpoints (Swagger at /docs)
```

## Stack

Python 3.12 · FastAPI · psycopg 3 (+pool) · BeautifulSoup · PostgreSQL 16 · Docker · GitHub Actions → ghcr.io · k3s (Raspberry Pi 5, Traefik)

## Features

- Daily polling inside the app (`asyncio` task, no external scheduler); interval configurable.
- Safe with several replicas: a PostgreSQL advisory lock ensures only one replica polls at a time.
- Idempotent inserts (`ON CONFLICT DO NOTHING` on unique indexes); already known reports are not re-downloaded.
- Resilient scraper: User-Agent, timeouts, retries with backoff; failed pages are skipped and retried on the next run.
- Case-insensitive keyword search with `LIMIT`/`OFFSET` pagination and escaped `LIKE` wildcards.
- Manual update endpoints protected by a shared secret header.
- CI: lint + tests against a real PostgreSQL service, then an arm64 image is built and pushed to GHCR.

## API

| Method | Path | Description |
|---|---|---|
| GET | `/police_report_by_keyword/{keyword}` | Search in report text |
| GET | `/meeting_by_keyword/{keyword}` | Search demonstrations by topic |
| GET | `/meeting_by_keyword_and_datum/{keyword}/{datum}` | Same, for a date (`DD.MM.YYYY`) |
| GET | `/update_polizei`, `/update_meetings` | Trigger a scrape now (header `X-Password`) |
| GET/HEAD | `/health` | Liveness/readiness |

Search endpoints accept `limit` (1–500, default 100) and `offset`. Interactive docs: `/docs`.

```bash
curl "http://localhost:8000/meeting_by_keyword/klima?limit=5"
curl -H "X-Password: change-me" http://localhost:8000/update_meetings
```

## Run locally

With Docker:

```bash
cp .env.example .env        # set POSTGRES_PASSWORD
docker compose up --build   # API on http://localhost:8000, first poll runs on startup
```

Without Docker (needs a PostgreSQL):

```bash
cp .env.example .env        # set DATABASE_URL and SECRET_PASSWORD
pip install -r requirements.txt
uvicorn main:app --reload
```

### Configuration

| Variable | Default | Description |
|---|---|---|
| `DATABASE_URL` | – (required) | PostgreSQL connection string |
| `SECRET_PASSWORD` | – | Value of `X-Password` for update endpoints; if unset they always return 401 |
| `POLL_INTERVAL_HOURS` | `24` | Poll period |
| `POLL_ON_STARTUP` | `true` | Poll immediately at start |
| `CORS_ORIGINS` | `*` | Comma-separated allowed origins |
| `ROOT_PATH` | empty | URL prefix behind a reverse proxy (e.g. `/berlin-stats`) |

## Tests

```bash
pip install -r requirements-dev.txt
docker run -d -p 5432:5432 -e POSTGRES_HOST_AUTH_METHOD=trust postgres:16
DATABASE_URL=postgresql://postgres@localhost:5432/postgres pytest
ruff check .
```

Parsers are tested on saved HTML fixtures (no network). DB and API tests use a real PostgreSQL and are skipped if none is reachable.

## Deployment (k3s)

Every push to `main` runs tests and publishes `ghcr.io/<owner>/berlin_stats:{latest,<sha>}` (linux/arm64). Manifests live in [`k8s/`](k8s):

- `postgres.yaml` – shared PostgreSQL 16 (namespace `postgres`, StatefulSet, 5Gi PVC). Each application gets its own role and database.
- `manifest.yaml` – namespace, Service, Traefik strip-prefix Middleware + Ingress (`/berlin-stats`), Deployment with 3 replicas.

Secrets are never stored in the repo:

```bash
kubectl create namespace postgres
kubectl -n postgres create secret generic postgres-auth --from-literal=POSTGRES_PASSWORD=...
kubectl apply -f k8s/postgres.yaml
kubectl -n postgres exec -i postgres-0 -- psql -U postgres \
  -c "CREATE ROLE berlin_stats LOGIN PASSWORD '...'" \
  -c "CREATE DATABASE berlin_stats OWNER berlin_stats"

kubectl create namespace berlin-stats
kubectl -n berlin-stats create secret generic berlin-stats-db \
  --from-literal=DATABASE_URL='postgresql://berlin_stats:...@postgres.postgres.svc.cluster.local:5432/berlin_stats'
kubectl -n berlin-stats create secret generic berlin-stats --from-literal=SECRET_PASSWORD=...
kubectl -n berlin-stats create secret docker-registry ghcr-secret \
  --docker-server=ghcr.io --docker-username=<user> --docker-password=<PAT with read:packages>
kubectl apply -f k8s/manifest.yaml
kubectl -n berlin-stats rollout restart deployment/berlin-stats   # pull a new image
```

Adapt to your environment: image name, the `/berlin-stats` prefix, `ghcr-secret` (not needed for a public package).

## Future work

- Scheduled `pg_dump` backups (CronJob)
- Prometheus metrics for poll results
- Rate limiting; public access via Cloudflare Tunnel
- Full-text search (`tsvector`) instead of `ILIKE`
- Parse dates into proper `date`/`timestamp` columns
