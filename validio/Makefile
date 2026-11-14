# Validio. Every command runs from validio/.
BACKEND := src/backend
UV := cd $(BACKEND) && uv run
# the raw Valio export (fetch_data.py --from-dir); set RAW=... to point elsewhere
RAW ?= data/raw

.PHONY: setup data index seed test test-backend test-web test-live record guards dev ci agent types demo demo-mock demo-check template demo-web demo-smoke e2e-live accounts-e2e a11y snapshots video revoke mutate modal-data modal-secret modal-deploy modal-seed modal-fill

setup:
	[ -f .env ] || cp .env.example .env
	cd $(BACKEND) && uv sync --frozen
	cd src/frontend && sh scripts/fetch-ui-kit.sh && npm ci
	$(MAKE) data index

data:
	$(UV) python ../../scripts/fetch_data.py --from-dir $(abspath $(RAW))

index:
	$(UV) python ../../scripts/index_catalog.py

seed:
	$(UV) python ../../scripts/seed_demo.py

test: test-backend test-web

test-backend: guards
	$(UV) ruff check validio tests ../../scripts ../../examples
	cd $(BACKEND) && REQUIRE_DATA=1 uv run pytest -q

test-web:
	cd src/frontend && npm run check && npx playwright test
	$(MAKE) accounts-e2e

# mutation testing on the deciding modules, see docs/TESTING.md (slow: one worker)
mutate:
	bash scripts/mutate.sh $(MUTATE)

types:
	$(UV) python ../../scripts/export_openapi.py

test-live:
	$(UV) pytest -q -m live

record:
	cd $(BACKEND) && VALIO_MODE=record uv run python ../../scripts/record_valio.py

guards:
	bash scripts/check_no_secrets.sh
	bash scripts/check_forbidden_hosts.sh

dev:
	$(UV) env VALIDIO_DEMO=1 uvicorn validio.api.app:app --host 127.0.0.1 --port 8410 --reload

ci: test

SCENE ?= 2
agent:
	$(UV) python -W ignore ../../scripts/agent.py --scene $(SCENE)

# The demo on 127.0.0.1:8410 from replayed Valio answers: web app built, store seeded.
demo:
	cd src/frontend && VITE_API=live npm run build
	$(MAKE) seed
	cd $(BACKEND) && VALIO_MODE=replay VALIDIO_DEMO=1 uv run uvicorn validio.api.app:app --host 127.0.0.1 --port 8410

# The web app alone on its recorded answers (src/lib/api/snapshots/states.ts), no backend: the
# sidebar says "Demo data". Never for the 10:00 run, which is `make demo`.
demo-mock:
	cd src/frontend && npm run build && npx vite preview --host 127.0.0.1 --port 8411 --strictPort

DEMO_SCENES ?= 1,2,3,4,5
# Revoke a Spend Pass early, e.g. make revoke PASS=M-1 (a reset issues the demo pass again)
revoke:
	@test -n "$(PASS)" || { echo "usage: make revoke PASS=M-1"; exit 2; }
	$(UV) python ../../scripts/revoke_pass.py $(PASS)

demo-check:
	$(UV) python -W ignore ../../scripts/demo_check.py --scenes $(DEMO_SCENES)

# The filled demo kitchen every account is copied from (docs/ACCOUNTS-API.md): the five scenes, one round,
# into data/template/. Without it a new account starts from a plain seed.
template:
	$(UV) python -W ignore ../../scripts/demo_check.py --rounds 1 --template --store $(abspath data/template)

# Backend on 127.0.0.1:8410 plus the web app's dev server on 127.0.0.1:5410 with VITE_API=live
# (Vite hands /api and /agent to the backend). The web client sends no approve code
# yet, so this local run switches it off; Ctrl-C stops both.
demo-web:
	$(MAKE) seed
	trap 'kill 0' INT TERM EXIT; \
	(cd $(BACKEND) && VALIO_MODE=replay VALIDIO_DEMO=1 VALIDIO_APPROVE_CODE= \
	  uv run uvicorn validio.api.app:app --host 127.0.0.1 --port 8410) & \
	(cd src/frontend && VITE_API=live npm run dev)

# Every /api answer the web app reads, after each demo scene, into src/frontend/src/lib/api/snapshots;
# `npm run check` then types them against types.ts.
snapshots:
	$(UV) python -W ignore ../../scripts/snapshot_api.py

# The public-deploy shape in a browser: one FastAPI process serves the built app and the API (no Vite),
# the real agent places scenes 2 and 3, the owner approves on the phone view. Port SMOKE_PORT (8416).
demo-smoke:
	cd src/frontend && VITE_API=live npm run build && npx playwright test -c playwright.live.config.ts

# The 10:00 click-through of docs/DEMO.md in a browser against the live backend: built app and API from
# one process on E2E_PORT (8419), approve code on, the real agent for scenes 1 to 3. A page without the
# data-testid a check needs makes that check a fixme (E2E_STRICT=1 makes it fail).
e2e-live:
	cd src/frontend && VITE_API=live npm run build && npx playwright test -c e2e-live/demo.config.ts

# The accounts plan's "Done means" in a fresh browser against the real backend (port ACCOUNTS_PORT, 8417):
# demo kitchen, connect the demo agent, example ordered, lower Rules, wait, approve, pause, refusal, diet.
accounts-e2e:
	cd src/frontend && npx playwright test -c playwright.accounts.config.ts

# Accessibility over every route at 1280 and 390 px, light and dark: axe-core WCAG 2.2 AA (contrast
# included), visible focus, 44 px targets on the phone, keyboard-only approve, renew and accept.
# Port A11Y_PORT (8420). Prints the findings per page; fails when there are any.
a11y:
	cd src/frontend && VITE_API=live npm run build && \
	{ npx playwright test -c a11y/a11y.config.ts; s=$$?; node a11y/summary.mjs ../../artifacts/a11y/results; exit $$s; }

# A scripted recording of the five scenes for the demo video: agent terminal left, web app right,
# 1920x1080, headless Firefox, its own server on a free port with replayed Valio answers. Writes
# artifacts/video/validio-demo.webm (and .mp4 with ffmpeg). Nothing is uploaded.
video:
	cd src/frontend && npx playwright install firefox
	$(UV) python -W ignore ../../scripts/record_video.py

# Validio on Modal (step 19). The volume holds the Valio data, never the image or git. Seed and fill call
# the deployed functions; fill runs before the first visit, so no web container holds an older store.
MODAL := cd $(BACKEND) && uv run --extra cloud modal

modal-data:
	$(MODAL) volume create validio-data 2>/dev/null || true
	$(MODAL) volume put --force validio-data ../../data/catalog.db /catalog.db
	$(MODAL) volume put --force validio-data ../../data/cache/valio /cache/valio

# the env file behind the secret: gitignored, mode 600
MODAL_SECRETS ?= .modal-secrets.env
modal-secret:
	@MODAL_SECRETS=$(abspath $(MODAL_SECRETS)) bash scripts/modal_secret.sh

modal-deploy:
	cd src/frontend && sh scripts/fetch-ui-kit.sh && npm ci --silent && VITE_API=live npm run build
	$(MODAL) deploy ../cloud/app_validio.py
	$(MAKE) modal-fill

modal-seed:
	cd $(BACKEND) && uv run --extra cloud python -c "import modal; print(modal.Function.from_name('validio-web', 'seed').remote())"

modal-fill:
	cd $(BACKEND) && uv run --extra cloud python -c "import modal; print(modal.Function.from_name('validio-web', 'fill').remote())"
