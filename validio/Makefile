# Validio. Every command runs from validio/.
BACKEND := src/backend
UV := cd $(BACKEND) && uv run
RAW ?= $(HOME)/.claude/jobs/22b51af2/tmp/ch/vportal

.PHONY: setup data index test test-live record guards dev ci

setup:
	[ -f .env ] || cp .env.example .env
	cd $(BACKEND) && uv sync --frozen
	$(MAKE) data index

data:
	$(UV) python ../../scripts/fetch_data.py --from-dir $(RAW)

index:
	$(UV) python ../../scripts/index_catalog.py

test: guards
	$(UV) ruff check validio tests ../../scripts
	$(UV) pytest -q

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
