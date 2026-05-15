#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Machura Shadow Reversal Validator V01

Cel:
1. Sprawdzic wzor przyrostu:
   score(G + chi) = score(G) + phi_G(chi)

2. Sprawdzic odwrócenie:
   jesli H jest czysty, to dla kazdego usunietego wierzcholka v:
   G = H - v jest czysty oraz phi_G(chi_v) = 0.

To nie jest obcy solver.
To jest walidator definicji cienia i odwrócenia logicznego.
"""

from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import math
import os
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

    if not s:
        raise ValueError("Empty graph6 line")

    vals = [ord(c) - 63 for c in s]
    if any(v < 0 or v > 63 for v in vals):
        raise ValueError("Invalid graph6 character")

    first = vals[0]
    pos = 1

    if first <= 62:
        n = first
    elif first == 63:
        if len(vals) < 4:
            raise ValueError("Invalid graph6 n encoding")
        n = (vals[1] << 12) | (vals[2] << 6) | vals[3]
        pos = 4
    else:
        raise ValueError("Unsupported graph6 n encoding")

    need = n * (n - 1) // 2
    data_bits = []
    for v in vals[pos:]:
        for k in range(5, -1, -1):
            data_bits.append((v >> k) & 1)

    if len(data_bits) < need:
        raise ValueError("graph6 data too short")

    adj = [[False] * n for _ in range(n)]
    p = 0
    for j in range(1, n):
        for i in range(j):
            val = bool(data_bits[p])
            adj[i][j] = val
            adj[j][i] = val
            p += 1

    return adj


def read_graph_lines(path: Path) -> List[Tuple[int, str, Adj]]:
    out = []
    with path.open("r", encoding="utf-8", errors="replace") as f:
        for lineno, raw in enumerate(f, start=1):
            line = raw.strip()
            if not line:
                continue
            if line.startswith("#"):
                continue

            token = line.split()[0].strip()

            try:
                if set(token) <= {"0", "1"}:
                    adj = decode_edge_bits(token)
                else:
                    adj = decode_graph6(token)
                out.append((lineno, token, adj))
            except Exception as e:
                raise ValueError(f"Failed to parse line {lineno}: {e}") from e

    return out


def is_red_clique(adj: Adj, vertices: Tuple[int, ...]) -> bool:
    for i, j in itertools.combinations(vertices, 2):
        if not adj[i][j]:
            return False
    return True


def is_blue_clique(adj: Adj, vertices: Tuple[int, ...]) -> bool:
    for i, j in itertools.combinations(vertices, 2):
        if adj[i][j]:
            return False
    return True


def count_red_cliques(adj: Adj, k: int) -> int:
    n = len(adj)
    cnt = 0
    for comb in itertools.combinations(range(n), k):
        if is_red_clique(adj, comb):
            cnt += 1
    return cnt


def count_blue_cliques(adj: Adj, k: int) -> int:
    n = len(adj)
    cnt = 0
    for comb in itertools.combinations(range(n), k):
        if is_blue_clique(adj, comb):
            cnt += 1
    return cnt


def score(adj: Adj, a: int, b: int) -> Dict[str, int]:
    red = count_red_cliques(adj, a)
    blue = count_blue_cliques(adj, b)
    return {
        "red_conflicts": red,
        "blue_conflicts": blue,
        "score": red + blue,
    }


def phi(adj: Adj, chi: List[bool], a: int, b: int) -> Dict[str, int]:
    """
    chi[i] = True oznacza czerwone polaczenie nowego wierzcholka z i.
    chi[i] = False oznacza niebieskie polaczenie.
    """
    n = len(adj)
    if len(chi) != n:
        raise ValueError("chi length does not match graph size")

    red_phi = 0
    blue_phi = 0

    red_need = a - 1
    blue_need = b - 1

    for comb in itertools.combinations(range(n), red_need):
        if all(chi[i] for i in comb) and is_red_clique(adj, comb):
            red_phi += 1

    for comb in itertools.combinations(range(n), blue_need):
        if all(not chi[i] for i in comb) and is_blue_clique(adj, comb):
            blue_phi += 1

    return {
        "red_phi": red_phi,
        "blue_phi": blue_phi,
        "phi": red_phi + blue_phi,
    }


def extend_graph(adj: Adj, chi: List[bool]) -> Adj:
    n = len(adj)
    if len(chi) != n:
        raise ValueError("chi length does not match graph size")

    out = [[False] * (n + 1) for _ in range(n + 1)]
    for i in range(n):
        for j in range(n):
            out[i][j] = adj[i][j]

    new = n
    for i, val in enumerate(chi):
        out[i][new] = val
        out[new][i] = val

    return out


def delete_vertex_with_chi(adj: Adj, v: int) -> Tuple[Adj, List[bool]]:
    n = len(adj)
    keep = [i for i in range(n) if i != v]

    core = [[False] * (n - 1) for _ in range(n - 1)]
    for ii, old_i in enumerate(keep):
        for jj, old_j in enumerate(keep):
            core[ii][jj] = adj[old_i][old_j]

    chi = [adj[v][old_i] for old_i in keep]
    return core, chi


def validate_increment(adj: Adj, chi: List[bool], a: int, b: int) -> Dict[str, Any]:
    s0 = score(adj, a, b)
    p = phi(adj, chi, a, b)
    ext = extend_graph(adj, chi)
    s1 = score(ext, a, b)

    lhs = s1["score"]
    rhs = s0["score"] + p["phi"]

    return {
        "n_core": len(adj),
        "a": a,
        "b": b,
        "score_core": s0,
        "phi": p,
        "score_extended": s1,
        "identity_lhs": lhs,
        "identity_rhs": rhs,
        "identity_ok": lhs == rhs,
        "extended_clean": s1["score"] == 0,
    }


def validate_reverse_clean_h(adj_h: Adj, a: int, b: int) -> Dict[str, Any]:
    s_h = score(adj_h, a, b)
    n_h = len(adj_h)

    vertex_results = []
    all_ok = True
    all_phi_zero = True
    all_core_clean = True

    for v in range(n_h):
        core, chi = delete_vertex_with_chi(adj_h, v)
        s_core = score(core, a, b)
        p = phi(core, chi, a, b)
        inc = validate_increment(core, chi, a, b)

        item = {
            "deleted_vertex": v,
            "core_score": s_core,
            "phi": p,
            "increment_identity_ok": inc["identity_ok"],
            "core_clean": s_core["score"] == 0,
            "phi_zero": p["phi"] == 0,
        }
        vertex_results.append(item)

        if not inc["identity_ok"]:
            all_ok = False
        if s_core["score"] != 0:
            all_core_clean = False
        if p["phi"] != 0:
            all_phi_zero = False

    return {
        "n_h": n_h,
        "a": a,
        "b": b,
        "score_h": s_h,
        "h_clean": s_h["score"] == 0,
        "all_increment_identities_ok": all_ok,
        "all_deleted_cores_clean": all_core_clean,
        "all_deleted_phis_zero": all_phi_zero,
        "reverse_lemma_ok_for_clean_h": (
            s_h["score"] == 0
            and all_ok
            and all_core_clean
            and all_phi_zero
        ),
        "vertex_results": vertex_results,
    }


def parse_chi_bits(bits: str) -> List[bool]:
    clean = "".join(c for c in bits.strip() if c in "01")
    if not clean:
        raise ValueError("empty chi")
    return [c == "1" for c in clean]


def write_manifest(outdir: Path) -> Path:
    rows = []
    for path in sorted(outdir.glob("*")):
        if path.is_file() and path.name != "MANIFEST_SHA256.txt":
            rows.append(f"{sha256_file(path)}  {path.name}")
    manifest = outdir / "MANIFEST_SHA256.txt"
    manifest.write_text("\n".join(rows) + "\n", encoding="utf-8")
    return manifest


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--a", type=int, required=True)
    ap.add_argument("--b", type=int, required=True)
    ap.add_argument("--mode", required=True, choices=[
        "reverse_clean_h",
        "core_plus_chi",
    ])
    ap.add_argument("--input", required=True)
    ap.add_argument("--chi", default=None)
    ap.add_argument("--outdir", required=True)
    args = ap.parse_args()

    in_path = Path(args.input)
    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    graphs = read_graph_lines(in_path)

    report: Dict[str, Any] = {
        "run_type": "MACHURA_SHADOW_REVERSAL_VALIDATOR_V01",
        "mode": args.mode,
        "a": args.a,
        "b": args.b,
        "input": str(in_path),
        "input_sha256": sha256_file(in_path),
        "graph_records": len(graphs),
        "results": [],
    }

    if args.mode == "reverse_clean_h":
        for lineno, token, adj in graphs:
            res = validate_reverse_clean_h(adj, args.a, args.b)
            res["line_number"] = lineno
            res["graph_token_sha256"] = sha256_text(token)
            report["results"].append(res)

        total = len(report["results"])
        clean = sum(1 for r in report["results"] if r["h_clean"])
        reverse_ok = sum(1 for r in report["results"] if r["reverse_lemma_ok_for_clean_h"])

        report["summary"] = {
            "total_records": total,
            "clean_h_records": clean,
            "reverse_lemma_ok_for_clean_h_records": reverse_ok,
            "status": "DONE",
        }

    elif args.mode == "core_plus_chi":
        if args.chi is None:
            raise ValueError("--chi is required for core_plus_chi mode")

        chi = parse_chi_bits(args.chi)

        for lineno, token, adj in graphs:
            res = validate_increment(adj, chi, args.a, args.b)
            res["line_number"] = lineno
            res["graph_token_sha256"] = sha256_text(token)
            report["results"].append(res)

        total = len(report["results"])
        identity_ok = sum(1 for r in report["results"] if r["identity_ok"])
        empty_shadow = sum(1 for r in report["results"] if r["phi"]["phi"] == 0)
        clean_extension = sum(1 for r in report["results"] if r["extended_clean"])

        report["summary"] = {
            "total_records": total,
            "increment_identity_ok_records": identity_ok,
            "empty_shadow_records": empty_shadow,
            "clean_extension_records": clean_extension,
            "status": "DONE",
        }

    report_path = outdir / "REPORT_SHADOW_REVERSAL_V01.json"
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

    manifest_path = write_manifest(outdir)

    print("DONE")
    print(f"MODE: {args.mode}")
    print(f"REPORT: {report_path}")
    print(f"MANIFEST: {manifest_path}")
    print(json.dumps(report.get("summary", {}), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
