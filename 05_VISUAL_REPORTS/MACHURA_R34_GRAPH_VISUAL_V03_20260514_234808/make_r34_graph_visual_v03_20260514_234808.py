#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import csv
import hashlib
import html
import math
from pathlib import Path
from collections import Counter


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


def detect_graph_bits(row, n):
    need = n * (n - 1) // 2

    for key, val in row.items():
        s = "".join(c for c in str(val) if c in "01")
        if len(s) == need:
            return s

    for key in ["graph_mask", "mask"]:
        if key in row and str(row[key]).strip() != "":
            m = int(row[key])
            return "".join("1" if ((m >> p) & 1) else "0" for p in range(need))

    raise ValueError("cannot detect graph bits")


def adj_from_bits(n, bits):
    adj = [[False] * n for _ in range(n)]
    p = 0
    for i in range(n):
        for j in range(i + 1, n):
            e = bits[p] == "1"
            adj[i][j] = e
            adj[j][i] = e
            p += 1
    return adj


def red_clique(adj, verts):
    for a in range(len(verts)):
        for b in range(a + 1, len(verts)):
            if not adj[verts[a]][verts[b]]:
                return False
    return True


def blue_clique(adj, verts):
    for a in range(len(verts)):
        for b in range(a + 1, len(verts)):
            if adj[verts[a]][verts[b]]:
                return False
    return True


def combinations(items, k):
    if k == 0:
        yield ()
        return
    if len(items) < k:
        return
    if k == 1:
        for x in items:
            yield (x,)
        return
    for i, x in enumerate(items):
        for rest in combinations(items[i + 1:], k - 1):
            yield (x,) + rest


def predecessor_terms(adj, a, b):
    n = len(adj)
    verts = list(range(n))

    red = []
    blue = []

    for c in combinations(verts, a - 1):
        if red_clique(adj, c):
            red.append(c)

    for c in combinations(verts, b - 1):
        if blue_clique(adj, c):
            blue.append(c)

    return red, blue


def phi_for_chi(red_terms, blue_terms, chi, n):
    red_phi = 0
    blue_phi = 0
    active_red = []
    active_blue = []

    for t in red_terms:
        if all(((chi >> i) & 1) == 1 for i in t):
            red_phi += 1
            active_red.append(t)

    for t in blue_terms:
        if all(((chi >> i) & 1) == 0 for i in t):
            blue_phi += 1
            active_blue.append(t)

    return red_phi, blue_phi, red_phi + blue_phi, active_red, active_blue


def best_witness(red_terms, blue_terms, n):
    best = None
    best_list = []

    for chi in range(1 << n):
        rp, bp, ph, ar, ab = phi_for_chi(red_terms, blue_terms, chi, n)
        if best is None or ph < best[0]:
            best = (ph, rp, bp, chi, ar, ab)
            best_list = [best]
        elif ph == best[0]:
            best_list.append((ph, rp, bp, chi, ar, ab))

    return best_list[0], len(best_list)


def chi_string(chi, n):
    return "".join("1" if ((chi >> i) & 1) else "0" for i in range(n))


def edge_pairs_from_bits(n, bits):
    edges = {}
    p = 0
    for i in range(n):
        for j in range(i + 1, n):
            edges[(i, j)] = int(bits[p])
            p += 1
    return edges


