# Track A targets (data and engine). Owned by Track A; each stub is replaced when the step is built.
A_TARGETS := fetch-smoke fetch parse lives bisect embed load checks align judge gloss eval m-lives atlas \
	sources-data dump release test-a

.PHONY: $(A_TARGETS)
$(A_TARGETS):
	@echo "$@: not built yet"; exit 1
