# Validio. Every command runs from validio/.
BACKEND := src/backend
UV := cd $(BACKEND) && uv run
RAW ?= $(HOME)/.claude/jobs/22b51af2/tmp/ch/vportal

.PHONY: setup data index seed test test-backend test-web test-live record guards dev ci agent types demo demo-check

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
	$(UV) ruff check validio tests ../../scripts
	$(UV) pytest -q

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
