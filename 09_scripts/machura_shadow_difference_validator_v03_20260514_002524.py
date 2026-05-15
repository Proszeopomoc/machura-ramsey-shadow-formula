#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import math
from pathlib import Path
from typing import List, Tuple, Dict, Any

Adj = List[List[bool]]


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def sha256_text(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def infer_n_from_edge_bits(m: int) -> int:
    disc = 1 + 8 * m
    r = int(math.isqrt(disc))
    if r * r != disc:
        raise ValueError(f"Cannot infer n from {m} edge bits")
    n = (1 + r) // 2
    if n * (n - 1) // 2 != m:
        raise ValueError(f"Cannot infer n from {m} edge bits")
    return n


def decode_edge_bits(bits: str) -> Adj:
    bits = "".join(c for c in bits.strip() if c in "01")
    n = infer_n_from_edge_bits(len(bits))
    adj = [[False] * n for _ in range(n)]
    p = 0
    for i in range(n):
        for j in range(i + 1, n):
            val = bits[p] == "1"
            adj[i][j] = val
            adj[j][i] = val
            p += 1
    return adj


def decode_graph6(line: str) -> Adj:
    s = line.strip()
    if s.startswith(">>graph6<<"):
        s = s[len(">>graph6<<"):]

    vals = [ord(c) - 63 for c in s]
    first = vals[0]
    pos = 1

    if first <= 62:
        n = first
    elif first == 63:
        n = (vals[1] << 12) | (vals[2] << 6) | vals[3]
        pos = 4
    else:
        raise ValueError("Unsupported graph6 n encoding")

    need = n * (n - 1) // 2
    data_bits = []
    for val in vals[pos:]:
        for k in range(5, -1, -1):
            data_bits.append((val >> k) & 1)

    if len(data_bits) < need:
        raise ValueError("graph6 data too short")

    adj = [[False] * n for _ in range(n)]
    p = 0
    for j in range(1, n):
        for i in range(j):
            edge = bool(data_bits[p])
            adj[i][j] = edge
            adj[j][i] = edge
            p += 1

    return adj


def read_graphs(path: Path):
    out = []
    with path.open("r", encoding="utf-8", errors="replace") as f:
        for lineno, raw in enumerate(f, start=1):
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            token = line.split()[0]
            if set(token) <= {"0", "1"}:
                adj = decode_edge_bits(token)
            else:
                adj = decode_graph6(token)
            out.append((lineno, token, adj))
    return out


def is_red_clique(adj: Adj, vertices: Tuple[int, ...]) -> bool:
    return all(adj[i][j] for i, j in itertools.combinations(vertices, 2))


def is_blue_clique(adj: Adj, vertices: Tuple[int, ...]) -> bool:
    return all(not adj[i][j] for i, j in itertools.combinations(vertices, 2))


def count_red_cliques(adj: Adj, k: int) -> int:
    return sum(
        1 for comb in itertools.combinations(range(len(adj)), k)
        if is_red_clique(adj, comb)
    )


def count_blue_cliques(adj: Adj, k: int) -> int:
    return sum(
        1 for comb in itertools.combinations(range(len(adj)), k)
        if is_blue_clique(adj, comb)
    )


def score(adj: Adj, a: int, b: int) -> Dict[str, int]:
    red = count_red_cliques(adj, a)
    blue = count_blue_cliques(adj, b)
    return {
        "red_score": red,
        "blue_score": blue,
        "score": red + blue,
    }


def delete_vertex(adj: Adj, v: int) -> Tuple[Adj, List[bool]]:
    n = len(adj)
    keep = [i for i in range(n) if i != v]

    core = [[False] * (n - 1) for _ in range(n - 1)]
    for ii, old_i in enumerate(keep):
        for jj, old_j in enumerate(keep):
            core[ii][jj] = adj[old_i][old_j]

    chi = [adj[v][old_i] for old_i in keep]
    return core, chi


def phi_from_core(core: Adj, chi: List[bool], a: int, b: int) -> Dict[str, int]:
    red_need = a - 1
    blue_need = b - 1

    red_phi = 0
    blue_phi = 0

    for comb in itertools.combinations(range(len(core)), red_need):
        if all(chi[i] for i in comb) and is_red_clique(core, comb):
            red_phi += 1

    for comb in itertools.combinations(range(len(core)), blue_need):
        if all(not chi[i] for i in comb) and is_blue_clique(core, comb):
            blue_phi += 1

    return {
        "red_phi": red_phi,
        "blue_phi": blue_phi,
        "phi": red_phi + blue_phi,
    }


def audit_graph(adj: Adj, a: int, b: int) -> Dict[str, Any]:
    n = len(adj)
    s_h = score(adj, a, b)

    vertex_results = []
    all_difference_ok = True
    all_color_difference_ok = True

    sum_phi = 0
    sum_red_phi = 0
    sum_blue_phi = 0

    for v in range(n):
        core, chi = delete_vertex(adj, v)
        s_core = score(core, a, b)
        p = phi_from_core(core, chi, a, b)

        diff_total = s_h["score"] - s_core["score"]
        diff_red = s_h["red_score"] - s_core["red_score"]
        diff_blue = s_h["blue_score"] - s_core["blue_score"]

        difference_ok = p["phi"] == diff_total
        color_difference_ok = (
            p["red_phi"] == diff_red and
            p["blue_phi"] == diff_blue
        )

        if not difference_ok:
            all_difference_ok = False
        if not color_difference_ok:
            all_color_difference_ok = False

        sum_phi += p["phi"]
        sum_red_phi += p["red_phi"]
        sum_blue_phi += p["blue_phi"]

        vertex_results.append({
            "v": v,
            "score_H": s_h,
            "score_H_minus_v": s_core,
            "phi_v": p,
            "diff_total": diff_total,
            "diff_red": diff_red,
            "diff_blue": diff_blue,
            "difference_ok": difference_ok,
            "color_difference_ok": color_difference_ok,
        })

    handshake_red_expected = a * s_h["red_score"]
    handshake_blue_expected = b * s_h["blue_score"]
    handshake_total_expected = handshake_red_expected + handshake_blue_expected

    return {
        "n": n,
        "score_H": s_h,
        "all_difference_ok": all_difference_ok,
        "all_color_difference_ok": all_color_difference_ok,
        "sum_phi_over_vertices": sum_phi,
        "sum_red_phi_over_vertices": sum_red_phi,
        "sum_blue_phi_over_vertices": sum_blue_phi,
        "handshake_red_expected": handshake_red_expected,
        "handshake_blue_expected": handshake_blue_expected,
        "handshake_total_expected": handshake_total_expected,
        "handshake_identity_ok": (
            sum_red_phi == handshake_red_expected and
            sum_blue_phi == handshake_blue_expected and
            sum_phi == handshake_total_expected
        ),
        "vertex_results": vertex_results,
    }


def write_manifest(outdir: Path):
    rows = []
    for p in sorted(outdir.glob("*")):
        if p.is_file() and p.name != "MANIFEST_SHA256.txt":
            rows.append(f"{sha256_file(p)}  {p.name}")
    (outdir / "MANIFEST_SHA256.txt").write_text("\n".join(rows) + "\n", encoding="utf-8")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--a", type=int, required=True)
    ap.add_argument("--b", type=int, required=True)
    ap.add_argument("--input", required=True)
    ap.add_argument("--outdir", required=True)
    args = ap.parse_args()

    input_path = Path(args.input)
    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=False)

    graphs = read_graphs(input_path)

    results = []
    for lineno, token, adj in graphs:
        r = audit_graph(adj, args.a, args.b)
        r["line_number"] = lineno
        r["graph_token_sha256"] = sha256_text(token)
        results.append(r)

    total = len(results)
    diff_ok = sum(1 for r in results if r["all_difference_ok"])
    color_diff_ok = sum(1 for r in results if r["all_color_difference_ok"])
    handshake_ok = sum(1 for r in results if r["handshake_identity_ok"])

    status = "PASS_SHADOW_DIFFERENCE_V03" if (
        diff_ok == total and color_diff_ok == total and handshake_ok == total
    ) else "REVIEW_SHADOW_DIFFERENCE_V03"

    report = {
        "run_type": "MACHURA_SHADOW_DIFFERENCE_VALIDATOR_V03",
        "status": status,
        "a": args.a,
        "b": args.b,
        "input": str(input_path),
        "input_sha256": sha256_file(input_path),
        "total_records": total,
        "difference_ok_records": diff_ok,
        "color_difference_ok_records": color_diff_ok,
        "handshake_identity_ok_records": handshake_ok,
        "theory_checked": [
            "Phi_{H-v}(chi_v) = score(H) - score(H-v)",
            "red_phi_v = red_score(H) - red_score(H-v)",
            "blue_phi_v = blue_score(H) - blue_score(H-v)",
            "sum_v |Phi_v(H)| = a * RedK_a(H) + b * BlueK_b(H^c)"
        ],
        "results": results,
    }

    report_path = outdir / "REPORT_SHADOW_DIFFERENCE_V03.json"
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

    summary = [
        "MACHURA SHADOW DIFFERENCE VALIDATOR V03",
        "=======================================",
        "",
        f"STATUS: {status}",
        f"INPUT: {input_path}",
        f"INPUT_SHA256: {sha256_file(input_path)}",
        f"TOTAL_RECORDS: {total}",
        f"DIFFERENCE_OK_RECORDS: {diff_ok}",
        f"COLOR_DIFFERENCE_OK_RECORDS: {color_diff_ok}",
        f"HANDSHAKE_IDENTITY_OK_RECORDS: {handshake_ok}",
        "",
        "CHECKED:",
        "Phi_{H-v}(chi_v) = score(H) - score(H-v)",
        "red_phi_v = red_score(H) - red_score(H-v)",
        "blue_phi_v = blue_score(H) - blue_score(H-v)",
        "sum_v |Phi_v(H)| = a * RedK_a(H) + b * BlueK_b(H^c)",
    ]

    summary_path = outdir / "SUMMARY_SHADOW_DIFFERENCE_V03.txt"
    summary_path.write_text("\n".join(summary) + "\n", encoding="utf-8")

    write_manifest(outdir)

    print("DONE")
    print(f"STATUS: {status}")
    print(f"REPORT: {report_path}")
    print(f"SUMMARY: {summary_path}")
    print(json.dumps({
        "status": status,
        "total_records": total,
        "difference_ok_records": diff_ok,
        "color_difference_ok_records": color_diff_ok,
        "handshake_identity_ok_records": handshake_ok,
    }, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
