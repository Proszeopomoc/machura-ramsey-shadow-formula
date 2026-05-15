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


def score(adj, a: int, b: int) -> int:
    return count_red_cliques(adj, a) + count_blue_cliques(adj, b)


def predecessor_terms(adj, a: int, b: int):
    n = len(adj)
    red_terms = []
    blue_terms = []

    for c in itertools.combinations(range(n), a - 1):
        if is_red_clique(adj, c):
            red_terms.append(c)

    for c in itertools.combinations(range(n), b - 1):
        if is_blue_clique(adj, c):
            blue_terms.append(c)

    return red_terms, blue_terms


def build_clauses(red_terms, blue_terms):
    """
    Empty shadow condition:

    Red product prod x_i must not activate:
      not(all x_i=1) <=> OR_i (x_i=0)
      literals are negative: -(i+1)

    Blue product prod (1-x_i) must not activate:
      not(all x_i=0) <=> OR_i (x_i=1)
      literals are positive: +(i+1)
    """
    clauses = []

    for term in red_terms:
        clauses.append(tuple(-(i + 1) for i in term))

    for term in blue_terms:
        clauses.append(tuple(i + 1 for i in term))

    return clauses


def lit_value(lit: int, assign):
    var = abs(lit) - 1
    val = assign[var]

    if val == -1:
        return None

    if lit > 0:
        return val == 1
    else:
        return val == 0


def unit_propagate(clauses, assign):
    changed = True
    forced = 0

    while changed:
        changed = False

        for clause in clauses:
            satisfied = False
            unassigned = []

            for lit in clause:
                v = lit_value(lit, assign)
                if v is True:
                    satisfied = True
                    break
                if v is None:
                    unassigned.append(lit)

            if satisfied:
                continue

            if not unassigned:
                return False, forced

            if len(unassigned) == 1:
                lit = unassigned[0]
                var = abs(lit) - 1
                need = 1 if lit > 0 else 0

                if assign[var] != -1 and assign[var] != need:
                    return False, forced

                if assign[var] == -1:
                    assign[var] = need
                    forced += 1
                    changed = True

    return True, forced


def choose_var(clauses, assign, n):
    # Choose unassigned variable appearing most often in unresolved clauses.
    score = [0] * n

    for clause in clauses:
        sat = False
        for lit in clause:
            v = lit_value(lit, assign)
            if v is True:
                sat = True
                break

        if sat:
            continue

        for lit in clause:
            var = abs(lit) - 1
            if assign[var] == -1:
                score[var] += 1

    best = -1
    best_s = -1

    for i in range(n):
        if assign[i] == -1 and score[i] > best_s:
            best_s = score[i]
            best = i

    if best >= 0:
        return best

    for i in range(n):
        if assign[i] == -1:
            return i

    return -1


def dpll_empty_shadow(clauses, n, node_limit=0, seconds=0.0):
    start = time.time()
    nodes = 0
    propagations = 0
    conflicts = 0
    node_limited = False
    timed_out = False

    def dfs(assign):
        nonlocal nodes, propagations, conflicts, node_limited, timed_out

        nodes += 1

        if node_limit and nodes >= node_limit:
            node_limited = True
            return None

        if seconds > 0 and nodes % 1000 == 0 and time.time() - start > seconds:
            timed_out = True
            return None

        assign = assign[:]
        ok, forced = unit_propagate(clauses, assign)
        propagations += forced

        if not ok:
            conflicts += 1
            return None

        var = choose_var(clauses, assign, n)

        if var < 0:
            return assign

        # Try both values. Value order is heuristic, not proof-critical.
        for val in (0, 1):
            nxt = assign[:]
            nxt[var] = val
            res = dfs(nxt)
            if res is not None:
                return res
            if node_limited or timed_out:
                return None

        return None

    result = dfs([-1] * n)
    elapsed = time.time() - start

    return {
        "found": result is not None,
        "chi": None if result is None else "".join(str(x) for x in result),
        "nodes": nodes,
        "propagations": propagations,
        "conflicts": conflicts,
        "node_limited": node_limited,
        "timed_out": timed_out,
        "elapsed_sec": elapsed,
    }


