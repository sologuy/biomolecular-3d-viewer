#!/bin/bash
# Safe, idempotent multi-harness skill installer for biomolecular-3d-viewer.
# Links this repository into ~/.agents/skills/, ~/.claude/skills/, and ~/.codex/skills/
# (plus ~/.hermes/skills/ if ~/.hermes exists) so all agent harnesses share a single source of truth.
set -euo pipefail

usage() {
  cat <<'EOF'
Usage: ./scripts/install.sh [--home <install-root>]

Options:
  --home <dir>        Override target HOME directory (or set MOL3D_INSTALL_HOME)
  -h, --help          Show this help message

Environment:
  MOL3D_INSTALL_HOME  Optional installation root (default: $HOME)
  MOL3D_PYTHON        Optional Python interpreter for preflight checks (requires Python >= 3.9)
EOF
}

INSTALL_HOME="${MOL3D_INSTALL_HOME:-$HOME}"
while [ "$#" -gt 0 ]; do
  case "$1" in
    --home)
      [ "$#" -ge 2 ] || { echo "Error: --home requires a directory path" >&2; exit 2; }
      INSTALL_HOME="$2"; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown argument: $1" >&2; usage >&2; exit 2 ;;
  esac
done

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PY="${MOL3D_PYTHON:-python3}"
PY="$(command -v "$PY" || true)"
if [ -z "$PY" ] || ! "$PY" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 9) else 1)'; then
  echo "Error: Python >= 3.9 is required (override via MOL3D_PYTHON=/path/to/python3)" >&2
  exit 1
fi

INSTALL_HOME="$("$PY" -c 'import os,sys; print(os.path.realpath(os.path.abspath(sys.argv[1])))' "$INSTALL_HOME")"
REPO_REAL="$("$PY" -c 'import os,sys; print(os.path.realpath(os.path.abspath(sys.argv[1])))' "$REPO")"
SKILL_NAME="biomolecular-3d-viewer"

echo "== Preflight Check ($SKILL_NAME) =="
[ -f "$REPO/SKILL.md" ] && [ -f "$REPO/scripts/mol3d_canvas.py" ] || {
  echo "Error: Missing SKILL.md or scripts/mol3d_canvas.py in $REPO" >&2
  exit 1
}

ROOTS=(
  "$INSTALL_HOME/.agents/skills"
  "$INSTALL_HOME/.claude/skills"
  "$INSTALL_HOME/.codex/skills"
)
[ ! -d "$INSTALL_HOME/.hermes" ] || ROOTS+=("$INSTALL_HOME/.hermes/skills")

TARGETS=()
for root in "${ROOTS[@]}"; do
  TARGETS+=("$root/$SKILL_NAME")
done

# Validate all target paths before modifying the filesystem
"$PY" - "$REPO_REAL" "${TARGETS[@]}" <<'PY'
import os
import sys

repo_real = sys.argv[1]
errors = []
for link in sys.argv[2:]:
    if os.path.lexists(link):
        if os.path.islink(link):
            continue
        if os.path.realpath(link) == repo_real:
            continue
        errors.append(f"Conflict: {link} already exists and is not a symlink (refusing to overwrite)")
    parent = os.path.dirname(link)
    while parent and parent != os.path.dirname(parent):
        if os.path.lexists(parent):
            if not os.path.isdir(parent):
                errors.append(f"Invalid parent path: {parent} is not a directory")
            elif not os.access(parent, os.W_OK | os.X_OK):
                errors.append(f"Permission denied: {parent} is not writable")
            break
        parent = os.path.dirname(parent)

if errors:
    print("\n".join(errors), file=sys.stderr)
    sys.exit(1)
PY

echo "== Linking Skill Across Harnesses =="
for link in "${TARGETS[@]}"; do
  mkdir -p "$(dirname "$link")"
  link_parent_real="$("$PY" -c 'import os,sys; print(os.path.realpath(sys.argv[1]))' "$(dirname "$link")")"
  canonical_target="$link_parent_real/$SKILL_NAME"
  if [ "$canonical_target" = "$REPO_REAL" ] && [ ! -L "$link" ]; then
    printf '  ✅ %s (canonical repository checkout)\n' "$link"
    continue
  fi
  if [ ! -L "$link" ] || [ "$(readlink "$link")" != "$REPO" ]; then
    ln -sfn "$REPO" "$link"
  fi
  printf '  ✅ %s -> %s\n' "$link" "$REPO"
done

echo ""
echo "Installation complete!"
echo "Native discovery via ~/.agents/skills/: Google Antigravity, GitHub Copilot CLI, DeepSeek Harness (DSH), Muse Code"
echo "Symlink discovery: Claude Code (~/.claude/skills/) & OpenAI Codex CLI (~/.codex/skills/)"
