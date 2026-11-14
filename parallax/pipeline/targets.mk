# Track A targets (data and engine). Owned by Track A.
TOPIC ?= winterwar
PY := $(UV) run python

A_STUBS := fetch parse lives bisect embed load checks align judge gloss eval m-lives contested atlas bench \
	sources-data l-scale dump release

.PHONY: fetch-smoke test-a $(A_STUBS)

fetch-smoke:
	$(PY) -m pipeline.wapi

test-a:
	$(UV) run pytest pipeline/tests engine/tests eval/tests -q

$(A_STUBS):
	@echo "$@: not built yet"; exit 1
