#!/bin/sh
# Fetch the Arlen ui-kit (MIT, github.com/arlenos/arlen) at a pinned commit into
# vendor/arlen-ui-kit. Only sdk/ui-kit/src is copied: Vite trips over the kit's
# own tsconfig.json otherwise. The folder is gitignored and never edited.
set -eu
COMMIT=a9f10d4df2528fb6467b3b9cf00ca4aa9ca4cf37
cd "$(dirname "$0")/.."
DEST=vendor/arlen-ui-kit
if [ -f "$DEST/COMMIT" ] && [ "$(cat "$DEST/COMMIT")" = "$COMMIT" ]; then
  echo "ui-kit already at $COMMIT"
  exit 0
fi
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT
git -C "$TMP" init -q
git -C "$TMP" remote add origin https://github.com/arlenos/arlen.git
git -C "$TMP" config core.sparseCheckout true
echo "sdk/ui-kit/src/" > "$TMP/.git/info/sparse-checkout"
git -C "$TMP" fetch -q --depth 1 origin "$COMMIT"
git -C "$TMP" checkout -q FETCH_HEAD
rm -rf "$DEST"
mkdir -p "$DEST"
cp -r "$TMP/sdk/ui-kit/src" "$DEST/src"
echo "$COMMIT" > "$DEST/COMMIT"
echo "ui-kit fetched at $COMMIT"
