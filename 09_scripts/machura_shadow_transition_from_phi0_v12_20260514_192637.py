#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import argparse
import csv
import hashlib
import itertools
import json
from collections import Counter
from pathlib import Path


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def graph_from_bits(n: int, bits: str):
    adj = [[False] * n for _ in range(n)]
    p = 0
    bits = bits.strip()
    need = n * (n - 1) // 2
    if len(bits) != need:
        raise ValueError(f"bad graph_bits length for n={n}: got {len(bits)}, need {need}")

    for i in range(n):
        for j in range(i + 1, n):
            e = bits[p] == "1"
            adj[i][j] = e
            adj[j][i] = e
            p += 1

    return adj


def bits_from_graph(adj):
    n = len(adj)
    out = []
    for i in range(n):
        for j in range(i + 1, n):
            out.append("1" if adj[i][j] else "0")
    return "".join(out)


def extend_graph(adj, chi_bits: str):
    n = len(adj)
    if len(chi_bits) != n:
        raise ValueError(f"bad chi length: got {len(chi_bits)}, need {n}")

    out = [[False] * (n + 1) for _ in range(n + 1)]

    for i in range(n):
        for j in range(n):
            out[i][j] = adj[i][j]

    new = n

    for i, c in enumerate(chi_bits):
        e = c == "1"
        out[i][new] = e
        out[new][i] = e

    return out


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


def phi_for_chi(red_pred, blue_pred, chi_int: int, n: int):
    red_phi = 0
    blue_phi = 0

    for c in red_pred:
        if all(((chi_int >> i) & 1) == 1 for i in c):
            red_phi += 1

    for c in blue_pred:
        if all(((chi_int >> i) & 1) == 0 for i in c):
            blue_phi += 1

    return red_phi, blue_phi, red_phi + blue_phi


