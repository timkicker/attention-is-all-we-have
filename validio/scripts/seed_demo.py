"""Reset the local store to the demo state: `make seed`. Run it as often as you like, the state is the same."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src" / "backend"))
from validio.demo import seed


def main() -> int:
    path = seed.reset()
    h = seed.load_history()
    m = seed.spend_pass(path)
    print(f"seeded {path}: kitchen {seed.KITCHEN}, Spend Pass {m.id}, clock {seed.NOW.isoformat()}, "
          f"{len(h.weeks)} weeks of simulated history ({h.weeks[0].delivered} to {h.weeks[-1].delivered}), "
          f"stock-out of {seed.STOCKOUT_ID} off")
    return 0


if __name__ == "__main__":
    sys.exit(main())