def draw_panel(n, bits, idx, wit, witness_count, x0, y0, size):
    adj = adj_from_bits(n, bits)
    edges = edge_pairs_from_bits(n, bits)

    ph, rp, bp, chi, active_red, active_blue = wit
    chi_s = chi_string(chi, n)

    cx = x0 + size / 2
    cy = y0 + size / 2 + 18
    rad = size * 0.36

    coords = {}
    for v in range(n):
        ang = -math.pi / 2 + 2 * math.pi * v / n
        coords[v] = (cx + rad * math.cos(ang), cy + rad * math.sin(ang))

    parts = []
    parts.append(f"<g transform='translate({x0},{y0})'>")
    parts.append(f"<rect x='0' y='0' width='{size}' height='{size + 105}' fill='white' stroke='#333'/>")
    parts.append(f"<text x='10' y='20' font-family='Consolas, monospace' font-size='13' font-weight='bold'>R(3,4) K8 core {idx}</text>")
    parts.append(f"<text x='10' y='40' font-family='Consolas, monospace' font-size='10'>chi={chi_s} Phi={ph} red={rp} blue={bp} witnesses={witness_count}</text>")

    for (i, j), val in edges.items():
        x1, y1 = coords[i]
        x2, y2 = coords[j]
        color = "#c62828" if val == 1 else "#1565c0"
        dash = "" if val == 1 else " stroke-dasharray='4 3'"
        parts.append(f"<line x1='{x1-x0:.2f}' y1='{y1-y0:.2f}' x2='{x2-x0:.2f}' y2='{y2-y0:.2f}' stroke='{color}' stroke-width='1.2'{dash}/>")

    for term in active_red:
        if len(term) == 2:
            i, j = term
            x1, y1 = coords[i]
            x2, y2 = coords[j]
            parts.append(f"<line x1='{x1-x0:.2f}' y1='{y1-y0:.2f}' x2='{x2-x0:.2f}' y2='{y2-y0:.2f}' stroke='#ff0000' stroke-width='5' opacity='0.60'/>")

    for term in active_blue:
        # blue active term is a triangle for R(3,4)
        for a in range(len(term)):
            for b in range(a + 1, len(term)):
                i = term[a]
                j = term[b]
                x1, y1 = coords[i]
                x2, y2 = coords[j]
                parts.append(f"<line x1='{x1-x0:.2f}' y1='{y1-y0:.2f}' x2='{x2-x0:.2f}' y2='{y2-y0:.2f}' stroke='#003cff' stroke-width='4' opacity='0.45'/>")

    for v in range(n):
        x, y = coords[v]
        bit = chi_s[v]
        fill = "#ffdddd" if bit == "1" else "#dde8ff"
        stroke = "#aa0000" if bit == "1" else "#003c99"
        parts.append(f"<circle cx='{x-x0:.2f}' cy='{y-y0:.2f}' r='13' fill='{fill}' stroke='{stroke}' stroke-width='2'/>")
        parts.append(f"<text x='{x-x0-4:.2f}' y='{y-y0+5:.2f}' font-family='Consolas, monospace' font-size='12'>{v}</text>")

    parts.append(f"<text x='10' y='{size+70}' font-family='Consolas, monospace' font-size='10'>solid red = red edge, dashed blue = complement edge</text>")
    parts.append(f"<text x='10' y='{size+86}' font-family='Consolas, monospace' font-size='10'>thick red edge or blue triangle = active Phi term</text>")
    parts.append("</g>")

    return "\n".join(parts)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--graphs", required=True)
    ap.add_argument("--html", required=True)
    ap.add_argument("--svg", required=True)
    ap.add_argument("--summary", required=True)
    ap.add_argument("--limit", type=int, default=12)
    args = ap.parse_args()

    rows = read_csv(args.graphs)
    rows = rows[:args.limit]

    n = 8
    a = 3
    b = 4

    panels = []
    data_rows = []
    type_counter = Counter()

    panel_size = 250
    cols = 3
    gap = 26

    for idx, r in enumerate(rows, start=1):
        bits = detect_graph_bits(r, n)
        adj = adj_from_bits(n, bits)
        red_terms, blue_terms = predecessor_terms(adj, a, b)
        wit, witness_count = best_witness(red_terms, blue_terms, n)
        ph, rp, bp, chi, ar, ab = wit

        type_counter[(rp, bp)] += 1

        col = (idx - 1) % cols
        row = (idx - 1) // cols
        x = 30 + col * (panel_size + gap)
        y = 95 + row * (panel_size + 130)

        panels.append(draw_panel(n, bits, idx, wit, witness_count, x, y, panel_size))

        data_rows.append({
            "idx": idx,
            "red_terms": len(red_terms),
            "blue_terms": len(blue_terms),
            "phi": ph,
            "red_phi": rp,
            "blue_phi": bp,
            "degree": bin(chi).count("1"),
            "chi": chi_string(chi, n),
            "min_witness_count": witness_count,
        })

    rows_count = math.ceil(len(rows) / cols)
    width = 30 + cols * (panel_size + gap) + 30
    height = 110 + rows_count * (panel_size + 130) + 40

    svg = f"""<svg width="{width}" height="{height}" viewBox="0 0 {width} {height}" xmlns="http://www.w3.org/2000/svg">
<rect x="0" y="0" width="{width}" height="{height}" fill="white"/>
<text x="30" y="35" font-family="Consolas, monospace" font-size="22" font-weight="bold">Machura Shadow Graph Visual V03 - R(3,4), K8 critical cores</text>
<text x="30" y="62" font-family="Consolas, monospace" font-size="13">Panels show clean K8 cores, one minimal Phi witness, and active red K2 or blue K3 shadow terms.</text>
{chr(10).join(panels)}
</svg>
"""

    Path(args.svg).write_text(svg, encoding="utf-8")

    table_rows = "\n".join(
        f"<tr><td>{d['idx']}</td><td>{d['red_terms']}</td><td>{d['blue_terms']}</td><td>{d['phi']}</td><td>{d['red_phi']}</td><td>{d['blue_phi']}</td><td>{d['degree']}</td><td>{esc(d['chi'])}</td><td>{d['min_witness_count']}</td></tr>"
        for d in data_rows
    )

    type_rows = "\n".join(
        f"<tr><td>red={k[0]}, blue={k[1]}</td><td>{v}</td></tr>"
        for k, v in sorted(type_counter.items())
    )

    html_out = f"""<!doctype html>
<html>
<head>
<meta charset="utf-8">
<title>Machura R(3,4) Graph Visual V03</title>
<style>
body {{ font-family: Consolas, monospace; margin: 28px; color: #111; }}
.card {{ border: 1px solid #aaa; padding: 16px; margin-bottom: 18px; border-radius: 8px; }}
table {{ border-collapse: collapse; width: 100%; margin-top: 10px; }}
th, td {{ border: 1px solid #aaa; padding: 6px 8px; text-align: left; }}
th {{ background: #eee; }}
pre {{ background: #f6f6f6; padding: 12px; border: 1px solid #ddd; }}
svg {{ max-width: 100%; height: auto; }}
</style>
</head>
<body>
<h1>Machura Shadow Graph Visual V03 - R(3,4)</h1>

<div class="card">
<h2>Purpose</h2>
<p>This report visualizes sampled clean K8 cores for R(3,4), one minimal shadow witness chi per core, and active Phi terms.</p>
<pre>R(3,4):
red predecessor terms are K2
blue predecessor terms are K3

solid red edge = red edge in G
dashed blue edge = blue edge in G^c
thick red edge = active red term
thick blue triangle = active blue term</pre>
</div>

<div class="card">
<h2>Sample summary</h2>
<table>
<tr><th>core</th><th>red terms</th><th>blue terms</th><th>Phi</th><th>red_phi</th><th>blue_phi</th><th>degree</th><th>chi</th><th>min witness count</th></tr>
{table_rows}
</table>
</div>

<div class="card">
<h2>Minimal shadow type distribution in sample</h2>
<table>
<tr><th>type</th><th>count</th></tr>
{type_rows}
</table>
</div>

<div class="card">
<h2>Graph panels</h2>
{svg}
</div>

<div class="card">
<h2>Input</h2>
<pre>Graphs: {esc(args.graphs)}
SHA256: {sha256_file(Path(args.graphs))}</pre>
</div>
</body>
</html>
"""

    Path(args.html).write_text(html_out, encoding="utf-8")

    summary = [
        "MACHURA R34 GRAPH VISUAL V03",
        "============================",
        "",
        f"Graphs: {args.graphs}",
        f"Graphs SHA256: {sha256_file(Path(args.graphs))}",
        f"Panels: {len(rows)}",
        "",
        "Type counts:",
    ]

    for k, v in sorted(type_counter.items()):
        summary.append(f"red={k[0]}, blue={k[1]}: {v}")

    Path(args.summary).write_text("\n".join(summary) + "\n", encoding="utf-8")

    print("DONE")
    print("HTML:", args.html)
    print("SVG:", args.svg)
    print("SUMMARY:", args.summary)


if __name__ == "__main__":
    main()
