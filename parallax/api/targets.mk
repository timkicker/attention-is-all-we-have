# Track B targets (app). Owned by Track B; each stub is replaced when the step is built.
API_PORT ?= 8000
B_STUBS := record
HOST ?=
BASE_URL ?=

.PHONY: api test-b web web-build test-web e2e record-checks app-stats demo demo-check deploy $(B_STUBS)

api:
	$(UV) run uvicorn api.main:app --host 127.0.0.1 --port $(API_PORT)

test-b:
	$(UV) run pytest api/tests -q

web:
	cd web && npm run dev

web-build:
	cd web && npm run build

test-web:
	cd web && npm test

# Check every answer of contract/fixtures/answers.json once with ENGINE and store it as recorded (again: replaces).
# RECORD_ARGS=--fixture records the fake engine's example answer instead.
record-checks:
	$(UV) run python -m api.record_checks $(RECORD_ARGS)

# Playwright against the API serving web/dist on E2E_PORT (default 8057) with seed-mini in its own database
# parallax_e2e (see e2e/playwright.config.ts); E2E_URL for a running instance.
# The demo walk (@demo) runs through make demo-check.
e2e: web-build
	cd e2e && npx playwright test --workers 1 --grep-invert @demo

# The stat keys the app reads (Under the hood, the Finnish scale line in Removed), on a restored seed.
app-stats:
	$(UV) run python -m pipeline.seed_stats --app-keys

# The demo on the loaded seed: build the web app, check the AI answers of contract/fixtures/answers.json once with
# the real engine (GEMINI_API_KEY in .env) unless the database holds recorded answers, serve on API_PORT.
demo: web-build app-stats
	ENGINE=real $(UV) run python -m api.record_checks --if-empty
	$(UV) run uvicorn api.main:app --host 127.0.0.1 --port $(API_PORT)

# Walk the demo script (PLAN section 0) against make demo, or against BASE_URL=https://... for a deployed instance.
# First step without BASE_URL: write the app stat keys into the local database (make app-stats).
demo-check: $(if $(BASE_URL),,app-stats)
	cd e2e && E2E_URL=$(or $(BASE_URL),http://127.0.0.1:$(API_PORT)) npx playwright test demo.spec.ts --workers 1 --reporter=./demo-reporter.ts

# Copy the repo to HOST (root@<ip>) and start deploy/docker-compose.prod.yml there; .env and the seed stay on the server.
# The ingest file adds a writable data/ and the ollama sidecar; pull bge-m3 once: $(C) exec ollama ollama pull bge-m3
deploy:
	test -n "$(HOST)"
	rsync -az --exclude .venv --exclude node_modules --exclude data --exclude .env ./ $(HOST):/opt/parallax/
	ssh $(HOST) 'cd /opt/parallax && docker compose -f deploy/docker-compose.prod.yml -f deploy/docker-compose.ingest.yml --env-file .env up -d --build'
	ssh $(HOST) 'cd /opt/parallax && docker compose -f deploy/docker-compose.prod.yml -f deploy/docker-compose.ingest.yml --env-file .env exec -T api uv run --no-sync python -m pipeline.seed_stats --app-keys'

$(B_STUBS):
	@echo "$@: not built yet"; exit 1
