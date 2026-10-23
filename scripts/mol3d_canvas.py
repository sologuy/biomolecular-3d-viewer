#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
mol3d_canvas.py — Universal Biomolecular 3D Structure Viewer & Atomic Close-Up Renderer.

Provides three deterministic subcommands for AI coding agents (Claude Code, Codex CLI,
Google Antigravity, GitHub Copilot CLI, DeepSeek Harness, Muse Code) and structural
biology workflows:
  1. inspect : Parse .pdb/.cif, report chains, interface hotspots, H-bonds/salt bridges, and clashes.
  2. closeup : Render publication-grade 3D atomic ball-and-stick close-up or side-by-side comparison (.png).
  3. viewer  : Build a self-contained 3Dmol.js Shared 3D Canvas (.html) with one-click camera presets.
"""

import argparse
import io
import json
import os
import platform
import subprocess
import sys
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D  # noqa: F401
from Bio.PDB import PDBParser, MMCIFParser, PDBIO, Select

# Cross-platform sans-serif font stack with full Unicode/CJK fallback support
plt.rcParams["font.sans-serif"] = [
    "DejaVu Sans", "Arial", "Helvetica", "Arial Unicode MS",
    "PingFang SC", "Heiti TC", "Noto Sans CJK SC"
]
plt.rcParams["axes.unicode_minus"] = False

ELEMENT_COLORS = {
    "C": "#E2E8F0",
    "N": "#38BDF8",
    "O": "#FB7185",
    "S": "#FACC15",
    "P": "#FB923C",
}

CHAIN_PALETTE = [
    "#38BDF8", "#A78BFA", "#F59E0B", "#14B8A6",
    "#F472B6", "#60A5FA", "#34D399", "#FB923C"
]


def load_structure(path, struct_id="s"):
    """Load the first model from a PDB or mmCIF file."""
    ext = os.path.splitext(path)[1].lower()
    if ext in (".cif", ".mmcif"):
        parser = MMCIFParser(QUIET=True)
    else:
        parser = PDBParser(QUIET=True)
    return parser.get_structure(struct_id, path)[0]


def is_std_aa(res):
    """Return True if residue is a standard amino acid with a CA atom."""
    return res.id[0] == " " and "CA" in res


def min_heavy_dist(res1, res2):
    """Return (min_distance_A, atom1, atom2) between heavy atoms of two residues."""
    best = (999.0, None, None)
    for a1 in res1:
        if a1.element == "H":
            continue
        for a2 in res2:
            if a2.element == "H":
                continue
            d = float(np.linalg.norm(a1.coord - a2.coord))
            if d < best[0]:
                best = (d, a1, a2)
    return best


def parse_focus_token(tok):
    """Parse 'H:99' or 'H:99:VH_Leu99' into (chain_id, resno, label)."""
    parts = tok.strip().split(":")
    if len(parts) < 2:
        raise ValueError(f"Invalid focus token '{tok}', expected CHAIN:RESNO[:LABEL]")
    cid = parts[0].strip()
    rno = int(parts[1].strip())
    lbl = ":".join(parts[2:]).strip() if len(parts) > 2 else None
    return cid, rno, lbl


def cmd_inspect(args):
    """Inspect chain composition and inter-chain atomic contacts."""
    model = load_structure(args.pdb, "inspect")
    chains_info = []
    for c in model:
        std_res = [r for r in c if is_std_aa(r)]
        if not std_res:
            continue
        chains_info.append({
            "chain": c.id,
            "length": len(std_res),
            "first_res": f"{std_res[0].resname}{std_res[0].id[1]}",
            "last_res": f"{std_res[-1].resname}{std_res[-1].id[1]}",
        })

    if args.interface and ":" in args.interface:
        g1_str, g2_str = args.interface.split(":", 1)
        group1 = [x.strip() for x in g1_str.split(",") if x.strip()]
        group2 = [x.strip() for x in g2_str.split(",") if x.strip()]
    else:
        all_c = [c["chain"] for c in chains_info]
        group1 = all_c[:1]
        group2 = all_c[1:]

    contacts = []
    for c1 in group1:
        if c1 not in model:
            continue
        for r1 in model[c1]:
            if not is_std_aa(r1):
                continue
            for c2 in group2:
                if c2 not in model:
                    continue
                for r2 in model[c2]:
                    if not is_std_aa(r2):
                        continue
                    if np.linalg.norm(r1["CA"].coord - r2["CA"].coord) > args.cutoff + 8.5:
                        continue
                    d, a1, a2 = min_heavy_dist(r1, r2)
                    if d <= args.cutoff:
                        kind = "nonpolar_or_vdw_contact"
                        if d < 2.4:
                            kind = "steric_clash"
                        elif d <= 3.5 and a1.element in ("N", "O") and a2.element in ("N", "O"):
                            kind = "polar_hbond_or_saltbridge"
                        contacts.append({
                            "dist_A": round(d, 2),
                            "type": kind,
                            "res1": f"{c1}:{r1.resname}{r1.id[1]}",
                            "atom1": a1.name,
                            "res2": f"{c2}:{r2.resname}{r2.id[1]}",
                            "atom2": a2.name,
                        })
    contacts.sort(key=lambda x: x["dist_A"])
    report = {
        "pdb": os.path.abspath(args.pdb),
        "chains": chains_info,
        "interface_groups": {"group1": group1, "group2": group2},
        "cutoff_A": args.cutoff,
        "total_contacts": len(contacts),
        "top_contacts": contacts[: args.top],
    }
    if args.json_out:
        os.makedirs(os.path.dirname(os.path.abspath(args.json_out)), exist_ok=True)
        with open(args.json_out, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
    print(json.dumps(report, ensure_ascii=False, indent=2))


def draw_residue_ball_stick(
    ax, res, carbon_color="#22D3EE", alpha=0.95, lw=2.6, s_scale=75, show_vdw=False, vdw_color=None
):
    """Draw heavy-atom covalent bonds, CPK spheres, and optional translucent VDW halos."""
    atoms = [a for a in res if a.element != "H"]
    coords = np.array([a.coord for a in atoms])
    for i in range(len(atoms)):
        for j in range(i + 1, len(atoms)):
            d = np.linalg.norm(atoms[i].coord - atoms[j].coord)
            if d < 1.92:
                p1, p2 = atoms[i].coord, atoms[j].coord
                ax.plot(
                    [p1[0], p2[0]], [p1[1], p2[1]], [p1[2], p2[2]],
                    color=carbon_color, lw=lw, alpha=alpha, zorder=5
                )
    for a in atoms:
        el = a.element if a.element in ELEMENT_COLORS else "C"
        col = carbon_color if el == "C" else ELEMENT_COLORS[el]
        sz = s_scale * (1.25 if a.name == "CA" else 1.0)
        ax.scatter(
            [a.coord[0]], [a.coord[1]], [a.coord[2]],
            color=col, edgecolors="#0F172A", linewidths=0.8, s=sz, alpha=alpha, zorder=8
        )
        if show_vdw and a.name not in ("N", "CA", "C", "O"):
            ax.scatter(
                [a.coord[0]], [a.coord[1]], [a.coord[2]],
                color=vdw_color or carbon_color, edgecolors="none", s=sz * 5.8, alpha=0.18, zorder=3
            )
    return coords


def draw_distance_line(ax, p1, p2, text, color="#FDE047", lw=2.2, ls="--", fontsize=9.2, offset=(0, 0, 1.2)):
    """Draw a dashed inter-atomic distance line with an offset leader-line callout badge."""
    ax.plot(
        [p1[0], p2[0]], [p1[1], p2[1]], [p1[2], p2[2]],
        color=color, lw=lw, linestyle=ls, zorder=12
    )
    mid = 0.5 * (p1 + p2)
    lbl_pos = mid + np.array(offset)
    ax.plot(
        [mid[0], lbl_pos[0]], [mid[1], lbl_pos[1]], [mid[2], lbl_pos[2]],
        color=color, lw=1.0, linestyle=":", alpha=0.85, zorder=11
    )
    ax.text(
        lbl_pos[0], lbl_pos[1], lbl_pos[2], text,
        color=color, fontsize=fontsize, fontweight="bold", ha="center", va="center",
        bbox=dict(boxstyle="round,pad=0.22", facecolor="#0F172A", edgecolor=color, alpha=0.92, lw=1.1),
        zorder=25
    )


def draw_callout_label(ax, pos, offset, text, color, fontsize=9.2):
    """Draw a residue label badge connected to its CA atom via a dotted leader line."""
    target = pos + np.array(offset)
    ax.plot(
        [pos[0], target[0]], [pos[1], target[1]], [pos[2], target[2]],
        color=color, lw=1.1, linestyle=":", alpha=0.85, zorder=14
    )
    ax.text(
        target[0], target[1], target[2], text,
        color=color, fontsize=fontsize, fontweight="bold", ha="center", va="center",
        bbox=dict(boxstyle="round,pad=0.2", facecolor="#0F172A", edgecolor=color, alpha=0.90, lw=0.9),
        zorder=24
    )


def style_dark_3d_ax(ax, title, subtitle=""):
    """Apply dark scientific theme to a Matplotlib 3D axis."""
    ax.set_facecolor("#0B1120")
    ax.xaxis.set_pane_color((0.06, 0.09, 0.16, 0.95))
    ax.yaxis.set_pane_color((0.06, 0.09, 0.16, 0.95))
    ax.zaxis.set_pane_color((0.06, 0.09, 0.16, 0.95))
    ax.grid(True, color="#1E293B", linestyle=":", linewidth=0.6, alpha=0.5)
    ax.tick_params(colors="#64748B", labelsize=7)
    ax.set_xlabel("X (Å)", color="#64748B", fontsize=8, labelpad=-2)
    ax.set_ylabel("Y (Å)", color="#64748B", fontsize=8, labelpad=-2)
    ax.set_zlabel("Z (Å)", color="#64748B", fontsize=8, labelpad=-2)
    ax.set_title(
        title + ("\n" + subtitle if subtitle else ""),
        color="#F8FAFC", fontsize=11.0, fontweight="bold", pad=10
    )


def choose_non_overlapping_pos(anchor, candidate_offsets, placed_positions, center=None, min_sep=3.2):
    """Select an offset around anchor that points outward from center and avoids existing labels."""
    best_pos = anchor + np.array(candidate_offsets[0])
    best_score = -1e9
    outward = (anchor - center) if center is not None else np.zeros(3)
    norm_out = float(np.linalg.norm(outward))
    if norm_out > 1e-6:
        outward = outward / norm_out
    for ofs in candidate_offsets:
        ofs_arr = np.array(ofs, dtype=float)
        pos = anchor + ofs_arr
        min_d = min((float(np.linalg.norm(pos - p)) for p in placed_positions), default=10.0)
        align = float(np.dot(ofs_arr / (np.linalg.norm(ofs_arr) + 1e-6), outward))
        score = min(min_d, 5.5) * 2.0 + align * 1.5
        if min_d >= min_sep and score > best_score:
            best_score = score
            best_pos = pos
    placed_positions.append(best_pos)
    return best_pos


def render_single_panel(ax, model, focus_list, title, subtitle, radius, elev, azim):
    """Render one 3D structural panel centered around the specified focal residues."""
    style_dark_3d_ax(ax, title, subtitle)
    focus_coords = []
    focus_set = set()
    for cid, rno, _ in focus_list:
        if cid in model and rno in model[cid]:
            focus_coords.append(model[cid][rno]["CA"].coord)
            focus_set.add((cid, rno))
    center = np.mean(focus_coords, axis=0) if focus_coords else np.zeros(3)

    # Draw local CA backbone traces within radius + 4.5 Å
    for idx, chain in enumerate(model):
        col = CHAIN_PALETTE[idx % len(CHAIN_PALETTE)]
        seg = []
        for res in chain:
            if not is_std_aa(res):
                continue
            ca = res["CA"].coord
            if np.linalg.norm(ca - center) <= radius + 4.5:
                seg.append(ca)
            else:
                if len(seg) >= 2:
                    arr = np.array(seg)
                    ax.plot(arr[:, 0], arr[:, 1], arr[:, 2], color=col, lw=3.8, alpha=0.55)
                seg = []
        if len(seg) >= 2:
            arr = np.array(seg)
            ax.plot(arr[:, 0], arr[:, 1], arr[:, 2], color=col, lw=3.8, alpha=0.55)

    offsets_ring = [
        (2.8, -2.0, -1.6), (-2.8, 2.0, 1.6), (3.0, 2.0, -1.4),
        (-3.0, -2.0, 1.4), (3.2, -0.8, 1.8), (-3.2, 0.8, -1.8),
        (0.0, -3.2, 1.8), (0.0, 3.2, -1.8)
    ]
    dist_offsets = [
        (-2.8, -1.6, 0.6), (2.8, 1.6, -0.6), (2.8, -1.8, 1.2),
        (-2.8, 1.8, -1.2), (0.0, -2.8, 0.0), (0.0, 2.8, 0.0)
    ]

    placed_labels = []
    neighbors_drawn = set()
    drawn_pairs = set()

    # 1. Draw all focal residues and their callout labels
    for f_idx, (cid, rno, custom_lbl) in enumerate(focus_list):
        if cid not in model or rno not in model[cid]:
            continue
        f_res = model[cid][rno]
        f_col = "#10B981" if f_idx == 0 else "#22D3EE"
        draw_residue_ball_stick(ax, f_res, carbon_color=f_col, lw=3.3, s_scale=90, show_vdw=True, vdw_color=f_col)
        lbl = custom_lbl or f"{cid}:{f_res.resname}{rno}"
        rot_offsets = offsets_ring[f_idx:] + offsets_ring[:f_idx]
        lbl_pos = choose_non_overlapping_pos(f_res["CA"].coord, rot_offsets, placed_labels, center=center, min_sep=3.4)
        draw_callout_label(ax, f_res["CA"].coord, lbl_pos - f_res["CA"].coord, lbl, f_col, fontsize=9.5)

    # 2. Measure and draw direct interactions between pairs of focal residues
    for i in range(len(focus_list)):
        c1, r1_no, _ = focus_list[i]
        if c1 not in model or r1_no not in model[c1]:
            continue
        res1 = model[c1][r1_no]
        for j in range(i + 1, len(focus_list)):
            c2, r2_no, _ = focus_list[j]
            if c2 not in model or r2_no not in model[c2]:
                continue
            if c1 == c2 and abs(r1_no - r2_no) <= 3:
                continue
            res2 = model[c2][r2_no]
            d, a1, a2 = min_heavy_dist(res1, res2)
            if d <= 8.5:
                pair_key = tuple(sorted([(c1, r1_no), (c2, r2_no)]))
                drawn_pairs.add(pair_key)
                line_col = "#FB7185" if d < 2.45 else ("#34D399" if d <= 3.5 else ("#FDE047" if d <= 4.5 else "#94A3B8"))
                tag = " [CLASH]" if d < 2.45 else ""
                mid = 0.5 * (a1.coord + a2.coord)
                lbl_pos = choose_non_overlapping_pos(mid, dist_offsets, placed_labels, min_sep=3.2)
                draw_distance_line(
                    ax, a1.coord, a2.coord,
                    f"{d:.2f} Å ({a1.name}–{a2.name}){tag}",
                    color=line_col, offset=lbl_pos - mid
                )

    # 3. Automatically locate top non-local contacting neighbor residues (<= 4.2 Å)
    for f_idx, (cid, rno, _) in enumerate(focus_list):
        if cid not in model or rno not in model[cid]:
            continue
        f_res = model[cid][rno]
        cand = []
        for c2 in model:
            for r2 in c2:
                if not is_std_aa(r2):
                    continue
                if c2.id == cid and abs(r2.id[1] - rno) <= 3:
                    continue
                if (c2.id, r2.id[1]) in focus_set:
                    continue
                d, a1, a2 = min_heavy_dist(f_res, r2)
                if d <= 4.2:
                    cand.append((d, c2.id, r2, a1, a2))
        cand.sort(key=lambda x: x[0])
        for d, c2_id, r2, a1, a2 in cand[:2]:
            key = (c2_id, r2.id[1])
            pair_key = tuple(sorted([(cid, rno), key]))
            if key not in neighbors_drawn:
                neighbors_drawn.add(key)
                draw_residue_ball_stick(
                    ax, r2, carbon_color="#F59E0B", lw=2.2, s_scale=68, show_vdw=True, vdw_color="#F59E0B"
                )
                lbl_pos = choose_non_overlapping_pos(r2["CA"].coord, offsets_ring, placed_labels, center=center, min_sep=3.2)
                draw_callout_label(
                    ax, r2["CA"].coord, lbl_pos - r2["CA"].coord,
                    f"{c2_id}:{r2.resname}{r2.id[1]}", "#FDE68A", fontsize=8.8
                )
            if pair_key not in drawn_pairs:
                drawn_pairs.add(pair_key)
                line_col = "#FB7185" if d < 2.45 else ("#34D399" if d <= 3.5 else "#FDE047")
                mid = 0.5 * (a1.coord + a2.coord)
                lbl_pos = choose_non_overlapping_pos(mid, dist_offsets, placed_labels, min_sep=3.2)
                draw_distance_line(
                    ax, a1.coord, a2.coord,
                    f"{d:.2f} Å ({a1.name}–{a2.name})",
                    color=line_col, offset=lbl_pos - mid
                )

    ax.set_xlim(center[0] - radius, center[0] + radius)
    ax.set_ylim(center[1] - radius, center[1] + radius)
    ax.set_zlim(center[2] - radius, center[2] + radius)
    ax.view_init(elev=elev, azim=azim)


def cmd_closeup(args):
    """Render a single-panel 3D pocket close-up or dual-panel WT vs. Mutant comparison PNG."""
    focus_list = [parse_focus_token(t) for t in args.focus.split(",") if t.strip()]
    m1 = load_structure(args.pdb1, "p1")
    if args.pdb2:
        m2 = load_structure(args.pdb2, "p2")
        fig = plt.figure(figsize=(15.0, 7.0), facecolor="#060B16")
        if args.suptitle:
            fig.suptitle(args.suptitle, color="#F8FAFC", fontsize=13.5, fontweight="bold", y=0.98)
        ax1 = fig.add_subplot(1, 2, 1, projection="3d", computed_zorder=False)
        render_single_panel(
            ax1, m1, focus_list,
            args.title1 or os.path.basename(args.pdb1),
            args.subtitle1 or "", args.radius, args.elev, args.azim
        )
        ax2 = fig.add_subplot(1, 2, 2, projection="3d", computed_zorder=False)
        focus_list2 = [parse_focus_token(t) for t in (args.focus2 or args.focus).split(",") if t.strip()]
        render_single_panel(
            ax2, m2, focus_list2,
            args.title2 or os.path.basename(args.pdb2),
            args.subtitle2 or "", args.radius, args.elev, args.azim
        )
        plt.subplots_adjust(wspace=0.14, top=0.86, bottom=0.04, left=0.03, right=0.97)
    else:
        fig = plt.figure(figsize=(8.2, 7.0), facecolor="#060B16")
        if args.suptitle:
            fig.suptitle(args.suptitle, color="#F8FAFC", fontsize=13.0, fontweight="bold", y=0.98)
        ax1 = fig.add_subplot(1, 1, 1, projection="3d", computed_zorder=False)
        render_single_panel(
            ax1, m1, focus_list,
            args.title1 or os.path.basename(args.pdb1),
            args.subtitle1 or "", args.radius, args.elev, args.azim
        )
        plt.tight_layout()

    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    fig.savefig(args.out, dpi=200, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close(fig)
    print(f"Saved 3D close-up figure: {os.path.abspath(args.out)}")


def structure_to_subset_pdb_string(path, focus_chains=None, cutoff=16.0):
    """Extract primary chains and nearby interface residues into an embedded PDB string."""
    model = load_structure(path, "sub")
    all_chains = [c.id for c in model]
    if not focus_chains:
        focus_chains = all_chains[:2] if len(all_chains) >= 2 else all_chains

    hl_coords = []
    for cid in focus_chains:
        if cid in model:
            for r in model[cid]:
                for a in r:
                    hl_coords.append(a.coord)
    hl_coords = np.array(hl_coords) if hl_coords else np.zeros((0, 3))

    keep_res = set()
    for c in model:
        for r in c:
            if c.id in focus_chains or len(hl_coords) == 0:
                keep_res.add((c.id, r.id[1]))
            else:
                rc = np.array([a.coord for a in r])
                if len(rc) > 0:
                    dmin = np.min(np.linalg.norm(rc[:, None, :] - hl_coords[None, :, :], axis=-1))
                    if dmin <= cutoff:
                        keep_res.add((c.id, r.id[1]))

    class SubsetSelect(Select):
        def accept_residue(self, residue):
            return (residue.get_parent().id, residue.id[1]) in keep_res

    buf = io.StringIO()
    io_writer = PDBIO()
    io_writer.set_structure(model)
    io_writer.save(buf, SubsetSelect())
    return buf.getvalue(), model


def open_file_cross_platform(filepath):
    """Open a generated file in the default desktop application."""
    sys_name = platform.system().lower()
    if sys_name == "darwin":
        subprocess.run(["open", filepath], check=False)
    elif sys_name == "linux":
        subprocess.run(["xdg-open", filepath], check=False)
    elif sys_name == "windows":
        os.startfile(filepath)  # type: ignore[attr-defined]


def cmd_viewer(args):
    """Generate a standalone, zero-CORS 3Dmol.js interactive HTML canvas."""
    pdb_entries = {}
    first_model = None
    first_key = None
    for item in args.pdb:
        if "=" in item:
            k, p = item.split("=", 1)
        else:
            k = os.path.splitext(os.path.basename(item))[0]
            p = item
        pdb_str, model = structure_to_subset_pdb_string(p, cutoff=args.cutoff)
        pdb_entries[k] = pdb_str
        if first_model is None:
            first_model = model
            first_key = k

    focus_list = [parse_focus_token(t) for t in (args.focus or "").split(",") if t.strip()]
    scenes = []
    all_chains = [c.id for c in first_model]

    # Scene 0: Global Overview for each loaded model
    for m_idx, m_key in enumerate(pdb_entries.keys(), start=1):
        scenes.append({
            "id": f"overview_{m_key}",
            "title": f"🔭 View {m_idx}: {m_key} — Complex Overview",
            "subtitle": f"Chains {', '.join(all_chains)} with highlighted focal sites",
            "model": m_key,
            "zoom": {"chain": all_chains[:2] if len(all_chains) >= 2 else all_chains},
            "highlights": [
                {"chain": cid, "resi": rno, "color": "#10B981", "label": lbl or f"{cid}:{rno}"}
                for cid, rno, lbl in focus_list
            ],
            "note": (
                f"Active Model: <b>{m_key}</b>.<br>"
                f"Chains loaded: <b>{', '.join(all_chains)}</b>.<br>"
                "Use left-drag to rotate in 3D, scroll to zoom, and right-drag to pan."
            ),
        })

    # Auto-build per-focus pocket close-up scenes with neighbor detection
    base_idx = len(scenes) + 1
    for offset_idx, (cid, rno, lbl) in enumerate(focus_list):
        if cid not in first_model or rno not in first_model[cid]:
            continue
        scene_num = base_idx + offset_idx
        f_res = first_model[cid][rno]
        neighbors = []
        for c2 in first_model:
            for r2 in c2:
                if not is_std_aa(r2):
                    continue
                if c2.id == cid and abs(r2.id[1] - rno) <= 3:
                    continue
                d, a1, a2 = min_heavy_dist(f_res, r2)
                if d <= 4.2:
                    neighbors.append((d, c2.id, r2.id[1], r2.resname, a1.name, a2.name))
        neighbors.sort(key=lambda x: x[0])
        hl = [{
            "chain": cid,
            "resi": rno,
            "color": "#10B981",
            "label": lbl or f"{cid}:{f_res.resname}{rno}",
            "surface": True,
        }]
        nb_desc = []
        for d, nc, nr, nname, an1, an2 in neighbors[:4]:
            hl.append({"chain": nc, "resi": nr, "color": "#F59E0B", "label": f"{nc}:{nname}{nr} ({d:.2f}Å)"})
            nb_desc.append(f"<b>{nc}:{nname}{nr}</b> ({an1}–{an2} = {d:.2f} Å)")
        scenes.append({
            "id": f"focus_{scene_num}",
            "title": f"🎯 View {scene_num}: {lbl or (cid + ':' + f_res.resname + str(rno))} Pocket Close-Up",
            "subtitle": f"Auto-detected {len(neighbors[:4])} contacting residues within 4.2 Å",
            "model": first_key,
            "zoom": {"chain": cid, "resi": rno},
            "highlights": hl,
            "note": (
                f"Focal Residue: <b>{cid}:{f_res.resname}{rno}</b> ({lbl or 'primary site'}).<br>"
                "Nearest heavy-atom contacts (≤ 4.2 Å):<br>• "
                + ("<br>• ".join(nb_desc) if nb_desc else "No non-adjacent heavy-atom contacts within 4.2 Å")
            ),
        })

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>{args.title}</title>
<script src="https://3Dmol.org/build/3Dmol-min.js"></script>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; background: #060B16; color: #F8FAFC; display: flex; height: 100vh; overflow: hidden; }}
  #sidebar {{ width: 390px; background: #0F172A; border-right: 1px solid #1E293B; display: flex; flex-direction: column; padding: 18px; overflow-y: auto; z-index: 10; }}
  h1 {{ font-size: 16px; font-weight: 700; color: #38BDF8; margin-bottom: 6px; }}
  .sub {{ font-size: 12px; color: #94A3B8; line-height: 1.5; margin-bottom: 14px; padding-bottom: 12px; border-bottom: 1px solid #1E293B; }}
  .btn {{ display: block; width: 100%; text-align: left; background: #1E293B; color: #F1F5F9; border: 1px solid #334155; border-radius: 8px; padding: 10px 12px; margin-bottom: 8px; cursor: pointer; font-size: 13px; transition: all 0.15s ease; }}
  .btn:hover {{ background: #334155; border-color: #38BDF8; }}
  .btn.active {{ background: #0284C7; border-color: #38BDF8; color: #FFFFFF; }}
  .btn small {{ display: block; color: #CBD5E1; font-size: 11px; margin-top: 3px; }}
  #note-card {{ margin-top: 12px; background: #0B1120; border: 1px solid #334155; border-left: 4px solid #10B981; border-radius: 8px; padding: 12px; font-size: 12.5px; line-height: 1.6; }}
  #viewer-wrap {{ flex: 1; position: relative; }}
  #viewer {{ width: 100%; height: 100%; }}
  #hud {{ position: absolute; top: 16px; right: 16px; background: rgba(15, 23, 42, 0.88); border: 1px solid #334155; border-radius: 8px; padding: 10px 14px; font-size: 12px; color: #CBD5E1; pointer-events: none; }}
</style>
</head>
<body>
  <div id="sidebar">
    <h1>🧬 {args.title}</h1>
    <div class="sub">{args.subtitle}</div>
    <div id="btn-list"></div>
    <div id="note-card"><div id="note-body"></div></div>
  </div>
  <div id="viewer-wrap">
    <div id="viewer"></div>
    <div id="hud">🖱️ Left-drag: Rotate 3D &nbsp;|&nbsp; Scroll: Zoom &nbsp;|&nbsp; Right-drag: Pan</div>
  </div>
<script>
const PDB_MODELS = {json.dumps(pdb_entries)};
const SCENES = {json.dumps(scenes, ensure_ascii=False)};
const CHAIN_COLORS = {json.dumps(CHAIN_PALETTE)};
let viewer = null;

function renderScene(idx) {{
  const sc = SCENES[idx];
  document.querySelectorAll('.btn').forEach((b, i) => b.classList.toggle('active', i === idx));
  viewer.clear();
  viewer.addModel(PDB_MODELS[sc.model], 'pdb');
  const chains = {json.dumps(all_chains)};
  chains.forEach((cid, i) => {{
    viewer.setStyle({{ chain: cid }}, {{ cartoon: {{ color: CHAIN_COLORS[i % CHAIN_COLORS.length], opacity: i < 2 ? 0.84 : 0.52 }} }});
  }});
  (sc.highlights || []).forEach(h => {{
    const sel = {{ chain: h.chain, resi: h.resi }};
    viewer.setStyle(sel, {{
      cartoon: {{ color: h.color, opacity: 0.9 }},
      stick: {{ radius: 0.24, colorscheme: 'Jmol', color: h.color }},
      sphere: {{ scale: 0.28, colorscheme: 'Jmol' }}
    }});
    if (h.surface) {{
      viewer.addSurface($3Dmol.SurfaceType.VDW, {{ opacity: 0.35, color: h.color }}, sel);
    }}
    if (h.label) {{
      viewer.addResLabels(sel, {{ font: 'sans-serif', fontSize: 12, fontColor: '#F8FAFC', backgroundColor: '#0F172A', backgroundOpacity: 0.88, borderColor: h.color, borderThickness: 1.2 }});
    }}
  }});
  viewer.zoomTo(sc.zoom || {{}});
  viewer.render();
  document.getElementById('note-body').innerHTML = sc.note;
}}

window.addEventListener('DOMContentLoaded', () => {{
  const listEl = document.getElementById('btn-list');
  SCENES.forEach((sc, i) => {{
    const btn = document.createElement('button');
    btn.className = 'btn' + (i === 0 ? ' active' : '');
    btn.innerHTML = '<b>' + sc.title + '</b><small>' + sc.subtitle + '</small>';
    btn.onclick = () => renderScene(i);
    listEl.appendChild(btn);
  }});
  viewer = $3Dmol.createViewer(document.getElementById('viewer'), {{ backgroundColor: '#060B16' }});
  renderScene(0);
}});
</script>
</body>
</html>
"""
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"Saved interactive 3D viewer HTML: {os.path.abspath(args.out)}")
    if args.open:
        open_file_cross_platform(os.path.abspath(args.out))


