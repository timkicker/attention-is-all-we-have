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
| End to end | `src/frontend/e2e/`, `src/frontend/e2e-live/` | `make test-web`, `make demo-smoke`, `make e2e-live` | The web app in a browser (Playwright, one worker): scenes 2 to 4 on the built app in fixture mode, then the built app against the live backend (smoke and the demo click-through). |

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
command to queue it behind other heavy jobs. A full run of all six modules takes more than an hour with one worker, so run one module at a time
(`MUTATE="run claims"`) and keep each run short on a shared machine.

Score = killed / (killed + survived + timeout). Mutants that cannot change behaviour are listed with a one-line
reason in `scripts/mutate_equivalent.txt` and left out of the score; the raw share of all mutants killed is given
too.

### Measured so far (14 Nov 2026, before the new tests)

The suite as of commit 161af66 (unit, scenes in the backend tests, adversarial, synthetic), without the
`test_mutants_*.py` files. `mandate.py` is the version after the key-binding hardening (161af66); the other five did
not change since e325d9b, where they were measured.

| Module | Mutants | Killed | Survived | Equivalent | Not run | Score | Raw (killed / all) |
|---|---:|---:|---:|---:|---:|---:|---:|
| `audit/log.py` | 251 | 210 | 13 | 28 | 0 | 94.2 % | 83.7 % |
| `policy/mandate.py` | 499 | 412 | 55 | 15 | 17 | 88.2 % | 82.6 % |
| `policy/decide.py` | 470 | 395 | 66 | 9 | 0 | 85.7 % | 84.0 % |
| `matching/rank.py` | 185 | 146 | 34 | 5 | 0 | 81.1 % | 78.9 % |
| `matching/substitute.py` | 287 | 230 | 55 | 2 | 0 | 80.7 % | 80.1 % |
| `trust/claims.py` | 125 | 86 | 31 | 8 | 0 | 73.5 % | 68.8 % |
| total | 1817 | 1479 | 254 | 67 | 17 | 85.3 % | 81.4 % |

Since then `audit/log.py` (signed ledger head), `matching/rank.py`, `matching/substitute.py` and
`policy/decide.py` (display sentences) changed again (as of 5ad0673), so their numbers and the mutant names in
`scripts/mutate_equivalent.txt` describe the code as measured, not the code today; only `trust/claims.py` and
`policy/mandate.py` are unchanged since their run.

The run was stopped to free the shared machine: 17 `mandate.py` mutants have no result, and **no module has been
mutated again with the new tests yet**, so there is no "after" score. Reproduce the "before" numbers by moving the
three `test_mutants_*.py` files out of the scratch copy; get the "after" numbers with
`make mutate MUTATE="run log"` and so on, one module per run.

### What survived, and the tests written for it

The survivors were read one by one. Those that change a decision, a grade or a check got a test:

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

Left alive on purpose:

- Text-only mutants (a sentence in capitals or with `XX` around it) where no test pins the exact wording yet.
- `rank.x_rank_one__mutmut_62`: Best Pick treats the cut-off second as still open, Cedar as passed. Which reading is
  right is a product question, so no test pins rank.py's side (finding G14 in the review notes).
- `present()` with no `iat` from the caller (`x_present__mutmut_13`, `_15`) and `alg=None` in its `add_signature`
  (`_33`, `_36`): not yet checked.

