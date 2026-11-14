# Testing

Every command runs from `validio/`. `make test` runs the backend and the web app; on a shared machine, run heavy
commands one at a time.

## The suites

| Suite | Where | Command | What it shows |
|---|---|---|---|
| Unit | `src/backend/tests/test_*.py` | `make test-backend` | One module or route at a time: need matching, Best Pick, Fact Grades, Hard Lines, Spend Pass, ledger, order service, agent API and MCP, Valio client. Starts with the guard checks and ruff. |
| Scenes | `scripts/demo_check.py`, scene tests in `test_api.py`, `test_mcp.py`, `test_agent.py` | `make demo-check` | The five demo scenes end to end through the agent API from a reset, two rounds, no key and no network. Ends with ALL SCENES OK. |
| Adversarial | `src/backend/tests/adversarial/` | part of `make test-backend` | Attacks and properties: Cedar invariants (hypothesis), Spend Pass fuzzing, a prompt-injection corpus, a ledger tamper matrix, approve abuse and races, the webshop guard, and the tests written against surviving mutants (`test_mutants_*.py`). A real bug found here is an `xfail(strict=True)` with the finding in the review notes, never a silent pass. |
| Synthetic | `src/backend/tests/test_synthetic.py`, `src/backend/tests/synthetic_data.py` | part of `make test-backend` | The decision path on invented products (ids 900001 to 900009), so CI runs without Valio's data. Locally `make test` sets `REQUIRE_DATA=1`, so a test that skips for missing data fails instead. |
| End to end | `src/frontend/e2e/`, `src/frontend/e2e-live/` | `make test-web`, `make demo-smoke`, `make e2e-live` | The web app in a browser (Playwright, one worker): every page (login, Home, Activity, Rules, Agent, Settings) on the built app in fixture mode, then the built app against the live backend on a demo copy: a real MCP client (`scripts/connector_check.py`) connects on the Agent page, orders alone, waits for approval after the alone limit is lowered, is refused when paused, and loses its address on Disconnect. `E2E_BASE` / `SMOKE_BASE` point them at a running server or the public link. |

## Mutation testing

A test suite can pass and still check little. mutmut changes the code that decides one small edit at a time (a `<`
for a `<=`, `and` for `or`, a constant, a dropped argument) and runs the tests that reach it. A mutant the tests do
not notice "survives". The modules under test are the ones that decide or grade:

`policy/decide.py`, `policy/mandate.py`, `audit/log.py`, `matching/rank.py`, `matching/substitute.py`,
`trust/claims.py` (all under `src/backend/validio/`).

```
make mutate                         # every mutant without a result yet, then the score per module
make mutate MUTATE="run mandate"    # one module from scratch (decide, mandate, log, rank, substitute, claims)
make mutate MUTATE="score -v"       # the last score again, with every survivor named
make mutate MUTATE="show NAME"      # the diff of one mutant
make mutate MUTATE="retest NAME"    # run named mutants again after adding a test
```

`scripts/mutate.sh` runs mutmut 3.8.1 (pinned in the dev dependencies) with one worker in a scratch copy under
`artifacts/mutmut/`, which is gitignored, so no `mutants/` cache ever reaches git. Set `MUTATE_HEAVY` to a wrapper
command to queue it behind other heavy jobs. A full run of all six modules took about 55 minutes with one worker
(1ba7f8a), so on a shared machine run one module at a time (`MUTATE="run claims"`). mutmut copies data files such as
`policies.cedar` into its `mutants/` folder only once; the script refreshes them on every run, because a stale policy
makes the suite fail in the copy and mutmut stops with "failed to collect stats".

Score = killed / (killed + survived + timeout). Mutants that cannot change behaviour are listed with a one-line
reason in `scripts/mutate_equivalent.txt` and left out of the score; the raw share of all mutants killed is given
too.

### Scores

Three runs, all with the same tests outside `test_mutants_*.py` (unit, scenes in the backend tests, adversarial,
synthetic). Equivalent mutants are left out of the score; the raw column is killed / all mutants.

**Before** (14 Nov 2026, without any `test_mutants_*.py`): `mandate.py` at 161af66, the other five at e325d9b.
17 `mandate.py` mutants were not run before the run was stopped.

| Module | Mutants | Killed | Survived | Equivalent | Not run | Score | Raw (killed / all) |
|---|---:|---:|---:|---:|---:|---:|---:|
| `audit/log.py` | 251 | 210 | 13 | 28 | 0 | 94.2 % | 83.7 % |
| `policy/mandate.py` | 499 | 412 | 55 | 15 | 17 | 88.2 % | 82.6 % |
| `policy/decide.py` | 470 | 395 | 66 | 9 | 0 | 85.7 % | 84.0 % |
| `matching/rank.py` | 185 | 146 | 34 | 5 | 0 | 81.1 % | 78.9 % |
| `matching/substitute.py` | 287 | 230 | 55 | 2 | 0 | 80.7 % | 80.1 % |
| `trust/claims.py` | 125 | 86 | 31 | 8 | 0 | 73.5 % | 68.8 % |
| total | 1817 | 1479 | 254 | 67 | 17 | 85.3 % | 81.4 % |