def main():
    p = argparse.ArgumentParser(
        description="Biomolecular 3D Structure Viewer & Atomic Close-Up Renderer"
    )
    sub = p.add_subparsers(dest="cmd", required=True)

    p_ins = sub.add_parser(
        "inspect",
        help="Inspect chains, interface contacts, H-bonds/salt bridges, and steric clashes",
    )
    p_ins.add_argument("pdb", help="Path to .pdb or .cif file")
    p_ins.add_argument("--interface", help="Chain groups, e.g. 'H,L:A,B'", default=None)
    p_ins.add_argument("--cutoff", type=float, default=4.5, help="Heavy-atom contact distance cutoff (Å)")
    p_ins.add_argument("--top", type=int, default=40, help="Max contacts to display")
    p_ins.add_argument("--json-out", default=None, help="Optional JSON output file path")
    p_ins.set_defaults(func=cmd_inspect)

    p_cls = sub.add_parser(
        "closeup",
        help="Render 3D atomic close-up or side-by-side WT vs. Mutant PNG",
    )
    p_cls.add_argument("--pdb1", required=True, help="Primary (or WT) .pdb/.cif path")
    p_cls.add_argument("--pdb2", default=None, help="Optional second (Mutant) .pdb/.cif path for side-by-side comparison")
    p_cls.add_argument("--focus", required=True, help="Comma-separated focus residues, e.g. 'L:36:VL_Asn36,H:108:VH_Val108'")
    p_cls.add_argument("--focus2", default=None, help="Optional focus tokens for pdb2 if labels differ")
    p_cls.add_argument("--out", required=True, help="Output .png path")
    p_cls.add_argument("--suptitle", default=None, help="Figure super-title")
    p_cls.add_argument("--title1", default=None, help="Left/main panel title")
    p_cls.add_argument("--subtitle1", default=None, help="Left/main panel subtitle")
    p_cls.add_argument("--title2", default=None, help="Right panel title")
    p_cls.add_argument("--subtitle2", default=None, help="Right panel subtitle")
    p_cls.add_argument("--radius", type=float, default=7.2, help="3D bounding box half-width (Å)")
    p_cls.add_argument("--elev", type=float, default=20.0, help="3D camera elevation angle")
    p_cls.add_argument("--azim", type=float, default=-45.0, help="3D camera azimuth angle")
    p_cls.set_defaults(func=cmd_closeup)

    p_vw = sub.add_parser(
        "viewer",
        help="Generate standalone 3Dmol.js Shared 3D Canvas HTML",
    )
    p_vw.add_argument("--pdb", action="append", required=True, help="Model entry 'label=path.pdb' or 'path.pdb'")
    p_vw.add_argument("--focus", default="", help="Comma-separated focus residues 'Chain:ResNo[:Label]'")
    p_vw.add_argument("--title", default="Biomolecular 3D Structure Viewer", help="Viewer title")
    p_vw.add_argument(
        "--subtitle",
        default="Generated by <code>biomolecular-3d-viewer</code> — Embedded atomic coordinates & contact network.",
        help="Viewer sidebar subtitle",
    )
    p_vw.add_argument("--cutoff", type=float, default=16.0, help="Interface cropping cutoff (Å) around primary chains")
    p_vw.add_argument("--out", required=True, help="Output .html path")
    p_vw.add_argument("--open", action="store_true", help="Open generated HTML in default browser")
    p_vw.set_defaults(func=cmd_viewer)

    args = p.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
