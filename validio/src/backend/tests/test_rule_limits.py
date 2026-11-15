"""The limits a request was decided under stay on its detail after the Rules change (plans/025, P3)."""
from validio.api.activity import limits_at
from validio.demo import seed


def test_each_version_keeps_its_own_limits(syn_ctx):
    path = syn_ctx.db_path
    v1 = limits_at(syn_ctx, 1)
    assert v1 is not None
    assert (v1.alone_up_to_cents, v1.approval_up_to_cents) == (120000, 200000)

    seed.sign_again(path, None, {"autoLimitCents": 50000, "hardCapCents": 300000})
    now = seed.pass_version(path, seed.SPEND_PASS_ID)
    newer = limits_at(syn_ctx, now)
    assert (newer.alone_up_to_cents, newer.approval_up_to_cents) == (50000, 300000)
    # The older version still answers with its own numbers.
    assert limits_at(syn_ctx, 1).alone_up_to_cents == 120000


def test_an_unknown_version_has_no_limits(syn_ctx):
    assert limits_at(syn_ctx, 99) is None
