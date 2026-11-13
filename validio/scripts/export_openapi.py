"""Write the backend's OpenAPI 3.1 description to src/frontend/src/lib/api/openapi.json (`make types`).
No server, no network: the description comes from the FastAPI app object."""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src" / "backend"))
from validio.api.app import app

OUT = ROOT / "src" / "frontend" / "src" / "lib" / "api" / "openapi.json"


def main() -> int:
    OUT.write_text(json.dumps(app.openapi(), indent=2, sort_keys=True, ensure_ascii=False) + "\n")
    print(f"wrote {OUT.relative_to(ROOT)} ({len(app.openapi()['paths'])} paths)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
