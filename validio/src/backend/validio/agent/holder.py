"""The agent's side of the Spend Pass: it holds the issued pass and its own key, and presents the pass
with a fresh nonce for every write, showing only budget, hard cap and diet."""

import sqlite3
from collections.abc import Callable
from pathlib import Path

from ..demo import seed
from ..policy.mandate import AUDIENCE, load_or_create_key, present

DISCLOSE = frozenset({"autoLimitCents", "hardCapCents", "diet"})


class Holder:
    def __init__(self, issuance: str, agent_key, nonce: Callable[[], str], disclose=DISCLOSE):
        self.issuance, self.key, self.nonce, self.disclose = issuance, agent_key, nonce, set(disclose)

    @classmethod
    def from_seed(cls, nonce: Callable[[], str], db_path: Path | None = None, keys_dir: Path | None = None,
                  disclose=DISCLOSE) -> "Holder":
        """The demo pass M-1 as `make seed` issued it to the agent."""
        con = sqlite3.connect(db_path or seed.db_path())
        try:
            (issuance,) = con.execute("select issuance from spend_pass where id = ?", (seed.SPEND_PASS_ID,)).fetchone()
        finally:
            con.close()
        key = load_or_create_key(Path(keys_dir or seed.keys_path()) / "agent-es256.json")
        return cls(issuance, key, nonce, disclose)

    def presentation(self) -> str:
        return present(self.issuance, self.disclose, self.key, AUDIENCE, self.nonce())
