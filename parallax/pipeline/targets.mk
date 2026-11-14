# Track A targets (data and engine). Owned by Track A.
TOPIC ?= winterwar
PY := $(UV) run python

.PHONY: fetch-smoke fetch parse lives bisect embed load reload checks checks-write dump release test-a align m-lives \
	m-lives-load contested m-embed judge gloss gloss-fill gloss-dump gloss-load atlas sources-data gold label eval answers bench l-scale docs ingest prepare

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

# Swap one topic's rows in a restored seed (make seed SEED=...) and keep everything else.
reload:
	$(PY) -m pipeline.load --topic $(TOPIC) --replace

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

align:
	$(PY) -m pipeline.align --topic $(TOPIC)

m-lives:
	$(PY) -m pipeline.m_lives

m-lives-load:
	$(PY) -m pipeline.m_lives --skip-parse

contested:
	$(PY) -m pipeline.contested

m-embed:
	$(PY) -m pipeline.m_embed --pages 100

SCOPE ?= demo
judge:
	$(PY) -m pipeline.judge --topic $(TOPIC) --scope $(SCOPE)

gloss:
	$(PY) -m pipeline.gloss --topic $(TOPIC)

# English glosses for everything the UI shows (dropped rows, past dates, timelines). Needs ENGINE=real and the key.
gloss-fill:
	$(PY) -m pipeline.gloss_fill --topic $(TOPIC)

# Carry the glosses to a server that holds the same seed, without calling the model again.
gloss-dump:
	mkdir -p data
	$(PY) -m pipeline.gloss_fill --topic $(TOPIC) --dump data/gloss-$(TOPIC).sql.gz

gloss-load:
	$(LOAD) $(FILE)

atlas:
	$(PY) -m pipeline.atlas

sources-data:
	$(PY) -m pipeline.sources --topic $(TOPIC)

gold:
	$(PY) -m eval.gold

LABELLER ?= human
label:
	$(PY) -m eval.label --labeller $(LABELLER)

JUDGE_PROMPTS ?= judge-v1
eval:
	$(PY) -m eval.score --judge $(JUDGE_PROMPTS)

answers:
	$(PY) -m pipeline.record_answers

bench:
	$(PY) -m pipeline.bench

l-scale:
	$(PY) -m pipeline.l_scale

docs:
	$(PY) -m pipeline.docs


# Any-article ingest (pipeline/job.py) without the API: one Wikidata item, or several one after another.
# Resumable: finished editions and loaded topics are skipped. Prints the model calls per item and in total.
# SINCE=2021-01-01 keeps only the history from that date on.
ingest:
	$(PY) -m pipeline.job $(QID) $(if $(SINCE),--since $(SINCE))

prepare:
	$(PY) -m pipeline.job $(QIDS) $(if $(SINCE),--since $(SINCE))
