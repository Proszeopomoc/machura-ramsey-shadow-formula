#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import argparse
import csv
import hashlib
import itertools
import json
from collections import Counter, defaultdict
from pathlib import Path


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def edge_count(n: int) -> int:
    return n * (n - 1) // 2


def graph_from_bits(n: int, bits: str):
    bits = "".join(c for c in str(bits).strip() if c in "01")
    if len(bits) != edge_count(n):
        raise ValueError(f"Bad graph_bits length: got {len(bits)}, expected {edge_count(n)}")

    adj = [[False] * n for _ in range(n)]
    p = 0
    for i in range(n):
        for j in range(i + 1, n):
            e = bits[p] == "1"
            adj[i][j] = e
            adj[j][i] = e
            p += 1
    return adj


def bits_from_mask(n: int, mask: int) -> str:
    m = edge_count(n)
    return "".join("1" if ((mask >> p) & 1) else "0" for p in range(m))


def is_red_clique(adj, vertices) -> bool:
    return all(adj[i][j] for i, j in itertools.combinations(vertices, 2))


def is_blue_clique(adj, vertices) -> bool:
    return all(not adj[i][j] for i, j in itertools.combinations(vertices, 2))


def predecessor_terms(adj, a: int, b: int):
    n = len(adj)
    red_terms = []
    blue_terms = []

    for c in itertools.combinations(range(n), a - 1):
        if is_red_clique(adj, c):
            red_terms.append(tuple(c))

    for c in itertools.combinations(range(n), b - 1):
        if is_blue_clique(adj, c):
            blue_terms.append(tuple(c))

    return red_terms, blue_terms


def phi_for_chi(red_terms, blue_terms, chi_bits: int, n: int):
    red_phi = 0
    blue_phi = 0

    active_red = []
    active_blue = []

    for idx, term in enumerate(red_terms):
        if all(((chi_bits >> i) & 1) == 1 for i in term):
            red_phi += 1
            active_red.append(idx)

    for idx, term in enumerate(blue_terms):
        if all(((chi_bits >> i) & 1) == 0 for i in term):
            blue_phi += 1
            active_blue.append(idx)

    return red_phi, blue_phi, red_phi + blue_phi, active_red, active_blue


def chi_string(chi_bits: int, n: int) -> str:
    return "".join("1" if ((chi_bits >> i) & 1) else "0" for i in range(n))


def load_graph_rows(path: Path):
    with path.open("r", encoding="utf-8", errors="replace", newline="") as f:
        return list(csv.DictReader(f))


def get_graph_bits(row, n: int):
    for key in ["graph_bits", "bits", "graph_bitstring"]:
        if key in row and str(row[key]).strip():
            bits = "".join(c for c in str(row[key]).strip() if c in "01")
            if len(bits) == edge_count(n):
                return bits

    for key in ["graph_mask", "mask"]:
        if key in row and str(row[key]).strip() != "":
            return bits_from_mask(n, int(row[key]))

    raise ValueError("Cannot find graph_bits or graph_mask in row")


def term_incidence(n: int, terms):
    inc = [0] * n
    for term in terms:
        for v in term:
            inc[v] += 1
    return inc


def active_incidence(n: int, terms, active_ids):
    inc = [0] * n
    for idx in active_ids:
        for v in terms[idx]:
            inc[v] += 1
    return inc


def analyze_graph(row, a: int, b: int, n: int, graph_index: int):
    bits = get_graph_bits(row, n)
    adj = graph_from_bits(n, bits)

    red_terms, blue_terms = predecessor_terms(adj, a, b)

    red_inc = term_incidence(n, red_terms)
    blue_inc = term_incidence(n, blue_terms)

    min_phi = None
    min_chis = []
    phi_hist = Counter()

    best_data = None

    for chi in range(1 << n):
        rp, bp, ph, ar, ab = phi_for_chi(red_terms, blue_terms, chi, n)
        phi_hist[ph] += 1

        if min_phi is None or ph < min_phi:
            min_phi = ph
            min_chis = [chi]
            best_data = (rp, bp, ph, ar, ab)
        elif ph == min_phi:
            min_chis.append(chi)

    best_chi = min_chis[0]
    best_rp, best_bp, best_ph, active_red, active_blue = best_data

    active_red_inc = active_incidence(n, red_terms, active_red)
    active_blue_inc = active_incidence(n, blue_terms, active_blue)

    vertex_rows = []
    coord_counter = Counter()

    for v in range(n):
        x = 1 if ((best_chi >> v) & 1) else 0

        rowv = {
            "graph_index": graph_index,
            "v": v,
            "x_in_min_chi": x,
            "red_incidence": red_inc[v],
            "blue_incidence": blue_inc[v],
            "total_incidence": red_inc[v] + blue_inc[v],
            "active_red_incidence": active_red_inc[v],
            "active_blue_incidence": active_blue_inc[v],
            "active_total_incidence": active_red_inc[v] + active_blue_inc[v],
            "blocker_if_zero_red": red_inc[v],
            "blocker_if_one_blue": blue_inc[v],
        }

        vertex_rows.append(rowv)

        key = (
            x,
            red_inc[v],
            blue_inc[v],
            active_red_inc[v],
            active_blue_inc[v],
        )
        coord_counter[key] += 1

    coord_rows = []
    for key, cnt in sorted(coord_counter.items()):
        x, ri, bi, ari, abi = key
        coord_rows.append({
            "graph_index": graph_index,
            "x_in_min_chi": x,
            "red_incidence": ri,
            "blue_incidence": bi,
            "active_red_incidence": ari,
            "active_blue_incidence": abi,
            "class_size": cnt,
        })

    graph_summary = {
        "graph_index": graph_index,
        "graph_bits_sha256": hashlib.sha256(bits.encode("ascii")).hexdigest(),
        "n": n,
        "a": a,
        "b": b,
        "red_terms": len(red_terms),
        "blue_terms": len(blue_terms),
        "min_phi": min_phi,
        "min_red_phi": best_rp,
        "min_blue_phi": best_bp,
        "min_degree": best_chi.bit_count(),
        "min_chi_count": len(min_chis),
        "min_chi_first": chi_string(best_chi, n),
        "phi_hist": json.dumps(dict(sorted(phi_hist.items())), sort_keys=True),
        "coordinate_class_count": len(coord_rows),
        "max_red_incidence": max(red_inc) if red_inc else 0,
        "max_blue_incidence": max(blue_inc) if blue_inc else 0,
        "max_total_incidence": max([red_inc[i] + blue_inc[i] for i in range(n)]) if n else 0,
        "max_active_total_incidence": max([active_red_inc[i] + active_blue_inc[i] for i in range(n)]) if n else 0,
    }

    witness_rows = []
    for chi in min_chis:
        rp, bp, ph, ar, ab = phi_for_chi(red_terms, blue_terms, chi, n)
        witness_rows.append({
            "graph_index": graph_index,
            "chi": chi_string(chi, n),
            "degree": chi.bit_count(),
            "phi": ph,
            "red_phi": rp,
            "blue_phi": bp,
            "active_red_terms": ";".join(",".join(map(str, red_terms[i])) for i in ar),
            "active_blue_terms": ";".join(",".join(map(str, blue_terms[i])) for i in ab),
        })

    return graph_summary, vertex_rows, coord_rows, witness_rows


