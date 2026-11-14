# Track B targets (app). Owned by Track B; each stub is replaced when the step is built.
API_PORT ?= 8000
B_STUBS := e2e record-checks demo demo-check record deploy

.PHONY: api test-b web web-build test-web $(B_STUBS)

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

$(B_STUBS):
	@echo "$@: not built yet"; exit 1
