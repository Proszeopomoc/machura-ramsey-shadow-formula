#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import csv
import hashlib
import html
import math
from pathlib import Path


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def read_csv(path):
    with Path(path).open("r", encoding="utf-8", errors="replace", newline="") as f:
        return list(csv.DictReader(f))


def esc(x):
    return html.escape(str(x), quote=True)


def edge_pairs_from_bits(n, bits):
    bits = "".join(c for c in str(bits) if c in "01")
    edges = {}
    p = 0
    for i in range(n):
        for j in range(i + 1, n):
            edges[(i, j)] = int(bits[p])
            p += 1
    return edges


def parse_terms(s):
    out = []
    s = str(s or "").strip()
    if not s:
        return out
    for part in s.split(";"):
        part = part.strip()
        if not part:
            continue
        try:
            vals = tuple(int(x) for x in part.split(",") if x.strip() != "")
            if vals:
                out.append(vals)
        except Exception:
            pass
    return out


def find_first_witnesses(witness_rows):
    first = {}
    for r in witness_rows:
        gi = str(r.get("graph_index", "")).strip()
        if gi and gi not in first:
            first[gi] = r
    return first


def graph_panel(n, bits, graph_index, witness, x0, y0, size):
    cx = x0 + size / 2
    cy = y0 + size / 2 + 10
    rad = size * 0.32

    coords = {}
    for v in range(n):
        ang = -math.pi / 2 + 2 * math.pi * v / n
        coords[v] = (cx + rad * math.cos(ang), cy + rad * math.sin(ang))

    edges = edge_pairs_from_bits(n, bits)
    chi = str(witness.get("chi", "")).strip() if witness else ""
    red_phi = witness.get("red_phi", "") if witness else ""
    blue_phi = witness.get("blue_phi", "") if witness else ""
    phi = witness.get("phi", "") if witness else ""
    degree = witness.get("degree", "") if witness else ""

    active_red = set(tuple(sorted(t)) for t in parse_terms(witness.get("active_red_terms", "") if witness else ""))
    active_blue = set(tuple(sorted(t)) for t in parse_terms(witness.get("active_blue_terms", "") if witness else ""))

    parts = []
    parts.append(f"<g transform='translate({x0},{y0})'>")
    parts.append(f"<rect x='0' y='0' width='{size}' height='{size + 90}' fill='white' stroke='#444'/>")
    parts.append(f"<text x='10' y='20' font-family='Consolas, monospace' font-size='13' font-weight='bold'>Graph {graph_index}</text>")
    parts.append(f"<text x='10' y='40' font-family='Consolas, monospace' font-size='11'>chi={esc(chi)} deg={esc(degree)} Phi={esc(phi)} R={esc(red_phi)} B={esc(blue_phi)}</text>")

    # base edges
    for (i, j), val in edges.items():
        x1, y1 = coords[i]
        x2, y2 = coords[j]
        color = "#c62828" if val == 1 else "#1565c0"
        dash = "" if val == 1 else " stroke-dasharray='4 3'"
        width = 1.4
        parts.append(f"<line x1='{x1-x0:.2f}' y1='{y1-y0:.2f}' x2='{x2-x0:.2f}' y2='{y2-y0:.2f}' stroke='{color}' stroke-width='{width}'{dash}/>")

    # active red terms
    for term in active_red:
        if len(term) == 2:
            i, j = term
            x1, y1 = coords[i]
            x2, y2 = coords[j]
            parts.append(f"<line x1='{x1-x0:.2f}' y1='{y1-y0:.2f}' x2='{x2-x0:.2f}' y2='{y2-y0:.2f}' stroke='#ff0000' stroke-width='5' opacity='0.55'/>")

    # active blue terms
    for term in active_blue:
        if len(term) == 2:
            i, j = term
            x1, y1 = coords[i]
            x2, y2 = coords[j]
            parts.append(f"<line x1='{x1-x0:.2f}' y1='{y1-y0:.2f}' x2='{x2-x0:.2f}' y2='{y2-y0:.2f}' stroke='#003cff' stroke-width='5' opacity='0.45'/>")

    # nodes
    for v in range(n):
        x, y = coords[v]
        bit = chi[v] if v < len(chi) else "?"
        fill = "#ffdddd" if bit == "1" else "#dde8ff"
        stroke = "#aa0000" if bit == "1" else "#003c99"
        parts.append(f"<circle cx='{x-x0:.2f}' cy='{y-y0:.2f}' r='14' fill='{fill}' stroke='{stroke}' stroke-width='2'/>")
        parts.append(f"<text x='{x-x0-4:.2f}' y='{y-y0+5:.2f}' font-family='Consolas, monospace' font-size='13'>{v}</text>")

    parts.append(f"<text x='10' y='{size+60}' font-family='Consolas, monospace' font-size='10'>red edge = solid red, blue edge = dashed blue</text>")
    parts.append(f"<text x='10' y='{size+76}' font-family='Consolas, monospace' font-size='10'>thick edge = active minimal shadow term</text>")
    parts.append("</g>")
    return "\n".join(parts)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--graphs", required=True)
    ap.add_argument("--witnesses", required=True)
    ap.add_argument("--html", required=True)
    ap.add_argument("--svg", required=True)
    ap.add_argument("--summary", required=True)
    args = ap.parse_args()

    graph_rows = read_csv(args.graphs)
    witness_rows = read_csv(args.witnesses)
    first_witness = find_first_witnesses(witness_rows)

    n = 5
    panels = []
    panel_size = 220
    cols = 3
    gap = 24

    for idx, r in enumerate(graph_rows, start=1):
        bits = r.get("graph_bits", "")
        w = first_witness.get(str(idx), {})
        col = (idx - 1) % cols
        row = (idx - 1) // cols
        x = 30 + col * (panel_size + gap)
        y = 90 + row * (panel_size + 115)
        panels.append(graph_panel(n, bits, idx, w, x, y, panel_size))

    rows_count = math.ceil(len(graph_rows) / cols)
    width = 30 + cols * (panel_size + gap) + 20
    height = 100 + rows_count * (panel_size + 115) + 40

    svg = f"""<svg width="{width}" height="{height}" viewBox="0 0 {width} {height}" xmlns="http://www.w3.org/2000/svg">
<rect x="0" y="0" width="{width}" height="{height}" fill="white"/>
<text x="30" y="35" font-family="Consolas, monospace" font-size="22" font-weight="bold">Machura Shadow Graph Visual V02 - R(3,3), K5 critical cores</text>
<text x="30" y="60" font-family="Consolas, monospace" font-size="13">Each panel shows one clean K5 core, first minimal Phi=2 witness chi, and active shadow terms.</text>
{chr(10).join(panels)}
</svg>
"""

    Path(args.svg).write_text(svg, encoding="utf-8")

    html_out = f"""<!doctype html>
<html>
<head>
<meta charset="utf-8">
<title>Machura Shadow Graph Visual V02</title>
<style>
body {{ font-family: Consolas, monospace; margin: 28px; }}
.card {{ border: 1px solid #aaa; padding: 16px; margin-bottom: 18px; border-radius: 8px; }}
pre {{ background: #f6f6f6; padding: 12px; border: 1px solid #ddd; }}
svg {{ max-width: 100%; height: auto; }}
</style>
</head>
<body>
<h1>Machura Shadow Graph Visual V02</h1>
<div class="card">
<h2>What is shown</h2>
<p>This visual report adds the missing graph visualization layer.</p>
<p>Each panel shows a clean K5 core for R(3,3), red and blue edges, one minimal witness chi with Phi=2, and active minimal shadow terms.</p>
<pre>Node fill:
red fill  = chi_i = 1
blue fill = chi_i = 0

Edges:
solid red  = red edge in G
dashed blue = blue edge in complement G^c
thick edge = active term in the minimal shadow</pre>
</div>
<div class="card">
{svg}
</div>
<div class="card">
<h2>Input files</h2>
<pre>Graphs: {esc(args.graphs)}
SHA256: {sha256_file(Path(args.graphs))}

Witnesses: {esc(args.witnesses)}
SHA256: {sha256_file(Path(args.witnesses))}</pre>
</div>
</body>
</html>
"""

    Path(args.html).write_text(html_out, encoding="utf-8")

    summary = f"""MACHURA SHADOW GRAPH VISUAL V02
===============================

Graphs: {args.graphs}
Graphs SHA256: {sha256_file(Path(args.graphs))}

Witnesses: {args.witnesses}
Witnesses SHA256: {sha256_file(Path(args.witnesses))}

HTML: {args.html}
SVG: {args.svg}

Panels: {len(graph_rows)}
Meaning:
Each panel shows one clean K5 core for R(3,3), red/blue edge coloring,
one minimal Phi=2 chi witness, and the active shadow terms.
"""
    Path(args.summary).write_text(summary, encoding="utf-8")

    print("DONE")
    print("HTML:", args.html)
    print("SVG:", args.svg)
    print("SUMMARY:", args.summary)


if __name__ == "__main__":
    main()
