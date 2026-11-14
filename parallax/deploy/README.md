# Deploy

The demo runs on one Verda CPU instance (4 vCPU, 16 GB, Ubuntu 24.04) with Docker: `db` (mariadb:12.3.3 with `db/my.cnf`), `api` (uvicorn serving the built `web/dist`, see `Dockerfile`) and `caddy` with HTTPS on `DOMAIN`, for example `<ip>.sslip.io`.

`.env` next to `Makefile` on the server holds `DB_PASSWORD`, `ENGINE=fake`, `SEED=v4`, `DOMAIN` and, for live Check only, `GEMINI_API_KEY`. It is copied over SSH and never committed.

```
make deploy HOST=root@<ip>          # rsync the repo, build and start the stack
```

Loading the seed on the server, once per fresh database (`data/seed-v4.sql.gz` copied there first):

```
C="docker compose -f deploy/docker-compose.prod.yml --env-file .env"
$C up -d --wait db
$C run --rm -T api uv run --no-sync python scripts/load_sql.py --reset data/seed-v4.sql.gz
```

Recorded answers: run `ENGINE=real make record-checks` where the embedding backend is reachable, or load the `check_run` and `check_claim` rows with `source='recorded'` from a database that has them. Then:

```
curl -s https://<ip>.sslip.io/api/health      # seed v4
BASE_URL=https://<ip>.sslip.io make demo-check
```
