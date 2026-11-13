"""`make agent SCENE=2`: the same as the `validio-agent` command, see validio/agent/cli.py."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src" / "backend"))
from validio.agent.cli import main

if __name__ == "__main__":
    sys.exit(main())
