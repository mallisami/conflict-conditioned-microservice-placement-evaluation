#!/usr/bin/env python3
"""Read-only guard for the public B5 development-gate disposition.

A successful exit means the disclosed audit state is internally consistent;
it does NOT mean that the scientific development gate has passed.
"""
from __future__ import annotations

import json
import math
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
LOCK_PATH = ROOT / "02_Methods_and_Configuration/03_Model_Locks/B5_MODEL_LOCK.json"
SUMMARY_PATH = ROOT / "05_Results_and_Analysis/09_Development_Selection_Audit/outputs/h1b/H1B_SUMMARY_20261019.json"
CALIBRATION_BASENAME = "calibration_aggregated.csv"


def fail(message: str) -> None:
    print(f"FAIL: {message}", file=sys.stderr)
    raise SystemExit(2)


def close(label: str, actual: float, expected: float, tolerance: float = 1e-12) -> None:
    if not math.isfinite(actual) or abs(actual - expected) > tolerance:
        fail(f"{label}: expected {expected:.15g}, found {actual!r}")
    print(f"PASS historical value: {label} = {actual:.12f}")


def main() -> int:
    for path in (LOCK_PATH, SUMMARY_PATH):
        if not path.is_file():
            fail(f"required audit input is missing: {path.relative_to(ROOT)}")

    lock = json.loads(LOCK_PATH.read_text(encoding="utf-8"))
    summary = json.loads(SUMMARY_PATH.read_text(encoding="utf-8"))
    gate = lock["development_gate"]
    corrected = summary["corrected_matched_policy_comparison"]

    if gate.get("passed") is not True:
        fail("historical model-lock gate field changed; inspect the frozen lock before updating this guard")
    if summary.get("nested_cv_performed") is not False:
        fail("expected historical audit to disclose nested_cv_performed=false")
    if summary.get("explicit_OOD_traffic_family_split_in_development_builder") is not False:
        fail("expected historical audit to disclose no explicit OOD traffic-family split")

    close("legacy B4 strict-regret threshold in frozen lock",
          float(gate["required_primary_oof_near_regret_le_B4_strict"]),
          0.0011698364338995793)
    close("corrected B4 strict regret",
          float(corrected["B4_strict_regret"]),
          0.0011208594647832)
    close("B5 selected OOF near-margin regret",
          float(corrected["B5_OOF_near_regret"]),
          0.0011250596781460325)
    close("B5 selected OOF strict regret",
          float(corrected["B5_OOF_strict_regret"]),
          0.001802098572433097)
    close("corrected B4 matched near-margin regret",
          float(corrected["B4_matched_near_regret"]),
          0.0012872232478627)

    mixed_difference = float(corrected["B5_OOF_near_regret"]) - float(corrected["B4_strict_regret"])
    strict_difference = float(corrected["B5_OOF_strict_regret"]) - float(corrected["B4_strict_regret"])
    near_difference = float(corrected["B5_OOF_near_regret"]) - float(corrected["B4_matched_near_regret"])
    close("mixed-rule difference (B5 near minus B4 strict)",
          mixed_difference, 0.000004200213362832387)
    close("same-rule strict difference (B5 strict minus B4 strict)",
          strict_difference, 0.000681239107649897)
    close("same-rule near difference (B5 near minus B4 near)",
          near_difference, -0.0001621635697166675)

    weight_min = float(summary["dense_pair_weight_share_leave_one_dense_graph_out_min"])
    weight_max = float(summary["dense_pair_weight_share_leave_one_dense_graph_out_max"])
    if not (0.99 <= weight_min <= weight_max <= 1.0):
        fail(f"unexpected dense-oracle pair-weight concentration: min={weight_min}, max={weight_max}")
    if int(summary["non_tied_pair_count"]) != 55722:
        fail("historical non-tied pair count changed")
    print(f"BLOCKER: dense N=8 oracle groups dominate pairwise weight mass "
          f"(leave-one-dense-graph-out range {weight_min:.4%}–{weight_max:.4%}).")
    print("BLOCKER: no nested cross-validation and no explicit held-out traffic-family split.")
    calibration_files = sorted(
        path for path in ROOT.rglob(CALIBRATION_BASENAME)
        if ".git" not in path.parts
    )
    if calibration_files:
        print("INPUT FOUND: historical calibration file basename exists; verify provenance and contents before any refit:")
        for path in calibration_files:
            print(f"  - {path.relative_to(ROOT)}")
        print("BLOCKER: a file's presence alone does not establish source authenticity or close the development gate.")
    else:
        print(f"BLOCKER: {CALIBRATION_BASENAME} is absent from this checkout; historical B3 cannot be independently refitted here.")
    print("AUDIT INTEGRITY: PASS")
    print("SCIENTIFIC DEVELOPMENT GATE: BLOCKED — this script is a disclosure guard, not a validation.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
