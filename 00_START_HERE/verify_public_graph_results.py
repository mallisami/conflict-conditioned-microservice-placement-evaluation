#!/usr/bin/env python3
"""Recalculate primary graph-level point estimates from published compact CSVs.

Standard library only. No raw archives, simulator, or Kubernetes required.
This checks mean paired differences and counts, NOT bootstrap confidence
intervals, raw-trace integrity, or rerun equivalence.
"""
from collections import defaultdict
from csv import DictReader
from pathlib import Path
from statistics import mean

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "05_Results_and_Analysis"


def rows(relative):
    with (RESULTS / relative).open(newline="", encoding="utf-8-sig") as stream:
        return list(DictReader(stream))


def check(label, values, expected_n, expected, tolerance=1e-11):
    actual = mean(values)
    ok = len(values) == expected_n and abs(actual - expected) <= tolerance
    print(f"{label}: n={len(values)}, mean={actual:+.12f}: {'PASS' if ok else 'FAIL'}")
    if not ok:
        raise SystemExit(f"Expected {expected_n} observations and {expected:+.12f}")


def run():
    pred = rows("01_RQ1_Prediction/PREDICTION_PANEL_GRAPH_METRICS.csv")
    for panel, target in (("ID", 0.0013081413131482166), ("OOD", 0.003650035911987598)):
        effects = [float(r["mae_B5_CONFLICT_RANK"]) - float(r["mae_B3_U_ONLY"])
                   for r in pred if r["split"].upper() == panel]
        check(f"RQ1 {panel}: B5 minus B3 MAE", effects, 60, target)

    delivery = rows("02_RQ2_Selection_and_Packet_Execution/RQ2_Selection_and_Delivery_Graph_Level.csv")
    effects = [float(r["delta"]) for r in delivery]
    check("RQ2 conflict-dense: B5 minus B3 delivery", effects, 200, -0.0019799247653576654)
    changed = sum(str(r["different"]).strip().lower() in ("true", "1") for r in delivery)
    wins = sum(x > 1e-12 for x in effects)
    losses = sum(x < -1e-12 for x in effects)
    ties = len(effects) - wins - losses
    if (changed, wins, losses, ties) != (140, 81, 59, 60):
        raise SystemExit(f"RQ2 accounting FAIL: {(changed, wins, losses, ties)}")
    print(f"RQ2 selection and directional accounting: {changed=} {wins=} {losses=} {ties=}: PASS")

    first = rows("07_Initial_Kubernetes_Experiment/STAGE_E_CELLS.csv")
    initial = defaultdict(list)
    for r in first:
        if r["load_regime"] == "high" and r["method"] in ("B3_U_ONLY", "B5_CONFLICT_RANK"):
            initial[(r["seed"], r["method"])].append(float(r["completion"]))
    seeds = sorted({seed for seed, _ in initial})
    if any((seed, method) not in initial for seed in seeds for method in ("B3_U_ONLY", "B5_CONFLICT_RANK")):
        raise SystemExit("Initial Kubernetes: incomplete paired graph data")
    differences = [mean(initial[seed, "B5_CONFLICT_RANK"]) - mean(initial[seed, "B3_U_ONLY"])
                   for seed in seeds]
    check("Initial Kubernetes high-load (within-graph repeat means)", differences, 40, 0.003345691379148222)

    fresh = rows("08_Fresh_Kubernetes_RQ3/RQ3_ALL_CELLS.csv")
    table = defaultdict(dict)
    for r in fresh:
        if r["replicate"] == "1":
            key = (r["panel"], r["seed"])
            if r["method"] in table[key]:
                raise SystemExit(f"Duplicate primary execution cell: {key} {r['method']}")
            table[key][r["method"]] = float(r["completion"])
    expected_pair = ("B5_COMPLETE", "B3_STRICT")
    if any(not all(m in methods for m in expected_pair) for methods in table.values()):
        raise SystemExit("Fresh Kubernetes: incomplete B5/B3 strict pairs")
    strict = [v["B5_COMPLETE"] - v["B3_STRICT"] for v in table.values()]
    check("Fresh Kubernetes complete minus strict", strict, 256, -0.00567851820936318)
    a = [v["B5_COMPLETE"] - v["B3_STABILIZED"]
         for (panel, _), v in table.items() if panel == "A" and "B3_STABILIZED" in v]
    check("Fresh Kubernetes Panel A matched stabilizer", a, 128, -0.007082987694544622)
    print("PUBLIC GRAPH-LEVEL POINT-ESTIMATE VERIFICATION: PASS")
    print("Scope: point estimates and accounting only. Confidence intervals and original packet traces are not recomputed.")


if __name__ == "__main__":
    run()
