#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import shutil
from collections import Counter
from pathlib import Path


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8", errors="replace"))


def read_csv(path: Path):
    with path.open("r", encoding="utf-8", errors="replace", newline="") as f:
        return list(csv.DictReader(f))


def write_csv(path: Path, rows):
    if not rows:
        path.write_text("", encoding="utf-8")
        return

    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)


def safe_copy(src: Path, dst: Path):
    if dst.exists():
        raise RuntimeError(f"Refusing overwrite: {dst}")
    shutil.copy2(src, dst)


def case_id(a, b):
    return f"R{a}_{b}"


def find_latest_transition_reports(runs_root: Path):
    reports = list(runs_root.rglob("REPORT_SHADOW_TRANSITION_FROM_PHI0_V12.json"))
    by_case = {}

    for p in reports:
        try:
            j = read_json(p)
            a = int(j["a"])
            b = int(j["b"])
            key = (a, b)
            if key not in by_case or p.stat().st_mtime > by_case[key].stat().st_mtime:
                by_case[key] = p
        except Exception:
            continue

    return by_case


def find_latest_v16_reports(runs_root: Path):
    reports = list(runs_root.rglob("REPORT_SHADOW_COORDINATE_PROFILER_V16.json"))
    by_case_n = {}

    for p in reports:
        try:
            j = read_json(p)
            a = int(j["a"])
            b = int(j["b"])
            n = int(j["n"])
            key = (a, b, n)
            if key not in by_case_n or p.stat().st_mtime > by_case_n[key].stat().st_mtime:
                by_case_n[key] = p
        except Exception:
            continue

    return by_case_n


def summarize_witnesses(witness_csv: Path):
    if not witness_csv.exists():
        return {
            "exists": False,
            "total_minimal_witnesses": None,
            "type_distribution": {},
            "degree_distribution": {},
            "per_core_min": None,
            "per_core_max": None,
            "per_core_average": None,
        }

    rows = read_csv(witness_csv)

    type_counter = Counter()
    degree_counter = Counter()
    per_core = Counter()

    for r in rows:
        rp = str(r.get("red_phi", "")).strip()
        bp = str(r.get("blue_phi", "")).strip()
        deg = str(r.get("degree", "")).strip()
        gi = str(r.get("graph_index", "")).strip()

        type_counter[f"red_phi={rp};blue_phi={bp}"] += 1
        degree_counter[f"degree={deg}"] += 1
        per_core[gi] += 1

    values = list(per_core.values())

    return {
        "exists": True,
        "total_minimal_witnesses": len(rows),
        "type_distribution": dict(sorted(type_counter.items())),
        "degree_distribution": dict(sorted(degree_counter.items())),
        "per_core_min": min(values) if values else None,
        "per_core_max": max(values) if values else None,
        "per_core_average": (sum(values) / len(values)) if values else None,
    }


