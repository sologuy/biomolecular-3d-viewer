#!/bin/bash
# Isolated verification suite for scripts/install.sh.
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TMP_BASE="$(mktemp -d "${TMPDIR:-/tmp}/mol3d-install-check.XXXXXX")"
trap 'rm -rf "$TMP_BASE"' EXIT

echo "== Test 1: Fresh isolated HOME installation =="
HOME1="$TMP_BASE/home1"
mkdir -p "$HOME1/.hermes"
MOL3D_INSTALL_HOME="$HOME1" "$REPO/scripts/install.sh"
for sub in .agents .claude .codex .hermes; do
  link="$HOME1/$sub/skills/biomolecular-3d-viewer"
  [ -L "$link" ] || { echo "FAIL: Expected symlink at $link" >&2; exit 1; }
  [ -f "$link/SKILL.md" ] || { echo "FAIL: Missing SKILL.md through symlink $link" >&2; exit 1; }
done

echo "== Test 2: Idempotent repeat installation =="
MOL3D_INSTALL_HOME="$HOME1" "$REPO/scripts/install.sh"

echo "== Test 3: Conflict protection against non-symlink directory =="
HOME2="$TMP_BASE/home2"
mkdir -p "$HOME2/.claude/skills/biomolecular-3d-viewer"
touch "$HOME2/.claude/skills/biomolecular-3d-viewer/custom.txt"
if MOL3D_INSTALL_HOME="$HOME2" "$REPO/scripts/install.sh" 2>/dev/null; then
  echo "FAIL: Expected install.sh to abort on existing real directory conflict" >&2
  exit 1
fi
[ -f "$HOME2/.claude/skills/biomolecular-3d-viewer/custom.txt" ] || {
  echo "FAIL: Existing file was modified during conflict abort" >&2
  exit 1
}

echo "All install-check tests passed!"
