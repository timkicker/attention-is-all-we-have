# list files to scan under $1: git tracked and untracked-not-ignored, else everything
list_files() {
  local root="$1"
  if git -C "$root" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    (cd "$root" && git ls-files -co --exclude-standard -- . | sed "s|^|$root/|")
  else
    find "$root" -type f -not -path '*/.git/*' -not -path '*/.venv/*' -not -path '*/node_modules/*' \
      -not -path '*/data/*' -not -path '*/artifacts/*' -not -name '.env'
  fi
}