def write_csv(path: Path, rows):
    if not rows:
        path.write_text("", encoding="utf-8")
        return

    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--graph-summary", required=True)
    ap.add_argument("--outdir", required=True)
    ap.add_argument("--a", type=int, required=True)
    ap.add_argument("--b", type=int, required=True)
    ap.add_argument("--n", type=int, required=True)
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()

    graph_summary_path = Path(args.graph_summary)
    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=False)

    rows = load_graph_rows(graph_summary_path)
    if args.limit:
        rows = rows[:args.limit]

    graph_summaries = []
    vertex_rows_all = []
    coord_rows_all = []
    witness_rows_all = []

    for idx, row in enumerate(rows, start=1):
        gs, vr, cr, wr = analyze_graph(row, args.a, args.b, args.n, idx)
        graph_summaries.append(gs)
        vertex_rows_all.extend(vr)
        coord_rows_all.extend(cr)
        witness_rows_all.extend(wr)

    graph_csv = outdir / f"SHADOW_COORD_GRAPH_SUMMARY_R{args.a}_{args.b}_N{args.n}.csv"
    vertex_csv = outdir / f"SHADOW_VERTEX_COORDINATES_R{args.a}_{args.b}_N{args.n}.csv"
    classes_csv = outdir / f"SHADOW_COORDINATE_CLASSES_R{args.a}_{args.b}_N{args.n}.csv"
    witnesses_csv = outdir / f"SHADOW_MIN_WITNESSES_R{args.a}_{args.b}_N{args.n}.csv"

    write_csv(graph_csv, graph_summaries)
    write_csv(vertex_csv, vertex_rows_all)
    write_csv(classes_csv, coord_rows_all)
    write_csv(witnesses_csv, witness_rows_all)

    delta = min(int(r["min_phi"]) for r in graph_summaries) if graph_summaries else None
    hist_delta = Counter(int(r["min_phi"]) for r in graph_summaries)

    report = {
        "run_type": "MACHURA_SHADOW_COORDINATE_PROFILER_V16",
        "a": args.a,
        "b": args.b,
        "n": args.n,
        "input_graph_summary": str(graph_summary_path),
        "input_sha256": sha256_file(graph_summary_path),
        "graphs_analyzed": len(graph_summaries),
        "delta_min_over_input": delta,
        "min_phi_distribution": dict(sorted(hist_delta.items())),
        "outputs": {
            "graph_summary": str(graph_csv),
            "vertex_coordinates": str(vertex_csv),
            "coordinate_classes": str(classes_csv),
            "min_witnesses": str(witnesses_csv),
        },
    }

    report_path = outdir / "REPORT_SHADOW_COORDINATE_PROFILER_V16.json"
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

    summary_path = outdir / "SUMMARY_SHADOW_COORDINATE_PROFILER_V16.txt"
    lines = [
        "MACHURA SHADOW COORDINATE PROFILER V16",
        "=======================================",
        "",
        f"CASE: R({args.a},{args.b}) n={args.n}",
        f"GRAPHS_ANALYZED: {len(graph_summaries)}",
        f"DELTA_MIN_OVER_INPUT: {delta}",
        f"MIN_PHI_DISTRIBUTION: {json.dumps(dict(sorted(hist_delta.items())), sort_keys=True)}",
        "",
        "Outputs:",
        f"- {graph_csv}",
        f"- {vertex_csv}",
        f"- {classes_csv}",
        f"- {witnesses_csv}",
    ]
    summary_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print("DONE")
    print(f"REPORT: {report_path}")
    print(f"SUMMARY: {summary_path}")
    print(json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
