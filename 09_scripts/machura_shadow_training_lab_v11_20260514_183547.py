#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import argparse
import csv
import hashlib
import itertools
import json
import math
from collections import Counter, defaultdict
from pathlib import Path


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def graph_from_bits(n: int, mask: int):
    adj = [[False] * n for _ in range(n)]
    p = 0
    for i in range(n):
        for j in range(i + 1, n):
            e = ((mask >> p) & 1) == 1
            adj[i][j] = e
            adj[j][i] = e
            p += 1
    return adj


def bits_string(n: int, mask: int) -> str:
    m = n * (n - 1) // 2
    return "".join("1" if ((mask >> p) & 1) else "0" for p in range(m))


def is_red_clique(adj, vertices) -> bool:
    return all(adj[i][j] for i, j in itertools.combinations(vertices, 2))


def is_blue_clique(adj, vertices) -> bool:
    return all(not adj[i][j] for i, j in itertools.combinations(vertices, 2))


def count_red_cliques(adj, k: int) -> int:
    n = len(adj)
    return sum(1 for c in itertools.combinations(range(n), k) if is_red_clique(adj, c))


def count_blue_cliques(adj, k: int) -> int:
    n = len(adj)
    return sum(1 for c in itertools.combinations(range(n), k) if is_blue_clique(adj, c))


def score(adj, a: int, b: int):
    r = count_red_cliques(adj, a)
    bl = count_blue_cliques(adj, b)
    return r, bl, r + bl


def predecessor_lists(adj, a: int, b: int):
    n = len(adj)
    red_need = a - 1
    blue_need = b - 1

    red = []
    blue = []

    for c in itertools.combinations(range(n), red_need):
        if is_red_clique(adj, c):
            red.append(c)

    for c in itertools.combinations(range(n), blue_need):
        if is_blue_clique(adj, c):
            blue.append(c)

    return red, blue


def phi_for_chi(red_pred, blue_pred, chi_bits, n: int):
    red_phi = 0
    blue_phi = 0

    for c in red_pred:
        if all(((chi_bits >> i) & 1) == 1 for i in c):
            red_phi += 1

    for c in blue_pred:
        if all(((chi_bits >> i) & 1) == 0 for i in c):
            blue_phi += 1

    return red_phi, blue_phi, red_phi + blue_phi


def near_pressure(red_pred, blue_pred, chi_bits, n: int, a: int, b: int):
    red_need = a - 1
    blue_need = b - 1

    red_near1 = 0
    red_near2 = 0
    blue_near1 = 0
    blue_near2 = 0

    for c in red_pred:
        cnt = sum(1 for i in c if ((chi_bits >> i) & 1) == 1)
        if cnt == red_need - 1:
            red_near1 += 1
        if cnt == red_need - 2:
            red_near2 += 1

    for c in blue_pred:
        cnt = sum(1 for i in c if ((chi_bits >> i) & 1) == 0)
        if cnt == blue_need - 1:
            blue_near1 += 1
        if cnt == blue_need - 2:
            blue_near2 += 1

    return red_near1, red_near2, blue_near1, blue_near2


def chi_string(chi_bits: int, n: int) -> str:
    return "".join("1" if ((chi_bits >> i) & 1) else "0" for i in range(n))


