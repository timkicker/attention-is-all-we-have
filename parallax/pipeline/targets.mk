# Track A targets (data and engine). Owned by Track A.
TOPIC ?= winterwar
PY := $(UV) run python

A_STUBS := judge gloss eval atlas bench sources-data l-scale

.PHONY: fetch-smoke fetch parse lives bisect embed load checks align m-lives m-lives-load contested checks-write dump release test-a $(A_STUBS)

fetch-smoke:
	$(PY) -m pipeline.wapi

fetch:
	$(PY) -m pipeline.fetch --topic $(TOPIC)

parse:
	$(PY) -m pipeline.parse --topic $(TOPIC)

lives:
	$(PY) -m pipeline.lives --topic $(TOPIC)

bisect:
	$(PY) -m pipeline.bisect --topic $(TOPIC)

embed:
	$(PY) -m pipeline.embed --topic $(TOPIC)

load: db-reset
	$(PY) -m pipeline.load --topic $(TOPIC)

checks:
	$(PY) -m pipeline.checks

checks-write:
	$(PY) -m pipeline.checks --write

# mariadb-dump runs inside the db container (credentials from its own environment), so the host needs no client.
dump:
	mkdir -p data
	docker compose exec -T db sh -c 'mariadb-dump -u"$$MARIADB_USER" -p"$$MARIADB_PASSWORD" --dump-history --single-transaction "$$MARIADB_DATABASE"' | gzip > data/seed.sql.gz
	@ls -lh data/seed.sql.gz

release:
	$(PY) -m pipeline.checks > data/release-notes.txt
	gh release create parallax-seed-$(SEED) data/seed.sql.gz --title "seed $(SEED)" --notes-file data/release-notes.txt

test-a:
	$(UV) run pytest pipeline/tests engine/tests eval/tests -q

$(A_STUBS):
	@echo "$@: not built yet"; exit 1
align:
	$(PY) -m pipeline.align --topic $(TOPIC)

m-lives:
	$(PY) -m pipeline.m_lives

m-lives-load:
	$(PY) -m pipeline.m_lives --skip-parse

contested:
	$(PY) -m pipeline.contested

