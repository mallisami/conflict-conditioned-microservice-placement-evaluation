#!/usr/bin/env python3
"""Recompute independently seeded graph-paired percentile-bootstrap intervals.

Uses public graph-level/cell CSV files and no original execution logs.
The archived historical RNG draws are not recovered, so these 100,000-draw
Monte Carlo intervals may differ slightly from published limits.
"""
import argparse
import random
from math import floor
from statistics import mean
from collections import defaultdict
from verify_public_graph_results import rows

def bootstrap(deltas, reps, seed):
    rng = random.Random(seed)
    n = len(deltas)
    estimates = sorted(sum(rng.choices(deltas,k=n))/n for _ in range(reps))
    def q(p):
        z = (reps-1)*p
        i = floor(z)
        return estimates[i]+(estimates[min(i+1,reps-1)]-estimates[i])*(z-i)
    return q(.025),q(.975)

def study_panels():
    pred=rows("01_RQ1_Prediction/PREDICTION_PANEL_GRAPH_METRICS.csv")
    for panel in ("ID","OOD"):
        yield "RQ1 "+panel,[float(r["mae_B5_CONFLICT_RANK"])-float(r["mae_B3_U_ONLY"]) for r in pred if r["split"].upper()==panel],60
    delivery=rows("02_RQ2_Selection_and_Packet_Execution/RQ2_Selection_and_Delivery_Graph_Level.csv")
    yield "RQ2 paired delivery",[float(r["delta"]) for r in delivery],200
    first=rows("07_Initial_Kubernetes_Experiment/STAGE_E_CELLS.csv")
    g=defaultdict(list)
    for r in first:
        if r["load_regime"]=="high" and r["method"] in ("B3_U_ONLY","B5_CONFLICT_RANK"):
            g[(r["seed"],r["method"])].append(float(r["completion"]))
    seeds=sorted({s for s,m in g})
    if any(not g.get((s,m)) for s in seeds for m in ("B3_U_ONLY","B5_CONFLICT_RANK")):
        raise ValueError("Original RQ3 incomplete graph pairs")
    yield "RQ3 original high load",[mean(g[(s,"B5_CONFLICT_RANK")])-mean(g[(s,"B3_U_ONLY")]) for s in seeds],40
    fresh=rows("08_Fresh_Kubernetes_RQ3/RQ3_ALL_CELLS.csv")
    pairs=defaultdict(dict)
    for r in fresh:
        if r["replicate"]=="1":
            key=(r["panel"],r["seed"])
            if r["method"] in pairs[key]:
                raise ValueError("Duplicate fresh graph/method")
            pairs[key][r["method"]]=float(r["completion"])
    if any("B5_COMPLETE" not in p or "B3_STRICT" not in p for p in pairs.values()):
        raise ValueError("Unpaired fresh graph")
    yield "Fresh RQ3 strict",[p["B5_COMPLETE"]-p["B3_STRICT"] for p in pairs.values()],256
    yield "Fresh RQ3 matched stabilization",[p["B5_COMPLETE"]-p["B3_STABILIZED"] for (panel,seed),p in pairs.items() if panel=="A" and "B3_STABILIZED" in p],128

def main():
    a=argparse.ArgumentParser()
    a.add_argument("--resamples",type=int,default=100000)
    a.add_argument("--seed",type=int,default=20261022)
    args=a.parse_args()
    if args.resamples<100:
        a.error("At least 100 resamples")
    for i,(name,deltas,n) in enumerate(study_panels()):
        if len(deltas)!=n:
            raise ValueError(f"{name}: expected {n} graphs; got {len(deltas)}")
        low,high=bootstrap(deltas,args.resamples,args.seed+i)
        print(f"{name}: n={n}, mean={mean(deltas):+.9f}, CI95=[{low:+.9f},{high:+.9f}]")
    print("PASS: independent graph-identity bootstrap computations completed")

if __name__=="__main__":
    main()
