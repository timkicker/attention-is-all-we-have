# Track B targets (app). Owned by Track B; each stub is replaced when the step is built.
API_PORT ?= 8000
B_STUBS := record deploy
BASE_URL ?=

.PHONY: api test-b web web-build test-web e2e record-checks demo demo-check $(B_STUBS)

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

# Check every answer of contract/fixtures/answers.json once with ENGINE (real after M2) and store it as recorded.
# RECORD_ARGS=--fixture records the fake engine's example answer instead.
record-checks:
	$(UV) run python -m api.record_checks $(RECORD_ARGS)

# Playwright against the API serving web/dist on E2E_PORT (default 8010) with seed-mini in its own database
# parallax_e2e (see e2e/playwright.config.ts); E2E_URL for a running instance.
# The demo walk (@demo) runs through make demo-check.
e2e: web-build
	cd e2e && npx playwright test --workers 2 --grep-invert @demo

# The demo on the loaded seed: build the web app, record the example answers once, serve on API_PORT.
# Without contract/fixtures/answers.json (A15) the fake engine's example answer is recorded.
demo: web-build
	$(UV) run python -m api.record_checks --if-empty $(if $(wildcard contract/fixtures/answers.json),,--fixture)
	$(UV) run uvicorn api.main:app --host 127.0.0.1 --port $(API_PORT)

# Walk the demo script (PLAN section 0) against make demo, or against BASE_URL=https://... for a deployed instance.
demo-check:
	cd e2e && E2E_URL=$(or $(BASE_URL),http://127.0.0.1:$(API_PORT)) npx playwright test demo.spec.ts --workers 1 --reporter=./demo-reporter.ts

$(B_STUBS):
	@echo "$@: not built yet"; exit 1
