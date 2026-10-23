#!/bin/bash
# Generate all showcase 3D atomic close-up figures and the interactive 3Dmol.js HTML viewer
# from the benchmark structures in examples/wt_complex.pdb and examples/mutant_complex.pdb.
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CLI="$REPO/scripts/mol3d_canvas.py"

echo "1. Inspecting interface contacts on examples/mutant_complex.pdb..."
python3 "$CLI" inspect "$REPO/examples/mutant_complex.pdb" --interface "H,L:A" --top 10

echo "2. Rendering 3D atomic pocket close-up figures into assets/..."
python3 "$CLI" closeup \
  --pdb1 "$REPO/examples/wt_complex.pdb" \
  --pdb2 "$REPO/examples/mutant_complex.pdb" \
  --focus "L:36:VL_Asn36(WT),H:98:VH_Trp98" \
  --focus2 "L:36:VL_His36(N36H),H:98:VH_Trp98" \
  --suptitle "3D Atomic Pocket Audit: Core Packing (WT) vs. Steric Clash (L:N36H)" \
  --title1 "Wild-Type (WT) — Optimal VH/VL Packing" \
  --subtitle1 "L:Asn36 forms a 2.86 Å inter-chain H-bond with H:Trp98" \
  --title2 "Mutant (L:N36H) — Core Steric Clash" \
  --subtitle2 "Bulky His36 imidazole ring clashes with H:Trp98 (1.99 Å)" \
  --radius 6.2 --elev 18 --azim -48 \
  --out "$REPO/assets/wt_vs_mutant_clash_3d.png"

python3 "$CLI" closeup \
  --pdb1 "$REPO/examples/wt_complex.pdb" \
  --pdb2 "$REPO/examples/mutant_complex.pdb" \
  --focus "H:52:VH_Thr52(WT),A:210:Target_Asp210" \
  --focus2 "H:52:VH_Arg52(T52R),A:210:Target_Asp210" \
  --suptitle "3D Electrostatic Engineering: Long-Range Salt-Bridge Formation (H:T52R)" \
  --title1 "Wild-Type (WT) — Short Thr52 Side Chain" \
  --subtitle1 "Thr52 cannot bridge the 7.50 Å cleft to Target Asp210" \
  --title2 "Engineered Variant (H:T52R) — Interfacial Salt Bridge" \
  --subtitle2 "Arg52 guanidinium forms a 2.78 Å salt bridge with Target Asp210" \
  --radius 7.5 --elev 18 --azim -42 \
  --out "$REPO/assets/interface_salt_bridge_3d.png"

python3 "$CLI" closeup \
  --pdb1 "$REPO/examples/wt_complex.pdb" \
  --pdb2 "$REPO/examples/mutant_complex.pdb" \
  --focus "H:100:VH_Val100(WT),H:102:VH_Thr102(WT)" \
  --focus2 "H:100:VH_Leu100(V100L),H:102:VH_Ser102(T102S)" \
  --suptitle "3D Pocket Complementarity: Hydrophobic Packing & Polar Relief (V100L + T102S)" \
  --title1 "Wild-Type (WT) — Sub-Optimal Cavity Fill" \
  --subtitle1 "Val100 leaves a hydrophobic void; Thr102 γ-methyl crowds Glu148" \
  --title2 "Engineered Variant (V100L + T102S) — Tight Interface" \
  --subtitle2 "Leu100 packs against Tyr145 (3.52 Å); Ser102 H-bonds with Glu148 (2.74 Å)" \
  --radius 7.2 --elev 20 --azim -50 \
  --out "$REPO/assets/cdr_pocket_packing_3d.png"

echo "3. Building standalone 3Dmol.js interactive canvas..."
python3 "$CLI" viewer \
  --pdb "Engineered_Variant=$REPO/examples/mutant_complex.pdb" \
  --pdb "Wild_Type=$REPO/examples/wt_complex.pdb" \
  --focus "H:52:VH_Arg52,H:100:VH_Leu100,H:102:VH_Ser102,L:36:VL_His36" \
  --title "Fab–Target Complex — Biomolecular 3D Viewer" \
  --out "$REPO/examples/demo_interactive_viewer.html"

echo "Done! Outputs written to assets/*.png and examples/demo_interactive_viewer.html"
