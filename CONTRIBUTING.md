# Contributing to `biomolecular-3d-viewer`

Thank you for your interest in contributing to **`biomolecular-3d-viewer`**! This project provides a deterministic, zero-daemon 3D biomolecular visualization skill and CLI for AI coding agents and structural biology researchers.

## Design Philosophy

1. **Deterministic Coordinates Over Hallucinated Geometry**: Always compute heavy-atom distances (`min_heavy_dist`) directly from `.pdb` or `.cif` coordinates via `Bio.PDB`. Never approximate side-chain contacts from Cα distances alone.
2. **Zero-CORS Standalone Canvases**: The `viewer` subcommand embeds the relevant PDB coordinate subset directly inside the generated `.html` file (`PDB_MODELS`), ensuring that users and agents can open the file directly via `file://` in any browser without running a local HTTP server.
3. **Non-Overlapping 3D Typography**: The `closeup` subcommand uses `computed_zorder=False` with outward radial repulsion (`choose_non_overlapping_pos`) so that residue callouts and inter-atomic distance badges never collide or get occluded by 3D scatter spheres.
4. **Single-Source Multi-Harness Compatibility**: Keep `SKILL.md` portable across `Claude Code`, `OpenAI Codex CLI`, `Google Antigravity`, `GitHub Copilot CLI`, `DeepSeek Harness (DSH)`, and `Muse Code` without relying on harness-specific template macros or hardcoded user paths.

## Verification Checklist

Before opening a pull request, run the full verification suite locally:

```bash
# 1. Syntax checks
bash -n scripts/install.sh scripts/install-check.sh scripts/dryrun.sh examples/run_demo.sh
python3 -m py_compile scripts/mol3d_canvas.py

# 2. Functional dry-run (inspect JSON + closeup PNGs + viewer HTML)
./scripts/dryrun.sh

# 3. Isolated multi-harness installation matrix
./scripts/install-check.sh
```

## Commit Style

Use Conventional Commits:

- `feat: ...` — new visualization modes, CLI flags, or structure analysis capabilities
- `fix: ...` — bug fixes in coordinate parsing, 3D label placement, or HTML rendering
- `docs: ...` — documentation or example updates
- `chore: ...` — CI, packaging, or installer maintenance

Before pushing, confirm that `git status --short` is clean and that no credentials or personal `/Users/<username>/` paths appear in tracked files.
