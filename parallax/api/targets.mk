# Track B targets (app). Owned by Track B; each stub is replaced when the step is built.
API_PORT ?= 8000
B_STUBS := web web-build test-web e2e record-checks demo demo-check record deploy

.PHONY: api test-b $(B_STUBS)

api:
	$(UV) run uvicorn api.main:app --host 127.0.0.1 --port $(API_PORT)

test-b:
	$(UV) run pytest api/tests -q

$(B_STUBS):
	@echo "$@: not built yet"; exit 1
