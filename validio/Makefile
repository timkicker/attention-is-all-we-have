# Validio. Every command runs from validio/.
BACKEND := src/backend
UV := cd $(BACKEND) && uv run
RAW ?= $(HOME)/.claude/jobs/22b51af2/tmp/ch/vportal

.PHONY: setup data index seed test test-backend test-web test-live record guards dev ci agent types demo demo-check demo-web demo-smoke snapshots

setup:
	[ -f .env ] || cp .env.example .env
	cd $(BACKEND) && uv sync --frozen
	cd src/frontend && sh scripts/fetch-ui-kit.sh && npm ci
	$(MAKE) data index

data:
	$(UV) python ../../scripts/fetch_data.py --from-dir $(RAW)

index:
	$(UV) python ../../scripts/index_catalog.py

seed:
	$(UV) python ../../scripts/seed_demo.py

test: test-backend test-web

test-backend: guards
	$(UV) ruff check validio tests ../../scripts ../../examples
	cd $(BACKEND) && REQUIRE_DATA=1 uv run pytest -q

test-web:
	cd src/frontend && npm run check && npx playwright test

types:
	$(UV) python ../../scripts/export_openapi.py

test-live:
	$(UV) pytest -q -m live

record:
	cd $(BACKEND) && VALIO_MODE=record uv run python ../../scripts/record_valio.py

guards:
	bash scripts/check_no_secrets.sh
	bash scripts/check_forbidden_hosts.sh

dev:
	$(UV) uvicorn validio.api.app:app --host 127.0.0.1 --port 8410 --reload

ci: test

SCENE ?= 2
agent:
	$(UV) python -W ignore ../../scripts/agent.py --scene $(SCENE)

# The demo on 127.0.0.1:8410 from replayed Valio answers: web app built, store seeded.
demo:
	cd src/frontend && VITE_API=live npm run build
	$(MAKE) seed
	cd $(BACKEND) && VALIO_MODE=replay uv run uvicorn validio.api.app:app --host 127.0.0.1 --port 8410

DEMO_SCENES ?= 1,2,3,4,5
demo-check:
	$(UV) python -W ignore ../../scripts/demo_check.py --scenes $(DEMO_SCENES)

# Backend on 127.0.0.1:8410 plus the web app's dev server on 127.0.0.1:5410 with VITE_API=live
# (Vite hands /api and /agent to the backend). The web client sends no approve code or demo token
# yet, so this local run switches both off; Ctrl-C stops both.
demo-web:
	$(MAKE) seed
	trap 'kill 0' INT TERM EXIT; \
	(cd $(BACKEND) && VALIO_MODE=replay VALIDIO_APPROVE_CODE= VALIDIO_DEMO_TOKEN= \
	  uv run uvicorn validio.api.app:app --host 127.0.0.1 --port 8410) & \
	(cd src/frontend && VITE_API=live npm run dev)

# Every /api answer the web app reads, after each demo scene, into src/frontend/src/lib/api/snapshots;
# `npm run check` then types them against types.ts.
snapshots:
	$(UV) python -W ignore ../../scripts/snapshot_api.py

# The public-deploy shape in a browser: one FastAPI process serves the built app and the API (no Vite),
# the real agent places scenes 2 and 3, the owner approves on the phone view. Port SMOKE_PORT (8416).
demo-smoke:
	cd src/frontend && VITE_API=live npm run build && npx playwright test -c playwright.live.config.ts
