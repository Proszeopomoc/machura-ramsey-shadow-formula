#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import argparse
import csv
import hashlib
import itertools
import json
import time
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
    return r + bl


def mask_of(vertices) -> int:
    m = 0
    for v in vertices:
        m |= 1 << v
    return m


def predecessor_terms(adj, a: int, b: int):
    n = len(adj)
    red_need = a - 1
    blue_need = b - 1

    red_terms = []
    blue_terms = []

    for c in itertools.combinations(range(n), red_need):
        if is_red_clique(adj, c):
            red_terms.append(mask_of(c))

    for c in itertools.combinations(range(n), blue_need):
        if is_blue_clique(adj, c):
            blue_terms.append(mask_of(c))

    return red_terms, blue_terms


def phi_full(red_terms, blue_terms, n: int, one_mask: int):
    all_mask = (1 << n) - 1
    zero_mask = all_mask ^ one_mask

    red_phi = 0
    blue_phi = 0

    for t in red_terms:
        if t & ~one_mask == 0:
            red_phi += 1

    for t in blue_terms:
        if t & ~zero_mask == 0:
            blue_phi += 1

    return red_phi, blue_phi, red_phi + blue_phi


def completed_phi_partial(red_terms, blue_terms, assigned_mask: int, one_mask: int):
    zero_mask = assigned_mask ^ one_mask

    red_phi = 0
    blue_phi = 0

    for t in red_terms:
        if t & ~assigned_mask == 0 and t & ~one_mask == 0:
            red_phi += 1

    for t in blue_terms:
        if t & ~assigned_mask == 0 and t & ~zero_mask == 0:
            blue_phi += 1

    return red_phi + blue_phi


def propagate_zero_fuses(red_terms, blue_terms, n: int, assigned_mask: int, one_mask: int):
    """
    Product-fuse propagation for target 0.

    Red term is safe if it contains at least one 0.
    If red term has all assigned 1 except one unassigned bit, force that bit to 0.

    Blue term is safe if it contains at least one 1.
    If blue term has all assigned 0 except one unassigned bit, force that bit to 1.
    """
    changed = True

    while changed:
        changed = False
        zero_mask = assigned_mask ^ one_mask

        for t in red_terms:
            if t & zero_mask:
                continue

            unassigned = t & ~assigned_mask

            if unassigned == 0:
                return None

            if unassigned.bit_count() == 1:
                bit = unassigned
                assigned_mask |= bit
                one_mask &= ~bit
                changed = True

        zero_mask = assigned_mask ^ one_mask

        for t in blue_terms:
            if t & one_mask:
                continue

            unassigned = t & ~assigned_mask

            if unassigned == 0:
                return None

            if unassigned.bit_count() == 1:
                bit = unassigned
                assigned_mask |= bit
                one_mask |= bit
                changed = True

    return assigned_mask, one_mask


def variable_score(red_terms, blue_terms, n: int, assigned_mask: int, one_mask: int, v: int):
    bit = 1 << v
    if assigned_mask & bit:
        return -1

    zero_mask = assigned_mask ^ one_mask

    score0 = 0
    score1 = 0

    for t in red_terms:
        if not (t & bit):
            continue
        if t & zero_mask:
            continue
        score0 += 10
        if (t & ~assigned_mask).bit_count() == 1:
            score0 += 100

    for t in blue_terms:
        if not (t & bit):
            continue
        if t & one_mask:
            continue
        score1 += 10
        if (t & ~assigned_mask).bit_count() == 1:
            score1 += 100

    return max(score0, score1)


def choose_variable(red_terms, blue_terms, n: int, assigned_mask: int, one_mask: int):
    best_v = -1
    best_s = -1

    for v in range(n):
        s = variable_score(red_terms, blue_terms, n, assigned_mask, one_mask, v)
        if s > best_s:
            best_s = s
            best_v = v

    if best_v >= 0:
        return best_v

    for v in range(n):
        if not ((assigned_mask >> v) & 1):
            return v

    return -1


