#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Machura Shadow Engine V06

Author: Michal Machura

Purpose:
Native shadow-formula engine.

This is not SAT, CP, ILP, or an external solver.
The engine works directly on the Machura shadow formula:

Phi_G(chi)
=
red predecessor hits
+
blue predecessor hits

For R(a,b):
red predecessors are red K_{a-1} in G.
blue predecessors are blue K_{b-1} in G^c.

Main question:
Does there exist chi such that Phi_G(chi) <= target?

Target 0:
searches for an empty shadow.

Target 1:
searches for a one-conflict shadow.

If no such chi exists and the search exhausts the space, the engine proves:
min Phi_G > target.
"""

from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import math
import random
import time
from pathlib import Path
from typing import List, Tuple, Dict, Any, Optional

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
    if not vals:
        raise ValueError("empty graph6")

    first = vals[0]
    pos = 1

    if first <= 62:
        n = first
    elif first == 63:
        if len(vals) < 4:
            raise ValueError("invalid graph6 n encoding")
        n = (vals[1] << 12) | (vals[2] << 6) | vals[3]
        pos = 4
    else:
        raise ValueError("unsupported graph6 n encoding")

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


def read_graphs(path: Path, limit: int = 0) -> List[Tuple[int, str, Adj]]:
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

            if limit and len(out) >= limit:
                break

    return out


def mask_from_vertices(vertices: Tuple[int, ...]) -> int:
    m = 0
    for v in vertices:
        m |= 1 << v
    return m


def is_red_clique(adj: Adj, vertices: Tuple[int, ...]) -> bool:
    return all(adj[i][j] for i, j in itertools.combinations(vertices, 2))


def is_blue_clique(adj: Adj, vertices: Tuple[int, ...]) -> bool:
    return all(not adj[i][j] for i, j in itertools.combinations(vertices, 2))


def build_shadow_hyperedges(adj: Adj, a: int, b: int) -> Dict[str, Any]:
    n = len(adj)
    red_need = a - 1
    blue_need = b - 1

    red_edges = []
    blue_edges = []

    for comb in itertools.combinations(range(n), red_need):
        if is_red_clique(adj, comb):
            red_edges.append(mask_from_vertices(comb))

    for comb in itertools.combinations(range(n), blue_need):
        if is_blue_clique(adj, comb):
            blue_edges.append(mask_from_vertices(comb))

    incidence = [0] * n
    red_incidence = [0] * n
    blue_incidence = [0] * n

    for e in red_edges:
        for i in range(n):
            if (e >> i) & 1:
                incidence[i] += 1
                red_incidence[i] += 1

    for e in blue_edges:
        for i in range(n):
            if (e >> i) & 1:
                incidence[i] += 1
                blue_incidence[i] += 1

    order = sorted(range(n), key=lambda i: (-incidence[i], -red_incidence[i], -blue_incidence[i], i))

    return {
        "n": n,
        "a": a,
        "b": b,
        "red_edges": red_edges,
        "blue_edges": blue_edges,
        "red_count": len(red_edges),
        "blue_count": len(blue_edges),
        "incidence": incidence,
        "red_incidence": red_incidence,
        "blue_incidence": blue_incidence,
        "order": order,
    }


def phi_from_masks(red_edges: List[int], blue_edges: List[int], one_mask: int, n: int) -> Dict[str, int]:
    all_mask = (1 << n) - 1
    zero_mask = all_mask ^ one_mask

    red_phi = 0
    blue_phi = 0

    for e in red_edges:
        if e & ~one_mask == 0:
            red_phi += 1

    for e in blue_edges:
        if e & ~zero_mask == 0:
            blue_phi += 1

    return {
        "red_phi": red_phi,
        "blue_phi": blue_phi,
        "phi": red_phi + blue_phi,
    }


def completed_phi_partial(red_edges: List[int], blue_edges: List[int], assigned_mask: int, one_mask: int, n: int) -> Dict[str, int]:
    zero_mask = assigned_mask ^ one_mask

    red_phi = 0
    blue_phi = 0

    for e in red_edges:
        if e & ~assigned_mask == 0 and e & ~one_mask == 0:
            red_phi += 1

    for e in blue_edges:
        if e & ~assigned_mask == 0 and e & ~zero_mask == 0:
            blue_phi += 1

    return {
        "red_phi": red_phi,
        "blue_phi": blue_phi,
        "phi": red_phi + blue_phi,
    }


def force_zero_shadow(
    red_edges: List[int],
    blue_edges: List[int],
    assigned_mask: int,
    one_mask: int,
    n: int
) -> Optional[Tuple[int, int]]:
    """
    Propagation for the zero-shadow remaining condition.

    Red predecessor must not become all 1.
    Blue predecessor must not become all 0.

    If an edge has all but one variable already forced toward conflict,
    the last variable is forced away from conflict.
    """
    changed = True

    while changed:
        changed = False
        zero_mask = assigned_mask ^ one_mask

        for e in red_edges:
            if e & zero_mask:
                continue

            un = e & ~assigned_mask

            if un == 0:
                return None

            if un.bit_count() == 1:
                bit = un
                assigned_mask |= bit
                one_mask &= ~bit
                changed = True

        zero_mask = assigned_mask ^ one_mask

        for e in blue_edges:
            if e & one_mask:
                continue

            un = e & ~assigned_mask

            if un == 0:
                return None

            if un.bit_count() == 1:
                bit = un
                assigned_mask |= bit
                one_mask |= bit
                changed = True

    return assigned_mask, one_mask


def choose_next_var(order: List[int], assigned_mask: int) -> int:
    for v in order:
        if ((assigned_mask >> v) & 1) == 0:
            return v
    return -1


def greedy_upper_bound(hyp: Dict[str, Any], restarts: int, seed: int) -> Dict[str, Any]:
    random.seed(seed)

    n = hyp["n"]
    red_edges = hyp["red_edges"]
    blue_edges = hyp["blue_edges"]
    base_order = hyp["order"]

    best = None

    for r in range(restarts):
        if r == 0:
            order = list(base_order)
        else:
            order = list(base_order)
            random.shuffle(order)

        one_mask = 0
        assigned_mask = 0

        for v in order:
            bit = 1 << v

            one0 = one_mask
            assign0 = assigned_mask | bit
            p0 = completed_phi_partial(red_edges, blue_edges, assign0, one0, n)["phi"]

            one1 = one_mask | bit
            assign1 = assigned_mask | bit
            p1 = completed_phi_partial(red_edges, blue_edges, assign1, one1, n)["phi"]

            if p1 < p0:
                one_mask = one1
            elif p0 < p1:
                one_mask = one0
            else:
                if random.randint(0, 1) == 1:
                    one_mask = one1
                else:
                    one_mask = one0

            assigned_mask |= bit

        p = phi_from_masks(red_edges, blue_edges, one_mask, n)

        item = {
            "restart": r,
            "one_mask": one_mask,
            "degree": one_mask.bit_count(),
            "phi": p,
        }

        if best is None or item["phi"]["phi"] < best["phi"]["phi"]:
            best = item

    return best or {
        "restart": -1,
        "one_mask": 0,
        "degree": 0,
        "phi": {"red_phi": 0, "blue_phi": 0, "phi": 0},
    }


def target_search(hyp: Dict[str, Any], target: int, seconds: float, node_limit: int) -> Dict[str, Any]:
    start = time.time()

    n = hyp["n"]
    red_edges = hyp["red_edges"]
    blue_edges = hyp["blue_edges"]
    order = hyp["order"]
    all_mask = (1 << n) - 1

    nodes = 0
    best_partial_phi = 10**18
    best_assigned = 0
    found_mask = None
    timed_out = False
    node_limited = False

    def dfs(assigned_mask: int, one_mask: int) -> bool:
        nonlocal nodes, best_partial_phi, best_assigned, found_mask, timed_out, node_limited

        nodes += 1

        if nodes % 20000 == 0:
            if seconds > 0 and time.time() - start > seconds:
                timed_out = True
                return False
            if node_limit > 0 and nodes >= node_limit:
                node_limited = True
                return False

        p = completed_phi_partial(red_edges, blue_edges, assigned_mask, one_mask, n)
        cur_phi = p["phi"]

        if cur_phi < best_partial_phi or assigned_mask.bit_count() > best_assigned:
            best_partial_phi = min(best_partial_phi, cur_phi)
            best_assigned = max(best_assigned, assigned_mask.bit_count())

        if cur_phi > target:
            return False

        if cur_phi == target:
            forced = force_zero_shadow(red_edges, blue_edges, assigned_mask, one_mask, n)
            if forced is None:
                return False
            assigned_mask, one_mask = forced

        if assigned_mask == all_mask:
            final_phi = phi_from_masks(red_edges, blue_edges, one_mask, n)
            if final_phi["phi"] <= target:
                found_mask = one_mask
                return True
            return False

        v = choose_next_var(order, assigned_mask)
        if v < 0:
            return False

        bit = 1 << v

        # Branch order: try value suggested by local immediate damage.
        p0 = completed_phi_partial(red_edges, blue_edges, assigned_mask | bit, one_mask, n)["phi"]
        p1 = completed_phi_partial(red_edges, blue_edges, assigned_mask | bit, one_mask | bit, n)["phi"]

        branches = []
        if p0 <= p1:
            branches = [(assigned_mask | bit, one_mask), (assigned_mask | bit, one_mask | bit)]
        else:
            branches = [(assigned_mask | bit, one_mask | bit), (assigned_mask | bit, one_mask)]

        for a2, o2 in branches:
            if timed_out or node_limited:
                return False
            if dfs(a2, o2):
                return True

        return False

    if target == 0:
        forced0 = force_zero_shadow(red_edges, blue_edges, 0, 0, n)
        if forced0 is None:
            status = "PROVED_NO_TARGET"
            elapsed = time.time() - start
            return {
                "status": status,
                "target": target,
                "nodes": nodes,
                "elapsed_sec": elapsed,
                "found": False,
                "found_mask": None,
                "found_degree": None,
                "found_phi": None,
                "best_partial_phi": None,
                "best_assigned": None,
                "timed_out": False,
                "node_limited": False,
            }
        init_assigned, init_one = forced0
    else:
        init_assigned, init_one = 0, 0

    ok = dfs(init_assigned, init_one)
    elapsed = time.time() - start

    if ok and found_mask is not None:
        found_phi = phi_from_masks(red_edges, blue_edges, found_mask, n)
        status = "FOUND_TARGET"
        found = True
        found_degree = found_mask.bit_count()
    elif timed_out:
        status = "TIME_LIMIT"
        found = False
        found_phi = None
        found_degree = None
    elif node_limited:
        status = "NODE_LIMIT"
        found = False
        found_phi = None
        found_degree = None
    else:
        status = "PROVED_NO_TARGET"
        found = False
        found_phi = None
        found_degree = None

    return {
        "status": status,
        "target": target,
        "nodes": nodes,
        "elapsed_sec": elapsed,
        "found": found,
        "found_mask": found_mask,
        "found_degree": found_degree,
        "found_phi": found_phi,
        "best_partial_phi": best_partial_phi,
        "best_assigned": best_assigned,
        "timed_out": timed_out,
        "node_limited": node_limited,
    }


def bitmask_to_bitstring(mask: Optional[int], n: int) -> Optional[str]:
    if mask is None:
        return None
    return "".join("1" if ((mask >> i) & 1) else "0" for i in range(n))


def write_manifest(outdir: Path) -> Path:
    rows = []
    for p in sorted(outdir.glob("*")):
        if p.is_file() and p.name != "MANIFEST_SHA256.txt":
            rows.append(f"{sha256_file(p)}  {p.name}")
    manifest = outdir / "MANIFEST_SHA256.txt"
    manifest.write_text("\n".join(rows) + "\n", encoding="utf-8")
    return manifest


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--a", type=int, required=True)
    ap.add_argument("--b", type=int, required=True)
    ap.add_argument("--input", required=True)
    ap.add_argument("--outdir", required=True)
    ap.add_argument("--mode", choices=["summary", "greedy", "target"], required=True)
    ap.add_argument("--target", type=int, default=0)
    ap.add_argument("--seconds-per-graph", type=float, default=30.0)
    ap.add_argument("--node-limit", type=int, default=0)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--greedy-restarts", type=int, default=200)
    ap.add_argument("--seed", type=int, default=12345)
    args = ap.parse_args()

    input_path = Path(args.input)
    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=False)

    graphs = read_graphs(input_path, limit=args.limit)

    results = []

    for idx, (lineno, token, adj) in enumerate(graphs, start=1):
        hyp = build_shadow_hyperedges(adj, args.a, args.b)

        base = {
            "record_index": idx,
            "line_number": lineno,
            "graph_token_sha256": sha256_text(token),
            "n": hyp["n"],
            "a": args.a,
            "b": args.b,
            "red_predecessor_count": hyp["red_count"],
            "blue_predecessor_count": hyp["blue_count"],
            "max_incidence": max(hyp["incidence"]) if hyp["incidence"] else 0,
            "top_incidence_vertices": sorted(
                [
                    {
                        "v": i,
                        "incidence": hyp["incidence"][i],
                        "red": hyp["red_incidence"][i],
                        "blue": hyp["blue_incidence"][i],
                    }
                    for i in range(hyp["n"])
                ],
                key=lambda x: (-x["incidence"], x["v"])
            )[:10],
        }

        if args.mode == "summary":
            base["status"] = "SUMMARY_DONE"

        elif args.mode == "greedy":
            g = greedy_upper_bound(hyp, args.greedy_restarts, args.seed + idx)
            base["status"] = "GREEDY_DONE"
            base["greedy"] = {
                "restart": g["restart"],
                "degree": g["degree"],
                "phi": g["phi"],
                "chi_bitstring": bitmask_to_bitstring(g["one_mask"], hyp["n"]),
            }

        elif args.mode == "target":
            s = target_search(
                hyp=hyp,
                target=args.target,
                seconds=args.seconds_per_graph,
                node_limit=args.node_limit,
            )
            base["status"] = s["status"]
            base["target_search"] = {
                "target": args.target,
                "nodes": s["nodes"],
                "elapsed_sec": s["elapsed_sec"],
                "found": s["found"],
                "found_degree": s["found_degree"],
                "found_phi": s["found_phi"],
                "chi_bitstring": bitmask_to_bitstring(s["found_mask"], hyp["n"]),
                "best_partial_phi": s["best_partial_phi"],
                "best_assigned": s["best_assigned"],
                "timed_out": s["timed_out"],
                "node_limited": s["node_limited"],
            }

        results.append(base)

    status_counts = {}
    for r in results:
        status_counts[r["status"]] = status_counts.get(r["status"], 0) + 1

    report = {
        "run_type": "MACHURA_SHADOW_ENGINE_V06",
        "mode": args.mode,
        "a": args.a,
        "b": args.b,
        "input": str(input_path),
        "input_sha256": sha256_file(input_path),
        "total_records": len(results),
        "status_counts": status_counts,
        "parameters": {
            "target": args.target,
            "seconds_per_graph": args.seconds_per_graph,
            "node_limit": args.node_limit,
            "limit": args.limit,
            "greedy_restarts": args.greedy_restarts,
            "seed": args.seed,
        },
        "results": results,
    }

    report_path = outdir / "REPORT_MACHURA_SHADOW_ENGINE_V06.json"
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

    summary_lines = [
        "MACHURA SHADOW ENGINE V06",
        "=========================",
        "",
        f"MODE: {args.mode}",
        f"A: {args.a}",
        f"B: {args.b}",
        f"INPUT: {input_path}",
        f"INPUT_SHA256: {sha256_file(input_path)}",
        f"TOTAL_RECORDS: {len(results)}",
        f"STATUS_COUNTS: {json.dumps(status_counts, sort_keys=True)}",
        "",
        "NOTES:",
        "This engine works directly on the shadow formula.",
        "It searches over connection maps chi, not over full larger graphs.",
    ]

    summary_path = outdir / "SUMMARY_MACHURA_SHADOW_ENGINE_V06.txt"
    summary_path.write_text("\n".join(summary_lines) + "\n", encoding="utf-8")

    manifest = write_manifest(outdir)

    print("DONE")
    print(f"STATUS_COUNTS: {json.dumps(status_counts, sort_keys=True)}")
    print(f"REPORT: {report_path}")
    print(f"SUMMARY: {summary_path}")
    print(f"MANIFEST: {manifest}")


if __name__ == "__main__":
    main()
