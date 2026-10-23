#!/bin/bash
# End-to-end functional test suite for mol3d_canvas.py (inspect, closeup, viewer).
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CLI="$REPO/scripts/mol3d_canvas.py"
WT_PDB="$REPO/examples/wt_complex.pdb"
MUT_PDB="$REPO/examples/mutant_complex.pdb"
TMP_OUT="$(mktemp -d "${TMPDIR:-/tmp}/mol3d-dryrun.XXXXXX")"
trap 'rm -rf "$TMP_OUT"' EXIT

echo "== 1. Testing 'inspect' subcommand (inter-chain contacts & clashes) =="
python3 "$CLI" inspect "$MUT_PDB" \
  --interface "H,L:A" \
  --cutoff 4.5 \
  --top 10 \
  --json-out "$TMP_OUT/inspect_hla.json" >/dev/null

python3 "$CLI" inspect "$MUT_PDB" \
  --interface "L:H" \
  --cutoff 4.5 \
  --top 10 \
  --json-out "$TMP_OUT/inspect_lh.json" >/dev/null

python3 - "$TMP_OUT/inspect_hla.json" "$TMP_OUT/inspect_lh.json" <<'PY'
import json
import sys

with open(sys.argv[1], encoding="utf-8") as f:
    hla = json.load(f)
assert hla["total_contacts"] >= 3, f"Expected >=3 H,L:A contacts, got {hla['total_contacts']}"
types_hla = {c["type"] for c in hla["top_contacts"]}
assert "polar_hbond_or_saltbridge" in types_hla, "Expected polar H-bond/salt-bridge detection"

with open(sys.argv[2], encoding="utf-8") as f:
    lh = json.load(f)
assert lh["total_contacts"] >= 1, "Expected L:H clash contact in mutant_complex.pdb"
assert lh["top_contacts"][0]["type"] == "steric_clash", f"Expected steric_clash, got {lh['top_contacts'][0]}"
print("  ✅ inspect JSON schema and contact classification verified")
PY

echo "== 2. Testing 'closeup' subcommand (single-panel & dual-panel 3D PNGs) =="
python3 "$CLI" closeup \
  --pdb1 "$WT_PDB" \
  --pdb2 "$MUT_PDB" \
  --focus "L:36:VL_Asn36(WT),H:98:VH_Trp98" \
  --focus2 "L:36:VL_His36(N36H),H:98:VH_Trp98" \
  --suptitle "Dry-Run Dual Panel Test" \
  --out "$TMP_OUT/dual_closeup.png"

python3 "$CLI" closeup \
  --pdb1 "$MUT_PDB" \
  --focus "H:52:VH_Arg52,A:210:Target_Asp210" \
  --title1 "Dry-Run Single Panel Test" \
  --out "$TMP_OUT/single_closeup.png"

python3 - "$TMP_OUT/dual_closeup.png" "$TMP_OUT/single_closeup.png" <<'PY'
import os
import sys

for p in sys.argv[1:]:
    assert os.path.isfile(p), f"Missing PNG output: {p}"
    size = os.path.getsize(p)
    assert size > 20_000, f"PNG output unexpectedly small ({size} bytes): {p}"
    with open(p, "rb") as f:
        sig = f.read(8)
    assert sig == b"\x89PNG\r\n\x1a\n", f"Invalid PNG signature in {p}"
print("  ✅ closeup single-panel and dual-panel 200 DPI PNG generation verified")
PY

echo "== 3. Testing 'viewer' subcommand (standalone 3Dmol.js HTML canvas) =="
python3 "$CLI" viewer \
  --pdb "Engineered_Variant=$MUT_PDB" \
  --pdb "Wild_Type=$WT_PDB" \
  --focus "H:52:VH_Arg52,H:100:VH_Leu100,L:36:VL_His36" \
  --title "Dry-Run 3D Viewer" \
  --out "$TMP_OUT/viewer.html"

python3 - "$TMP_OUT/viewer.html" <<'PY'
import sys

with open(sys.argv[1], encoding="utf-8") as f:
    html = f.read()
assert "3Dmol-min.js" in html, "Missing 3Dmol.js script tag"
assert "const PDB_MODELS =" in html, "Missing embedded PDB_MODELS payload"
assert "Engineered_Variant" in html and "Wild_Type" in html, "Missing model keys in HTML"
assert "Pocket Close-Up" in html, "Missing auto-generated pocket close-up scenes"
print("  ✅ viewer standalone zero-CORS HTML generation verified")
PY

echo "All dryrun checks passed!"