**After the first tests** (14 Nov 2026, main at 1ba7f8a, all six modules mutated again). The code had changed in
the meantime (signed ledger head, display sentences, the stock-out name), so the mutant counts differ:

| Module | Mutants | Killed | Survived | Equivalent | Score | Raw (killed / all) |
|---|---:|---:|---:|---:|---:|---:|
| `audit/log.py` | 507 | 433 | 31 | 43 | 93.3 % | 85.4 % |
| `policy/mandate.py` | 499 | 469 | 11 | 19 | 97.7 % | 94.0 % |
| `policy/decide.py` | 472 | 432 | 27 | 13 | 94.1 % | 91.5 % |
| `matching/rank.py` | 196 | 185 | 6 | 5 | 96.9 % | 94.4 % |
| `matching/substitute.py` | 291 | 285 | 3 | 3 | 99.0 % | 97.9 % |
| `trust/claims.py` | 125 | 117 | 0 | 8 | 100.0 % | 93.6 % |
| total | 2090 | 1921 | 78 | 91 | 96.1 % | 91.9 % |

Most of the `log.py` survivors came from the signed head, added after the first tests were written.

**After the second tests** (same code, survivors run again with the tests added for them):

| Module | Mutants | Killed | Survived | Equivalent | Score | Raw (killed / all) |
|---|---:|---:|---:|---:|---:|---:|
| `audit/log.py` | 507 | 463 | 1 | 43 | 99.8 % | 91.3 % |
| `policy/mandate.py` | 499 | 476 | 4 | 19 | 99.2 % | 95.4 % |
| `policy/decide.py` | 472 | 453 | 6 | 13 | 98.7 % | 96.0 % |
| `matching/rank.py` | 196 | 190 | 1 | 5 | 99.5 % | 96.9 % |
| `matching/substitute.py` | 291 | 286 | 2 | 3 | 99.3 % | 98.3 % |
| `trust/claims.py` | 125 | 117 | 0 | 8 | 100.0 % | 93.6 % |
| total | 2090 | 1988 | 11 | 91 | 99.4 % | 95.1 % |

The `log.py` row counts `__init___48` as killed: it was listed as equivalent under a stale name, the second tests
kill it, and it was run again on its own. Mutant numbers shift whenever a function changes, so after a code change
`scripts/mutate_equivalent.txt` has to be checked against `make mutate MUTATE="score -v"` again.

### What survived, and the tests written for it

The survivors were read one by one. Those that change a decision, a grade or a check got a test.

First tests:

- `test_mutants_policy.py`: every escalation sentence alone and none at the limits (`>` against `>=` on the auto
  limit and the split limit), an undisclosed diet that would block instead of asking a person, the split in basis
  points, the request deadline and stock unit in `context_for`, the cut-off at the exact second, a context outside
  the Cedar schema, every `load_policy` error, and a grade and sentence table for every claim kind. Vegan was not
  tested at all before: milk, egg and honey in a vegan product went unnoticed by the suite.
- `test_mutants_matching.py`: the 5 % tie band edge, reliability 0.0, carbon known before unknown, the order of
  rejected options, a quote with an error flag but a price, the pack size from the comparison price, every Safe Swap
  verdict and sentence, and a fake catalog where the outside search must not stop at 12 screened products.
- `test_mutants_ledger_pass.py`: a failed append or open rolls back, exact `VerifyResult` values, a body whose
  `seq` is rewritten with its hash and the head, a zeroed head count; the nonce store's ttl edge and its errors,
  the key binding's iat window at both ends, revocation by jti, the RFC 9901 disclosure check, and `_mandate`
  defaults that fail closed.

Second tests:

- Ledger: a failed append leaves no transaction open (before, a `ROLLBACK` replaced by nothing went unnoticed,
  because the next append nested into the open transaction and only that one connection saw it); a failed append
  inside the order store's transaction keeps that transaction and drops only its own entry; a head from before the
  signature gets its `at` and `sig` columns; a body with a field more and a recomputed hash breaks the chain there;
  a changed head hash on a one-entry ledger points at that entry; the signed head carries `typ` and `kid`; a
  tampered row is shown with empty values of the right type.
- Spend Pass: an `iat` that is not a number is refused (before, it reached `iat > now` and raised a TypeError
  instead of a refusal); the pass `iat` is accepted at exactly 60 s ahead and refused at 61 s; a pass without `jti`
  asks revocation about the empty id; a key binding without a given `iat` is signed now.
- Policy: Cedar errors next to an Allow are still an error (with `and` for `or`, a forbid that failed to evaluate
  would leave an Allow behind); the blocked sentence names each cause (diet, hard cap, no delivery line, no rule);
  a total of 0 is named, 1 cent is not.
- Matching: the empty and the short stock sentences, an unknown pack size as a reason, and an outside option that
  cannot be delivered marked `on_valio_list = False` instead of `None`.

Left alive on purpose (the 11 survivors):

- `rank.x_rank_one__mutmut_60`: Best Pick treats the cut-off second as still open, Cedar as passed. Which reading
  is right is a product question, so no test pins rank.py's side (finding G14 in the review notes).
- Ten text-only mutants: the `TypeError` message of `PolicyContext`, the fallback escalation sentence, the
  "disclosure not part of the Spend Pass" message at its second raise site, and the claim list in `_kept` in
  capitals.
