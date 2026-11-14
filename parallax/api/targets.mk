# Track B targets (app). Owned by Track B; each stub is replaced when the step is built.
API_PORT ?= 8000
B_STUBS := demo demo-check record deploy

.PHONY: api test-b web web-build test-web e2e record-checks $(B_STUBS)

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

# Playwright against the API serving web/dist on E2E_PORT (default 8000) with the loaded seed; E2E_URL for a remote.
e2e: web-build
	cd e2e && npx playwright test --workers 2

$(B_STUBS):
	@echo "$@: not built yet"; exit 1