def make_case_package(
    outroot: Path,
    transition_report: Path,
    v16_report: Path | None,
):
    tr = read_json(transition_report)

    a = int(tr["a"])
    b = int(tr["b"])
    cid = case_id(a, b)

    source_n = int(tr["source_n"])
    critical_n = int(tr["target_n"])
    boundary_n = critical_n + 1
    delta = int(tr["global_min_phi_to_next_layer"])

    case_dir = outroot / f"CASE_{cid}"
    if case_dir.exists():
        raise RuntimeError(f"Refusing overwrite existing case dir: {case_dir}")
    case_dir.mkdir(parents=True)

    v16 = None
    v16_outputs = {}
    witness_summary = {
        "exists": False,
        "total_minimal_witnesses": None,
        "type_distribution": {},
        "degree_distribution": {},
        "per_core_min": None,
        "per_core_max": None,
        "per_core_average": None,
    }

    if v16_report is not None and v16_report.exists():
        v16 = read_json(v16_report)
        v16_outputs = v16.get("outputs", {})

        witness_path = Path(v16_outputs.get("min_witnesses", ""))
        witness_summary = summarize_witnesses(witness_path)

    case_summary = {
        "case_name": f"R({a},{b})",
        "a": a,
        "b": b,
        "source_n": source_n,
        "critical_n": critical_n,
        "boundary_n": boundary_n,
        "shadow_boundary_delta": delta,
        "status": tr.get("status"),
        "phi0_source_rows": tr.get("phi0_source_rows"),
        "reconstructed_clean_graphs_n_plus_1": tr.get("reconstructed_clean_graphs_n_plus_1"),
        "graphs_with_phi0_to_next_layer": tr.get("graphs_with_phi0_to_next_layer"),
        "total_phi0_to_next_layer": tr.get("total_phi0_to_next_layer"),
        "total_phi1_to_next_layer": tr.get("total_phi1_to_next_layer"),
        "total_phi2_to_next_layer": tr.get("total_phi2_to_next_layer"),
        "global_min_phi_to_next_layer": tr.get("global_min_phi_to_next_layer"),
        "global_phi_hist_to_next_layer": tr.get("global_phi_hist_to_next_layer"),
        "local_delta_distribution": None if v16 is None else v16.get("min_phi_distribution"),
        "graphs_analyzed_by_v16": None if v16 is None else v16.get("graphs_analyzed"),
        "witness_summary": witness_summary,
        "source_files": {
            "transition_report": str(transition_report),
            "transition_report_sha256": sha256_file(transition_report),
            "v16_report": None if v16_report is None else str(v16_report),
            "v16_report_sha256": None if v16_report is None else sha256_file(v16_report),
        },
    }

    summary_json = case_dir / f"01_CASE_SUMMARY_{cid}.json"
    summary_json.write_text(json.dumps(case_summary, indent=2, ensure_ascii=False), encoding="utf-8")

    summary_txt = case_dir / f"02_CASE_SUMMARY_{cid}.txt"
    lines = []
    lines.append(f"MACHURA RAMSEY SHADOW FORMULA - CASE {cid}")
    lines.append("=" * (42 + len(cid)))
    lines.append("")
    lines.append(f"case_name: R({a},{b})")
    lines.append(f"source_n: {source_n}")
    lines.append(f"critical_n: {critical_n}")
    lines.append(f"boundary_n: {boundary_n}")
    lines.append(f"shadow_boundary_delta: {delta}")
    lines.append("")
    lines.append("Transition evidence:")
    lines.append(f"phi0_source_rows: {tr.get('phi0_source_rows')}")
    lines.append(f"reconstructed_clean_graphs_n_plus_1: {tr.get('reconstructed_clean_graphs_n_plus_1')}")
    lines.append(f"total_phi0_to_next_layer: {tr.get('total_phi0_to_next_layer')}")
    lines.append(f"total_phi1_to_next_layer: {tr.get('total_phi1_to_next_layer')}")
    lines.append(f"total_phi2_to_next_layer: {tr.get('total_phi2_to_next_layer')}")
    lines.append(f"global_min_phi_to_next_layer: {tr.get('global_min_phi_to_next_layer')}")
    lines.append(f"global_phi_hist_to_next_layer: {json.dumps(tr.get('global_phi_hist_to_next_layer'), sort_keys=True)}")
    lines.append("")
    lines.append("Local Delta geometry:")
    lines.append(f"local_delta_distribution: {json.dumps(case_summary['local_delta_distribution'], sort_keys=True)}")
    lines.append("")
    lines.append("Minimal shadow witness geometry:")
    lines.append(f"total_minimal_witnesses: {witness_summary.get('total_minimal_witnesses')}")
    lines.append(f"type_distribution: {json.dumps(witness_summary.get('type_distribution'), sort_keys=True)}")
    lines.append(f"degree_distribution: {json.dumps(witness_summary.get('degree_distribution'), sort_keys=True)}")
    lines.append(f"per_core_min: {witness_summary.get('per_core_min')}")
    lines.append(f"per_core_max: {witness_summary.get('per_core_max')}")
    lines.append(f"per_core_average: {witness_summary.get('per_core_average')}")
    lines.append("")
    lines.append("Meaning:")
    lines.append("The transition report reconstructs the clean critical layer from Phi=0 shadows.")
    lines.append("Then it computes the shadow from the critical layer to the boundary layer.")
    lines.append("The smallest nonzero shadow value is recorded as shadow_boundary_delta.")
    lines.append("")
    lines.append("Official formula names:")
    lines.append("Phi_G(x)")
    lines.append("score_{a,b}(G)")
    lines.append("C_n^{a,b}")
    lines.append("Delta_{a,b}(critical_n -> boundary_n)")
    lines.append("shadow_boundary_delta(R(a,b))")

    summary_txt.write_text("\n".join(lines) + "\n", encoding="utf-8")

    delta_csv = case_dir / f"03_SHADOW_BOUNDARY_DELTA_{cid}.csv"
    write_csv(delta_csv, [{
        "case_name": f"R({a},{b})",
        "a": a,
        "b": b,
        "source_n": source_n,
        "critical_n": critical_n,
        "boundary_n": boundary_n,
        "shadow_boundary_delta": delta,
        "total_phi0_to_next_layer": tr.get("total_phi0_to_next_layer"),
        "total_phi1_to_next_layer": tr.get("total_phi1_to_next_layer"),
        "total_phi2_to_next_layer": tr.get("total_phi2_to_next_layer"),
        "status": tr.get("status"),
    }])

    local_delta_csv = case_dir / f"04_LOCAL_DELTA_DISTRIBUTION_{cid}.csv"
    local_rows = []
    dist = case_summary["local_delta_distribution"] or {}
    for k, v in sorted(dist.items(), key=lambda x: int(x[0])):
        local_rows.append({
            "case_name": f"R({a},{b})",
            "local_delta": k,
            "core_count": v,
        })
    write_csv(local_delta_csv, local_rows)

    witness_csv = case_dir / f"05_MINIMAL_SHADOW_WITNESS_PROFILE_{cid}.csv"
    witness_rows = []
    for k, v in witness_summary.get("type_distribution", {}).items():
        witness_rows.append({
            "case_name": f"R({a},{b})",
            "profile_type": "red_blue_phi",
            "profile_key": k,
            "count": v,
        })
    for k, v in witness_summary.get("degree_distribution", {}).items():
        witness_rows.append({
            "case_name": f"R({a},{b})",
            "profile_type": "degree",
            "profile_key": k,
            "count": v,
        })
    write_csv(witness_csv, witness_rows)

    input_csv = case_dir / f"06_INPUT_FILES_{cid}.csv"
    input_rows = [
        {
            "file_role": "transition_report",
            "path": str(transition_report),
            "sha256": sha256_file(transition_report),
        }
    ]
    if v16_report is not None:
        input_rows.append({
            "file_role": "v16_report",
            "path": str(v16_report),
            "sha256": sha256_file(v16_report),
        })
    write_csv(input_csv, input_rows)

    return {
        "case_name": f"R({a},{b})",
        "case_id": cid,
        "case_dir": str(case_dir),
        "critical_n": critical_n,
        "boundary_n": boundary_n,
        "shadow_boundary_delta": delta,
        "local_delta_distribution": case_summary["local_delta_distribution"],
        "witness_summary": witness_summary,
    }