def branch_order(red_terms, blue_terms, n: int, assigned_mask: int, one_mask: int, v: int):
    bit = 1 << v

    a0 = assigned_mask | bit
    o0 = one_mask & ~bit
    p0 = completed_phi_partial(red_terms, blue_terms, a0, o0)

    a1 = assigned_mask | bit
    o1 = one_mask | bit
    p1 = completed_phi_partial(red_terms, blue_terms, a1, o1)

    if p0 < p1:
        return [(a0, o0), (a1, o1)]
    if p1 < p0:
        return [(a1, o1), (a0, o0)]

    # tie-break: block more currently endangered products
    s = variable_score(red_terms, blue_terms, n, assigned_mask, one_mask, v)
    return [(a0, o0), (a1, o1)] if s >= 0 else [(a1, o1), (a0, o0)]


def solve_target(red_terms, blue_terms, n: int, target: int, node_limit: int, seconds: float):
    start = time.time()
    all_mask = (1 << n) - 1

    nodes = 0
    best_phi = 10**9
    best_mask = None
    cut_by_phi = 0
    cut_by_fuse = 0
    timed_out = False
    node_limited = False

    seen = set()

    def dfs(assigned_mask: int, one_mask: int):
        nonlocal nodes, best_phi, best_mask, cut_by_phi, cut_by_fuse, timed_out, node_limited

        nodes += 1

        if node_limit and nodes >= node_limit:
            node_limited = True
            return False

        if seconds > 0 and nodes % 1000 == 0 and time.time() - start > seconds:
            timed_out = True
            return False

        key = (assigned_mask, one_mask)
        if key in seen:
            return False
        seen.add(key)

        current_completed = completed_phi_partial(red_terms, blue_terms, assigned_mask, one_mask)

        if current_completed > target:
            cut_by_phi += 1
            return False

        if target == 0:
            forced = propagate_zero_fuses(red_terms, blue_terms, n, assigned_mask, one_mask)
            if forced is None:
                cut_by_fuse += 1
                return False
            assigned_mask, one_mask = forced

        if assigned_mask == all_mask:
            rp, bp, ph = phi_full(red_terms, blue_terms, n, one_mask)
            if ph < best_phi:
                best_phi = ph
                best_mask = one_mask
            return ph <= target

        v = choose_variable(red_terms, blue_terms, n, assigned_mask, one_mask)
        if v < 0:
            return False

        for a2, o2 in branch_order(red_terms, blue_terms, n, assigned_mask, one_mask, v):
            if timed_out or node_limited:
                return False
            if dfs(a2, o2):
                return True

        return False

    found = dfs(0, 0)

    elapsed = time.time() - start

    return {
        "found_target": found,
        "best_phi": best_phi if best_phi < 10**9 else None,
        "best_chi": None if best_mask is None else "".join("1" if ((best_mask >> i) & 1) else "0" for i in range(n)),
        "nodes": nodes,
        "seen_states": len(seen),
        "cut_by_phi": cut_by_phi,
        "cut_by_fuse": cut_by_fuse,
        "elapsed_sec": elapsed,
        "timed_out": timed_out,
        "node_limited": node_limited,
    }


