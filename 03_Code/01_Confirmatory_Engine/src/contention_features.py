from __future__ import annotations
from dataclasses import dataclass
import math
from typing import Mapping

@dataclass(frozen=True)
class ContentionShape:
    utilization: float
    headroom: float
    active_streams: int
    hhi: float
    n_eff: float
    total_airtime_seconds: float

def from_airtime_by_directed_pair(airtime: Mapping[str,float], budget_seconds: float) -> ContentionShape:
    if not math.isfinite(budget_seconds) or budget_seconds <= 0:
        raise ValueError("budget_seconds must be finite and > 0")
    raw=[float(v) for v in airtime.values()]
    if any((not math.isfinite(v) or v < 0) for v in raw):
        raise ValueError("airtime values must be finite and non-negative")
    vals=[v for v in raw if v>0]
    total=sum(vals)
    u=total/budget_seconds
    if not vals:
        return ContentionShape(u,1.0-u,0,0.0,0.0,total)
    p=[v/total for v in vals]
    hhi=sum(x*x for x in p)
    return ContentionShape(u,1.0-u,len(vals),hhi,1.0/hhi,total)

def aggregate_pair_airtime(problem, placement, scenario):
    from mape_cap_bplus.objective import link_for
    nodes=problem.node_by_id
    out={}
    for flow in problem.flows:
        src=nodes[placement[flow.source_replica]].rack_id
        dst=nodes[placement[flow.destination_replica]].rack_id
        if src==dst: continue
        link=link_for(scenario,src,dst)
        if not link.available or not link.conflict_group: continue
        key=(link.conflict_group,f"{src}>{dst}")
        out[key]=out.get(key,0.0)+flow.bits_per_window/link.goodput_bps
    return out

def placement_contention_shapes(problem, placement):
    result={}
    for scenario in problem.scenarios:
        agg=aggregate_pair_airtime(problem,placement,scenario)
        for group,budget in scenario.conflict_budgets_seconds.items():
            pairs={pair:a for (g,pair),a in agg.items() if g==group}
            result[(scenario.scenario_id,group)]=from_airtime_by_directed_pair(pairs,budget)
    return result