def chi_string(chi_int: int, n: int) -> str:
    return "".join("1" if ((chi_int >> i) & 1) else "0" for i in range(n))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--graph-summary", required=True, help="GRAPH_SUMMARY_Ra_b_Nn.csv from V11")
    ap.add_argument("--chi-training", required=True, help="CHI_TRAINING_Ra_b_Nn.csv from V11")
    ap.add_argument("--outdir", required=True)
    ap.add_argument("--a", type=int, required=True)
    ap.add_argument("--b", type=int, required=True)
    ap.add_argument("--source-n", type=int, required=True)
    ap.add_argument("--expect-phi0-extended", type=int, default=-1)
    args = ap.parse_args()

    graph_summary = Path(args.graph_summary)
    chi_training = Path(args.chi_training)
    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=False)

    # Map graph_mask -> graph_bits from source clean layer.
    graph_bits_by_mask = {}

    with graph_summary.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            graph_bits_by_mask[row["graph_mask"]] = row["graph_bits"]

    extended = {}
    source_rows = 0
    phi0_source_rows = 0

    # Reconstruct C_{n+1} from Phi=0 rows.
    with chi_training.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            source_rows += 1

            if int(row["phi"]) != 0:
                continue

            phi0_source_rows += 1

            gmask = row["graph_mask"]
            chi = row["chi_bits"]

            if gmask not in graph_bits_by_mask:
                raise ValueError(f"missing graph mask in summary: {gmask}")

            adj = graph_from_bits(args.source_n, graph_bits_by_mask[gmask])
            ext = extend_graph(adj, chi)
            ext_bits = bits_from_graph(ext)
            ext_hash = hashlib.sha256(ext_bits.encode("ascii")).hexdigest()

            extended[ext_hash] = ext_bits

    target_n = args.source_n + 1

    ext_csv = outdir / f"EXTENDED_CLEAN_LAYER_R{args.a}_{args.b}_N{target_n}_FROM_PHI0.csv"

    with ext_csv.open("w", encoding="utf-8", newline="") as f:
        fieldnames = ["extended_index", "n", "graph_bits_sha256", "graph_bits"]
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()

        for idx, (h, bits) in enumerate(sorted(extended.items()), start=1):
            w.writerow({
                "extended_index": idx,
                "n": target_n,
                "graph_bits_sha256": h,
                "graph_bits": bits,
            })

    # Now compute shadow from C_{n+1} -> C_{n+2}
    graph_rows = []
    chi_rows = []

    global_hist = Counter()
    global_min_phi = None
    graphs_with_phi0 = 0
    total_phi0 = 0
    total_phi1 = 0
    total_phi2 = 0

    for idx, (h, bits) in enumerate(sorted(extended.items()), start=1):
        adj = graph_from_bits(target_n, bits)
        rs, bs, sc = score(adj, args.a, args.b)

        if sc != 0:
            raise ValueError(f"reconstructed graph is not clean: idx={idx}, score={sc}")

        red_pred, blue_pred = predecessor_lists(adj, args.a, args.b)

        hist = Counter()
        min_phi = 10**9
        min_red_phi = None
        min_blue_phi = None
        min_degree = None
        min_chi = None
        phi0_count = 0
        phi1_count = 0
        phi2_count = 0

        for chi_int in range(1 << target_n):
            deg = chi_int.bit_count()
            rp, bp, ph = phi_for_chi(red_pred, blue_pred, chi_int, target_n)

            hist[ph] += 1
            global_hist[ph] += 1

            if ph == 0:
                phi0_count += 1
                total_phi0 += 1
            elif ph == 1:
                phi1_count += 1
                total_phi1 += 1
            elif ph == 2:
                phi2_count += 1
                total_phi2 += 1

            if ph < min_phi:
                min_phi = ph
                min_red_phi = rp
                min_blue_phi = bp
                min_degree = deg
                min_chi = chi_string(chi_int, target_n)

            chi_rows.append({
                "a": args.a,
                "b": args.b,
                "n": target_n,
                "graph_index": idx,
                "graph_bits_sha256": h,
                "chi_bits": chi_string(chi_int, target_n),
                "degree": deg,
                "red_phi": rp,
                "blue_phi": bp,
                "phi": ph,
            })

        if phi0_count > 0:
            graphs_with_phi0 += 1

        if global_min_phi is None or min_phi < global_min_phi:
            global_min_phi = min_phi

        graph_rows.append({
            "a": args.a,
            "b": args.b,
            "n": target_n,
            "graph_index": idx,
            "graph_bits_sha256": h,
            "red_pred_count": len(red_pred),
            "blue_pred_count": len(blue_pred),
            "min_phi": min_phi,
            "min_red_phi": min_red_phi,
            "min_blue_phi": min_blue_phi,
            "min_degree": min_degree,
            "min_chi": min_chi,
            "phi0_count": phi0_count,
            "phi1_count": phi1_count,
            "phi2_count": phi2_count,
            "phi_hist": json.dumps(dict(sorted(hist.items())), sort_keys=True),
        })

    graph_csv = outdir / f"GRAPH_SUMMARY_R{args.a}_{args.b}_N{target_n}_TRANSITION.csv"
    chi_csv = outdir / f"CHI_TRAINING_R{args.a}_{args.b}_N{target_n}_TRANSITION.csv"
    report_json = outdir / "REPORT_SHADOW_TRANSITION_FROM_PHI0_V12.json"
    summary_txt = outdir / "SUMMARY_SHADOW_TRANSITION_FROM_PHI0_V12.txt"

    with graph_csv.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(graph_rows[0].keys()) if graph_rows else [])
        if graph_rows:
            w.writeheader()
            w.writerows(graph_rows)

    with chi_csv.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(chi_rows[0].keys()) if chi_rows else [])
        if chi_rows:
            w.writeheader()
            w.writerows(chi_rows)

    status = "DONE"
    if args.expect_phi0_extended >= 0:
        status = "PASS_EXPECTED_PHI0_COUNT" if total_phi0 == args.expect_phi0_extended else "REVIEW_EXPECTED_PHI0_COUNT"

    report = {
        "run_type": "MACHURA_SHADOW_TRANSITION_FROM_PHI0_V12",
        "status": status,
        "a": args.a,
        "b": args.b,
        "source_n": args.source_n,
        "target_n": target_n,
        "source_graph_summary": str(graph_summary),
        "source_chi_training": str(chi_training),
        "source_graph_summary_sha256": sha256_file(graph_summary),
        "source_chi_training_sha256": sha256_file(chi_training),
        "source_rows": source_rows,
        "phi0_source_rows": phi0_source_rows,
        "reconstructed_clean_graphs_n_plus_1": len(extended),
        "graphs_with_phi0_to_next_layer": graphs_with_phi0,
        "total_phi0_to_next_layer": total_phi0,
        "total_phi1_to_next_layer": total_phi1,
        "total_phi2_to_next_layer": total_phi2,
        "global_min_phi_to_next_layer": global_min_phi,
        "global_phi_hist_to_next_layer": dict(sorted(global_hist.items())),
        "expected_phi0_extended": args.expect_phi0_extended,
        "extended_clean_layer_csv": str(ext_csv),
        "graph_summary_csv": str(graph_csv),
        "chi_training_csv": str(chi_csv),
    }

    report_json.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

    lines = [
        "MACHURA SHADOW TRANSITION FROM PHI0 V12",
        "=======================================",
        "",
        f"STATUS: {status}",
        f"CASE: R({args.a},{args.b})",
        f"SOURCE_N: {args.source_n}",
        f"TARGET_N: {target_n}",
        f"SOURCE_ROWS: {source_rows}",
        f"PHI0_SOURCE_ROWS: {phi0_source_rows}",
        f"RECONSTRUCTED_CLEAN_GRAPHS_N_PLUS_1: {len(extended)}",
        f"GRAPHS_WITH_PHI0_TO_NEXT_LAYER: {graphs_with_phi0}",
        f"TOTAL_PHI0_TO_NEXT_LAYER: {total_phi0}",
        f"TOTAL_PHI1_TO_NEXT_LAYER: {total_phi1}",
        f"TOTAL_PHI2_TO_NEXT_LAYER: {total_phi2}",
        f"GLOBAL_MIN_PHI_TO_NEXT_LAYER: {global_min_phi}",
        f"GLOBAL_PHI_HIST_TO_NEXT_LAYER: {json.dumps(dict(sorted(global_hist.items())), sort_keys=True)}",
        "",
        "Meaning:",
        "Phi=0 rows from layer n reconstruct the clean layer n+1.",
        "Then the shadow from n+1 to n+2 is computed exactly.",
    ]

    summary_txt.write_text("\n".join(lines) + "\n", encoding="utf-8")

    manifest = outdir / "MANIFEST_SHA256.txt"
    files = [ext_csv, graph_csv, chi_csv, report_json, summary_txt]
    manifest.write_text(
        "".join(f"{sha256_file(p)}  {p.name}\n" for p in files),
        encoding="utf-8"
    )

    print("DONE")
    print(f"STATUS: {status}")
    print(f"REPORT: {report_json}")
    print(f"SUMMARY: {summary_txt}")
    print(f"MANIFEST: {manifest}")
    print(json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
