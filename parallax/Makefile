# Parallax shared targets (contract). Track A owns pipeline/targets.mk, Track B owns api/targets.mk.
SHELL := /bin/bash
SEED ?= v4
UV ?= uv
LOAD := $(UV) run python scripts/load_sql.py

.PHONY: db-up db-down db-reset seed seed-mini test-contract lint check-rules test

db-up:
	docker compose up -d --wait db

db-down:
	docker compose down

db-reset:
	$(LOAD) --reset contract/schema.sql

data/seed-$(SEED).sql.gz:
	mkdir -p data
	gh release download parallax-seed-$(SEED) -p seed.sql.gz -O $@

seed: data/seed-$(SEED).sql.gz
	$(LOAD) --reset data/seed-$(SEED).sql.gz

seed-mini:
	$(LOAD) --reset contract/schema.sql contract/fixtures/seed-mini.sql

test-contract:
	$(UV) run pytest tests/contract -q

lint:
	$(UV) run ruff check .
	$(UV) run ruff format --check .

check-rules:
	$(UV) run python scripts/check_rules.py

test: test-contract test-a test-b

include pipeline/targets.mk
include api/targets.mk
