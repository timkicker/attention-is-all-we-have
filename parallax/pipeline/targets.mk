# Track A targets (data and engine). Owned by Track A.
TOPIC ?= winterwar
PY := $(UV) run python

A_STUBS := bisect embed load checks align judge gloss eval m-lives contested atlas bench \
	sources-data l-scale dump release

.PHONY: fetch-smoke fetch parse lives test-a $(A_STUBS)

fetch-smoke:
	$(PY) -m pipeline.wapi

fetch:
	$(PY) -m pipeline.fetch --topic $(TOPIC)

parse:
	$(PY) -m pipeline.parse --topic $(TOPIC)

lives:
	$(PY) -m pipeline.lives --topic $(TOPIC)

test-a:
	$(UV) run pytest pipeline/tests engine/tests eval/tests -q

$(A_STUBS):
	@echo "$@: not built yet"; exit 1
