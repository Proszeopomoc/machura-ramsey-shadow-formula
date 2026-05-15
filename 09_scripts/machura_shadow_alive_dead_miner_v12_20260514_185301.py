#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from statistics import mean


NUM_COLS = [
    "red_pred_count",
    "blue_pred_count",
    "min_phi",
    "min_red_phi",
    "min_blue_phi",
    "min_degree",
    "phi0_count",
    "phi1_count",
]


def to_int(x, default=0):
    try:
        return int(str(x).strip())
    except Exception:
        return default


def load_rows(path: Path):
    with path.open("r", encoding="utf-8", errors="replace", newline="") as f:
        return list(csv.DictReader(f))


def summarize_group(rows):
    out = {"count": len(rows)}
    if not rows:
        return out

    for col in NUM_COLS:
        vals = [to_int(r.get(col, 0)) for r in rows]
        out[col] = {
            "min": min(vals),
            "max": max(vals),
            "mean": mean(vals),
        }

    return out


def split_alive_dead(rows):
    alive = [r for r in rows if to_int(r.get("phi0_count", 0)) > 0]
    dead = [r for r in rows if to_int(r.get("phi0_count", 0)) == 0]
    return alive, dead


def compare(alive, dead):
    comp = {}
    for col in NUM_COLS:
        av = [to_int(r.get(col, 0)) for r in alive]
        dv = [to_int(r.get(col, 0)) for r in dead]

        if av and dv:
            comp[col] = {
                "alive_mean": mean(av),
                "dead_mean": mean(dv),
                "dead_minus_alive": mean(dv) - mean(av),
                "alive_min": min(av),
                "alive_max": max(av),
                "dead_min": min(dv),
                "dead_max": max(dv),
            }
        elif av:
            comp[col] = {
                "alive_mean": mean(av),
                "dead_mean": None,
                "dead_minus_alive": None,
                "alive_min": min(av),
                "alive_max": max(av),
                "dead_min": None,
                "dead_max": None,
            }
        elif dv:
            comp[col] = {
                "alive_mean": None,
                "dead_mean": mean(dv),
                "dead_minus_alive": None,
                "alive_min": None,
                "alive_max": None,
                "dead_min": min(dv),
                "dead_max": max(dv),
            }
    return comp


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--outdir", required=True)
    ap.add_argument("--graph-summary", action="append", required=True)
    args = ap.parse_args()

    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=False)

    cases = []

    for fp in args.graph_summary:
        path = Path(fp)
        rows = load_rows(path)
        alive, dead = split_alive_dead(rows)

        case = {
            "file": str(path),
            "rows": len(rows),
            "alive_count": len(alive),
            "dead_count": len(dead),
            "alive_fraction": len(alive) / len(rows) if rows else None,
            "dead_fraction": len(dead) / len(rows) if rows else None,
            "alive_summary": summarize_group(alive),
            "dead_summary": summarize_group(dead),
            "comparison": compare(alive, dead),
        }
        cases.append(case)

    report = {
        "run_type": "MACHURA_SHADOW_ALIVE_DEAD_MINER_V12",
        "cases": cases,
    }

    report_path = outdir / "REPORT_SHADOW_ALIVE_DEAD_MINER_V12.json"
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

    lines = [
        "MACHURA SHADOW ALIVE-DEAD MINER V12",
        "====================================",
        "",
        "Purpose:",
        "Compare clean cores with Phi=0 extensions against clean cores without Phi=0 extensions.",
        "",
    ]

    for c in cases:
        lines.append(f"FILE: {c['file']}")
        lines.append(f"ROWS: {c['rows']}")
        lines.append(f"ALIVE_COUNT: {c['alive_count']}")
        lines.append(f"DEAD_COUNT: {c['dead_count']}")
        lines.append(f"ALIVE_FRACTION: {c['alive_fraction']}")
        lines.append(f"DEAD_FRACTION: {c['dead_fraction']}")

        lines.append("KEY DIFFERENCES:")
        for col, d in c["comparison"].items():
            lines.append(
                f"- {col}: alive_mean={d.get('alive_mean')} dead_mean={d.get('dead_mean')} dead_minus_alive={d.get('dead_minus_alive')}"
            )
        lines.append("")

    summary_path = outdir / "SUMMARY_SHADOW_ALIVE_DEAD_MINER_V12.txt"
    summary_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print("DONE")
    print(f"REPORT: {report_path}")
    print(f"SUMMARY: {summary_path}")
    print(json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