def analyze_case(a: int, b: int, n: int, target: int, max_graphs: int, node_limit: int, seconds_per_graph: float):
    edge_count = n * (n - 1) // 2
    total_graphs = 1 << edge_count

    if max_graphs and total_graphs > max_graphs:
        raise RuntimeError(f"Refusing enumeration: {total_graphs} graphs exceeds max_graphs {max_graphs}")

    rows = []
    clean_count = 0
    found_count = 0
    proved_no_target = 0
    global_best_phi = None

    for gmask in range(total_graphs):
        adj = graph_from_bits(n, gmask)

        if score(adj, a, b) != 0:
            continue

        clean_count += 1

        red_terms, blue_terms = predecessor_terms(adj, a, b)

        result = solve_target(
            red_terms=red_terms,
            blue_terms=blue_terms,
            n=n,
            target=target,
            node_limit=node_limit,
            seconds=seconds_per_graph,
        )

        if result["found_target"]:
            found_count += 1

        if not result["found_target"] and not result["timed_out"] and not result["node_limited"]:
            proved_no_target += 1

        if result["best_phi"] is not None:
            if global_best_phi is None or result["best_phi"] < global_best_phi:
                global_best_phi = result["best_phi"]

        rows.append({
            "a": a,
            "b": b,
            "n": n,
            "graph_index": clean_count,
            "graph_mask": gmask,
            "graph_bits_sha256": hashlib.sha256(bits_string(n, gmask).encode("ascii")).hexdigest(),
            "red_terms": len(red_terms),
            "blue_terms": len(blue_terms),
            "target": target,
            "found_target": result["found_target"],
            "best_phi": result["best_phi"],
            "best_chi": result["best_chi"],
            "nodes": result["nodes"],
            "seen_states": result["seen_states"],
            "cut_by_phi": result["cut_by_phi"],
            "cut_by_fuse": result["cut_by_fuse"],
            "elapsed_sec": result["elapsed_sec"],
            "timed_out": result["timed_out"],
            "node_limited": result["node_limited"],
        })

    return {
        "summary": {
            "case": f"R({a},{b}) n={n} target={target}",
            "a": a,
            "b": b,
            "n": n,
            "target": target,
            "edge_count": edge_count,
            "total_graphs": total_graphs,
            "clean_graphs": clean_count,
            "found_target_graphs": found_count,
            "proved_no_target_graphs": proved_no_target,
            "global_best_phi_seen": global_best_phi,
        },
        "rows": rows,
    }


def write_csv(path: Path, rows):
    if not rows:
        path.write_text("", encoding="utf-8")
        return

    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)


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
    ap.add_argument("--case", action="append", required=True, help="format a,b,n")
    ap.add_argument("--target", type=int, default=0)
    ap.add_argument("--max-graphs", type=int, default=2000000)
    ap.add_argument("--node-limit", type=int, default=0)
    ap.add_argument("--seconds-per-graph", type=float, default=0.0)
    args = ap.parse_args()

    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=False)

    summaries = []

    for c in args.case:
        a, b, n = [int(x.strip()) for x in c.split(",")]
        result = analyze_case(
            a=a,
            b=b,
            n=n,
            target=args.target,
            max_graphs=args.max_graphs,
            node_limit=args.node_limit,
            seconds_per_graph=args.seconds_per_graph,
        )

        summaries.append(result["summary"])

        csv_path = outdir / f"PRODUCT_FUSE_R{a}_{b}_N{n}_TARGET{args.target}.csv"
        write_csv(csv_path, result["rows"])

    report = {
        "run_type": "MACHURA_DELTA_SHADOW_PRODUCT_FUSE_V14A",
        "target": args.target,
        "summaries": summaries,
    }

    report_path = outdir / "REPORT_DELTA_SHADOW_PRODUCT_FUSE_V14A.json"
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

    summary_path = outdir / "SUMMARY_DELTA_SHADOW_PRODUCT_FUSE_V14A.txt"
    lines = [
        "MACHURA DELTA SHADOW PRODUCT-FUSE ENGINE V14A",
        "==============================================",
        "",
        "Purpose:",
        "Algorithmic product-fuse search for Delta target, not plain Phi evaluation.",
        "",
    ]

    for s in summaries:
        lines.append(f"CASE: {s['case']}")
        lines.append(f"CLEAN_GRAPHS: {s['clean_graphs']}")
        lines.append(f"FOUND_TARGET_GRAPHS: {s['found_target_graphs']}")
        lines.append(f"PROVED_NO_TARGET_GRAPHS: {s['proved_no_target_graphs']}")
        lines.append(f"GLOBAL_BEST_PHI_SEEN: {s['global_best_phi_seen']}")
        lines.append("")

    summary_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    manifest = write_manifest(outdir)

    print("DONE")
    print(f"REPORT: {report_path}")
    print(f"SUMMARY: {summary_path}")
    print(f"MANIFEST: {manifest}")
    print(json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
