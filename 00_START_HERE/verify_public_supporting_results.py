#!/usr/bin/env python3
"""Verify publicly deposited secondary RQ2 policy contrasts and state diagnostics.

Graph identities are the units (200 independent graphs; 50 per size).
This recomputes point estimates and algebraic identities, not hypothesis
test p-values or every historical bootstrap interval.
"""
from collections import defaultdict
from csv import DictReader
from pathlib import Path
from statistics import mean

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "05_Results_and_Analysis/02_RQ2_Selection_and_Packet_Execution/STAGE_D_GRAPH_METHOD_STATE.csv"
groups = defaultdict(dict)
with SOURCE.open(newline="",encoding="utf-8-sig") as f:
    for r in DictReader(f):
        graph = (r["size"],r["seed"])
        key = (r["method"],r["state"])
        if key in groups[graph]:
            raise ValueError(f"Duplicate graph-method-state observation: {graph} {key}")
        groups[graph][key] = float(r["delivered_fraction"])

if len(groups)!=200 or any(len(r)!=24 for r in groups.values()):
    raise ValueError("Expected 200 graphs with eight methods in all three states")

def verify(label, obs, n, expected, tol=1e-10):
    if len(obs)!=n:
        raise ValueError(f"{label}: incorrect graph count {len(obs)}")
    value = mean(obs)
    if abs(value-expected)>tol:
        raise ValueError(f"{label}: expected {expected:+.12f}, observed {value:+.12f}")
    print(f"PASS {label}: n={n}, mean={value:+.12f}")

def contrast(rows, method, state="conflict-dense"):
    return [row[("B5_CONFLICT_RANK",state)]-row[(method,state)] for row in rows]

all_rows=list(groups.values())
comparators={
    "B1_MAPE_CAP_WS":0.00830221513228379,
    "A1_U_NEFF":0.000885460475450256,
    "B4_FULL_SHAPE":0.0008117653905270988,
    "B5_MAE_ONLY":-0.00014474952473453984,
    "B5_GLOBAL_RANK":0.00017087147637573574,
    "B5_NOTIE":0.0023072571865230553,
}
for method,estimate in comparators.items():
    verify("Secondary RQ2 B5 minus "+method,contrast(all_rows,method),200,estimate)

state_means={"conflict-dense":-0.0019799247653576654,
             "partial-blockage":0.00009017487467513463,
             "persistent-degradation":-0.0002573801826911787}
for state,target in state_means.items():
    verify("B5 minus B3 / "+state,contrast(all_rows,"B3_U_ONLY",state),200,target)

weights={"conflict-dense":2/7,"partial-blockage":3/7,"persistent-degradation":2/7}
comp=[sum(w*(r[("B5_CONFLICT_RANK",s)]-r[("B3_U_ONLY",s)]) for s,w in weights.items()) for r in all_rows]
verify("Three-state prespecified weighted B5-B3 difference",comp,200,-0.0006005836102960403)
by_size={"n8":0.00041402619201274637,"n12":-0.0012006348663824928,
         "n16":0.005053110118180886,"n24":-0.0121862005052418}
for size,target in by_size.items():
    subset=[r for (n,seed),r in groups.items() if n==size]
    verify("Exploratory size "+size,contrast(subset,"B3_U_ONLY"),50,target)
print("PUBLIC SECONDARY GRAPH-LEVEL CONTRAST VERIFICATION: PASS")