def write_manifest(outroot: Path):
    rows = []
    for p in sorted(outroot.rglob("*")):
        if p.is_file() and p.name != "MANIFEST_SHA256.txt":
            rows.append(f"{sha256_file(p)}  {p.relative_to(outroot)}")
    manifest = outroot / "MANIFEST_SHA256.txt"
    manifest.write_text("\n".join(rows) + "\n", encoding="utf-8")
    return manifest


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs-root", required=True)
    ap.add_argument("--outroot", required=True)
    args = ap.parse_args()

    runs_root = Path(args.runs_root)
    outroot = Path(args.outroot)

    if outroot.exists():
        raise RuntimeError(f"Refusing overwrite existing outroot: {outroot}")
    outroot.mkdir(parents=True)

    transitions = find_latest_transition_reports(runs_root)
    v16s = find_latest_v16_reports(runs_root)

    cases = []

    for key, tr_path in sorted(transitions.items()):
        a, b = key
        tr = read_json(tr_path)
        critical_n = int(tr["target_n"])
        v16_path = v16s.get((a, b, critical_n))
        cases.append(make_case_package(outroot, tr_path, v16_path))

    master_json = outroot / "00_MASTER_CASE_INDEX.json"
    master = {
        "run_type": "MACHURA_RAMSEY_SHADOW_FORMULA_V17_BOUNDARY_ATLAS",
        "cases": cases,
    }
    master_json.write_text(json.dumps(master, indent=2, ensure_ascii=False), encoding="utf-8")

    master_txt = outroot / "00_MASTER_CASE_INDEX.txt"
    lines = [
        "MACHURA RAMSEY SHADOW FORMULA V17 - BOUNDARY ATLAS",
        "===================================================",
        "",
        "Purpose:",
        "Standardized case packages using official terminology from the Machura Ramsey Shadow Formula.",
        "",
        "Cases:",
    ]

    for c in cases:
        lines.append("")
        lines.append(f"case_name: {c['case_name']}")
        lines.append(f"critical_n: {c['critical_n']}")
        lines.append(f"boundary_n: {c['boundary_n']}")
        lines.append(f"shadow_boundary_delta: {c['shadow_boundary_delta']}")
        lines.append(f"local_delta_distribution: {json.dumps(c['local_delta_distribution'], sort_keys=True)}")
        lines.append(f"case_dir: {c['case_dir']}")

    master_txt.write_text("\n".join(lines) + "\n", encoding="utf-8")

    manifest = write_manifest(outroot)

    print("DONE")
    print("OUTROOT:", outroot)
    print("MASTER_JSON:", master_json)
    print("MASTER_TXT:", master_txt)
    print("MANIFEST:", manifest)
    print(json.dumps(master, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