def analyze_case(a, b, n, max_graphs, node_limit, seconds_per_graph):
    edge_count = n * (n - 1) // 2
    total_graphs = 1 << edge_count

    if max_graphs and total_graphs > max_graphs:
        raise RuntimeError(f"Refusing enumeration: {total_graphs} graphs exceeds max_graphs {max_graphs}")

    rows = []
    clean_count = 0
    found_count = 0
    proved_no_target = 0
    unknown = 0

    for gmask in range(total_graphs):
        adj = graph_from_bits(n, gmask)

        if score(adj, a, b) != 0:
            continue

        clean_count += 1

        red_terms, blue_terms = predecessor_terms(adj, a, b)
        clauses = build_clauses(red_terms, blue_terms)

        res = dpll_empty_shadow(
            clauses=clauses,
            n=n,
            node_limit=node_limit,
            seconds=seconds_per_graph,
        )

        if res["found"]:
            found_count += 1
        elif res["node_limited"] or res["timed_out"]:
            unknown += 1
        else:
            proved_no_target += 1

        rows.append({
            "a": a,
            "b": b,
            "n": n,
            "graph_index": clean_count,
            "graph_mask": gmask,
            "graph_bits_sha256": hashlib.sha256(bits_string(n, gmask).encode("ascii")).hexdigest(),
            "red_terms": len(red_terms),
            "blue_terms": len(blue_terms),
            "clauses": len(clauses),
            "found_empty_shadow": res["found"],
            "chi": res["chi"],
            "nodes": res["nodes"],
            "propagations": res["propagations"],
            "conflicts": res["conflicts"],
            "node_limited": res["node_limited"],
            "timed_out": res["timed_out"],
            "elapsed_sec": res["elapsed_sec"],
        })

    return {
        "summary": {
            "case": f"R({a},{b}) n={n} target=0",
            "a": a,
            "b": b,
            "n": n,
            "edge_count": edge_count,
            "total_graphs": total_graphs,
            "clean_graphs": clean_count,
            "found_empty_shadow_graphs": found_count,
            "proved_no_empty_shadow_graphs": proved_no_target,
            "unknown_graphs": unknown,
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
    ap.add_argument("--max-graphs", type=int, default=3000000)
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
            max_graphs=args.max_graphs,
            node_limit=args.node_limit,
            seconds_per_graph=args.seconds_per_graph,
        )

        summaries.append(result["summary"])

        csv_path = outdir / f"DPLL_EMPTY_SHADOW_R{a}_{b}_N{n}.csv"
        write_csv(csv_path, result["rows"])

    report = {
        "run_type": "MACHURA_DELTA_SHADOW_DPLL_V14B",
        "summaries": summaries,
    }

    report_path = outdir / "REPORT_DELTA_SHADOW_DPLL_V14B.json"
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

    lines = [
        "MACHURA DELTA SHADOW DPLL ENGINE V14B",
        "=====================================",
        "",
        "Purpose:",
        "Algorithmic DPLL search for empty shadow using product-fuse clauses.",
        "",
    ]

    for s in summaries:
        lines.append(f"CASE: {s['case']}")
        lines.append(f"CLEAN_GRAPHS: {s['clean_graphs']}")
        lines.append(f"FOUND_EMPTY_SHADOW_GRAPHS: {s['found_empty_shadow_graphs']}")
        lines.append(f"PROVED_NO_EMPTY_SHADOW_GRAPHS: {s['proved_no_empty_shadow_graphs']}")
        lines.append(f"UNKNOWN_GRAPHS: {s['unknown_graphs']}")
        lines.append("")

    summary_path = outdir / "SUMMARY_DELTA_SHADOW_DPLL_V14B.txt"
    summary_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    manifest = write_manifest(outdir)

    print("DONE")
    print(f"REPORT: {report_path}")
    print(f"SUMMARY: {summary_path}")
    print(f"MANIFEST: {manifest}")
    print(json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
