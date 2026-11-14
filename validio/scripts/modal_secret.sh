#!/usr/bin/env bash
# Create the Modal secret validio-web from a 600 env file outside git ($MODAL_SECRETS). Writes fresh
# values first when the file is missing. Never prints them.
set -euo pipefail
cd "$(dirname "$0")/.."
f="${MODAL_SECRETS:?set MODAL_SECRETS to the env file that holds the Modal secrets}"
host="${MODAL_HOST:-timkicker--validio.us-east.modal.run}"
if [ ! -f "$f" ]; then
  umask 077
  code=$(python3 -c 'import secrets; print(f"{secrets.randbelow(10**6):06d}")')
  kitchen=$(python3 -c 'import secrets; print(secrets.token_urlsafe(24))')
  demo=$(python3 -c 'import secrets; print(secrets.token_urlsafe(24))')
  printf 'VALIDIO_PUBLIC=1\nVALIDIO_DEMO=1\nVALIDIO_APPROVE_CODE=%s\nVALIDIO_KITCHEN_TOKEN=%s\nVALIDIO_DEMO_TOKEN=%s\nVALIDIO_MCP_HOSTS=%s\n' \
    "$code" "$kitchen" "$demo" "$host" > "$f"
  echo "wrote $f"
fi
chmod 600 "$f"
cd src/backend
uv run --extra cloud modal secret create validio-web --force --from-dotenv "$f" >/dev/null
echo "modal secret validio-web set from $f"