def analyze_case(a: int, b: int, n: int, outdir: Path, max_graphs: int = 0):
    edge_count = n * (n - 1) // 2
    total_graphs = 1 << edge_count

    if max_graphs and total_graphs > max_graphs:
        raise RuntimeError(
            f"Refusing exact enumeration: 2^{edge_count}={total_graphs} graphs exceeds max_graphs={max_graphs}"
        )

    graph_rows = []
    chi_rows = []

    clean_count = 0
    phi0_graphs = 0
    global_min_phi = None
    global_hist = Counter()

    for gmask in range(total_graphs):
        adj = graph_from_bits(n, gmask)
        red_s, blue_s, sc = score(adj, a, b)

        if sc != 0:
            continue

        clean_count += 1

        red_pred, blue_pred = predecessor_lists(adj, a, b)
        hist = Counter()

        min_phi = 10**9
        min_red_phi = None
        min_blue_phi = None
        min_degree = None
        min_chi = None
        phi0_count = 0
        phi1_count = 0

        for chi in range(1 << n):
            degree = chi.bit_count()

            rp, bp, ph = phi_for_chi(red_pred, blue_pred, chi, n)
            rn1, rn2, bn1, bn2 = near_pressure(red_pred, blue_pred, chi, n, a, b)

            hist[ph] += 1
            global_hist[ph] += 1

            if ph == 0:
                phi0_count += 1
            if ph == 1:
                phi1_count += 1

            if ph < min_phi:
                min_phi = ph
                min_red_phi = rp
                min_blue_phi = bp
                min_degree = degree
                min_chi = chi

            chi_rows.append({
                "a": a,
                "b": b,
                "n": n,
                "graph_index": clean_count,
                "graph_mask": gmask,
                "graph_bits_sha256": hashlib.sha256(bits_string(n, gmask).encode("ascii")).hexdigest(),
                "chi_bits": chi_string(chi, n),
                "degree": degree,
                "red_phi": rp,
                "blue_phi": bp,
                "phi": ph,
                "red_near1": rn1,
                "red_near2": rn2,
                "blue_near1": bn1,
                "blue_near2": bn2,
            })

        if phi0_count > 0:
            phi0_graphs += 1

        if global_min_phi is None or min_phi < global_min_phi:
            global_min_phi = min_phi

        graph_rows.append({
            "a": a,
            "b": b,
            "n": n,
            "graph_index": clean_count,
            "graph_mask": gmask,
            "graph_bits": bits_string(n, gmask),
            "graph_bits_sha256": hashlib.sha256(bits_string(n, gmask).encode("ascii")).hexdigest(),
            "red_pred_count": len(red_pred),
            "blue_pred_count": len(blue_pred),
            "min_phi": min_phi,
            "min_red_phi": min_red_phi,
            "min_blue_phi": min_blue_phi,
            "min_degree": min_degree,
            "min_chi": chi_string(min_chi, n),
            "phi0_count": phi0_count,
            "phi1_count": phi1_count,
            "phi_hist": json.dumps(dict(sorted(hist.items())), sort_keys=True),
        })

    graph_csv = outdir / f"GRAPH_SUMMARY_R{a}_{b}_N{n}.csv"
    chi_csv = outdir / f"CHI_TRAINING_R{a}_{b}_N{n}.csv"
    summary_json = outdir / f"SUMMARY_R{a}_{b}_N{n}.json"

    if graph_rows:
        with graph_csv.open("w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(graph_rows[0].keys()))
            w.writeheader()
            w.writerows(graph_rows)
    else:
        graph_csv.write_text("", encoding="utf-8")

    if chi_rows:
        with chi_csv.open("w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(chi_rows[0].keys()))
            w.writeheader()
            w.writerows(chi_rows)
    else:
        chi_csv.write_text("", encoding="utf-8")

    summary = {
        "case": f"R({a},{b}) layer n={n}",
        "a": a,
        "b": b,
        "n": n,
        "edge_count": edge_count,
        "total_graphs_enumerated": total_graphs,
        "clean_graphs": clean_count,
        "graphs_with_phi0": phi0_graphs,
        "global_min_phi": global_min_phi,
        "global_phi_hist": dict(sorted(global_hist.items())),
        "graph_summary_csv": str(graph_csv),
        "chi_training_csv": str(chi_csv),
    }

    summary_json.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")

    return summary


def write_manifest(outdir: Path):
    rows = []
    for p in sorted(outdir.glob("*")):
        if p.is_file() and p.name != "MANIFEST_SHA256.txt":
            rows.append(f"{sha256_file(p)}  {p.name}")
    manifest = outdir / "MANIFEST_SHA256.txt"
    manifest.write_text("\n".join(rows) + "\n", encoding="utf-8")
    return manifest


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--outdir", required=True)
    ap.add_argument("--case", action="append", required=True, help="format: a,b,n ; example 3,3,5")
    ap.add_argument("--max-graphs", type=int, default=2000000)
    args = ap.parse_args()

    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=False)

    all_summaries = []

    for c in args.case:
        a, b, n = [int(x.strip()) for x in c.split(",")]
        s = analyze_case(a, b, n, outdir, max_graphs=args.max_graphs)
        all_summaries.append(s)

    report = {
        "run_type": "MACHURA_SHADOW_TRAINING_LAB_V11",
        "cases": all_summaries,
    }

    report_path = outdir / "REPORT_SHADOW_TRAINING_LAB_V11.json"
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

    summary_txt = outdir / "SUMMARY_SHADOW_TRAINING_LAB_V11.txt"
    lines = [
        "MACHURA SHADOW TRAINING LAB V11",
        "================================",
        "",
        "Purpose:",
        "Exact small-case shadow training for learning what good chi profiles look like.",
        "",
    ]

    for s in all_summaries:
        lines.append(f"CASE: {s['case']}")
        lines.append(f"TOTAL_GRAPHS_ENUMERATED: {s['total_graphs_enumerated']}")
        lines.append(f"CLEAN_GRAPHS: {s['clean_graphs']}")
        lines.append(f"GRAPHS_WITH_PHI0: {s['graphs_with_phi0']}")
        lines.append(f"GLOBAL_MIN_PHI: {s['global_min_phi']}")
        lines.append(f"GLOBAL_PHI_HIST: {json.dumps(s['global_phi_hist'], sort_keys=True)}")
        lines.append("")

    summary_txt.write_text("\n".join(lines) + "\n", encoding="utf-8")

    manifest = write_manifest(outdir)

    print("DONE")
    print(f"REPORT: {report_path}")
    print(f"SUMMARY: {summary_txt}")
    print(f"MANIFEST: {manifest}")
    print(json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
