# Track B targets (app). Owned by Track B; each stub is replaced when the step is built.
B_TARGETS := api web web-build test-b test-web e2e record-checks demo demo-check record deploy

.PHONY: $(B_TARGETS)
$(B_TARGETS):
	@echo "$@: not built yet"; exit 1
