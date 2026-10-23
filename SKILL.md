---
name: biomolecular-3d-viewer
description: "Render publication-grade 3D atomic close-up figures (.png) and standalone interactive 3Dmol.js Biomolecular Structure Viewer canvases (.html) from .pdb or .cif files, and automatically inspect inter-chain contacts, hydrogen bonds, salt bridges, and steric clashes. Use this skill when asked to visualize protein/antibody/peptide/ligand 3D structures, compare wild-type vs. mutant pockets in 3D, inspect binding interface distances or clashes, or build an interactive 3D structure viewer (Triggers: 3D structure, 3D viewer, Biomolecular Structure Viewer, pocket close-up, clash check, hydrogen bonds, salt bridges, 3dmol, 3D结构, 看结构, 3D画布, 结构可视化, 口袋特写, 碰撞检查, 氢键盐桥, PDB看图)."
---

# Biomolecular 3D Viewer (`biomolecular-3d-viewer`)

Generate interactive 3D biomolecular structure canvases (`.html`, modeled after the *Biomolecular Structure Viewer / Shared 3D Canvas* paradigm) and publication-grade 3D atomic ball-and-stick close-up figures (`.png`, 200 DPI, dark scientific theme with non-overlapping leader-line distance callouts) directly from `.pdb` or `.cif` coordinate files.

## Bundled CLI Resolution

Resolve the bundled `mol3d_canvas.py` script across any supported agent harness (`Claude Code`, `Codex CLI`, `Google Antigravity`, `GitHub Copilot CLI`, `DeepSeek Harness`, `Muse Code`):

```bash
MOL3D=$(ls \
  "$HOME/.agents/skills/biomolecular-3d-viewer/scripts/mol3d_canvas.py" \
  "$HOME/.claude/skills/biomolecular-3d-viewer/scripts/mol3d_canvas.py" \
  "$HOME/.codex/skills/biomolecular-3d-viewer/scripts/mol3d_canvas.py" \
  2>/dev/null | head -1)
```

Runtime dependencies: Python >= 3.9 with `biopython`, `numpy`, and `matplotlib`.

## Core Subcommands

### 1. Inspect Chains & Interface Hotspots (`inspect`)

Always run `inspect` first when exploring an unfamiliar `.pdb` or `.cif` file. It parses chain IDs, residue numbering ranges, and the closest inter-chain heavy-atom contacts (`<= 4.5 Å`), automatically classifying polar H-bonds/salt bridges (`<= 3.5 Å`) and steric clashes (`< 2.4 Å`):

```bash
python3 "$MOL3D" inspect \
  /path/to/complex.pdb \
  --interface "H,L:A" \
  --cutoff 4.5 \
  --top 30 \
  --json-out /tmp/interface_contacts.json
```

### 2. Render 3D Atomic Close-Up or Side-by-Side Comparison (`closeup`)

Render a single-panel 3D pocket close-up or a dual-panel side-by-side comparison (e.g., Wild-Type vs. Mutant) with automatic neighbor detection (`<= 4.2 Å`), translucent van der Waals spheres, dashed inter-atomic distance lines (`Å`), and leader-line callout badges:

```bash
python3 "$MOL3D" closeup \
  --pdb1 /path/to/wt_complex.pdb \
  --pdb2 /path/to/mutant_complex.pdb \
  --focus "L:36:VL_Asn36(WT),H:98:VH_Trp98" \
  --focus2 "L:36:VL_His36(N36H),H:98:VH_Trp98" \
  --suptitle "3D Atomic Pocket Comparison: Wild-Type vs. N36H Mutant" \
  --title1 "Wild-Type (WT) — Optimal Core Packing" \
  --subtitle1 "Asn36 maintains 2.85 Å H-bond without steric clash" \
  --title2 "N36H Mutant — Core Steric Clash" \
  --subtitle2 "Bulky His36 imidazole ring clashes with Trp98 (2.18 Å)" \
  --radius 7.0 \
  --elev 22 --azim -50 \
  --out /path/to/wt_vs_mutant_closeup_3d.png
```

### 3. Build Standalone Interactive 3D Canvas (`viewer`)

Generate a self-contained, zero-CORS `3Dmol.js` HTML viewer that embeds the relevant interface coordinates directly inside the HTML file and automatically creates one-click camera preset buttons for the overall complex and each focal residue:

```bash
python3 "$MOL3D" viewer \
  --pdb "Engineered_Variant=/path/to/variant.pdb" \
  --pdb "Wild_Type=/path/to/wt.pdb" \
  --focus "H:52:VH_Arg52,H:100:VH_Leu100,L:36:VL_Asn36" \
  --title "Fab-Antigen Complex — 3D Structure Viewer" \
  --out /path/to/interactive_3d_viewer.html \
  --open
```

## Workflow Guidelines

1. **Always inspect coordinates before plotting**: Run `inspect` first to verify exact chain IDs and residue numbers in the `.pdb`/`.cif` file rather than guessing numbering schemes (1-based sequential vs. Kabat/IMGT/Chothia).
2. **Keep labels concise and non-overlapping**: Use compact `--focus` tokens (`Chain:ResNo:ShortLabel`), adjust `--radius` (`6.5`–`8.5 Å` for local pockets, `18`–`25 Å` for domain overviews), and tune `--elev` / `--azim` camera angles when needed.
3. **Deliver both static PNG and interactive HTML**: Pair the 200 DPI `.png` figure (for inline report inspection) with the self-contained `.html` canvas (for interactive 3D rotation, zooming, and pocket switching in the browser).
