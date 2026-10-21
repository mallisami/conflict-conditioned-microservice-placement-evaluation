#!/usr/bin/env python3
from __future__ import annotations
import json, random, sys, time
from dataclasses import replace
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
import run_stage_c as C
import b5_model as B5
FULL=json.loads((ROOT/'config/full_campaign.json').read_text());CFG=FULL['stage_c_robustness'];OUT=ROOT/'stage_c_robustness_results'
def dump(p,o):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(o,indent=2,sort_keys=True),encoding='utf-8')
def perturb_problem(p,eps,seed):
    rng=random.Random(seed)
    flow_factor={f"{f.source_replica}>{f.destination_replica}":rng.uniform(1-eps,1+eps) for f in p.flows}
    flow=tuple(replace(f,bits_per_window=float(f.bits_per_window)*flow_factor[f"{f.source_replica}>{f.destination_replica}"]) for f in p.flows)
    scenarios=[]
    for sc in p.scenarios:
        links={}
        for (a,b),ln in sc.links.items():
            fac=rng.uniform(1-eps,1+eps)
            links[(a,b)]=replace(ln,goodput_bps=max(1.0,float(ln.goodput_bps)*fac))
        scenarios.append(replace(sc,links=links))
    return replace(p,flows=flow,scenarios=tuple(scenarios))
def _solve_graph(args):
    gp_s,coeffs=args; gp=Path(gp_s); g=json.loads(gp.read_text())
    if not g.get('valid') or g.get('no_admissible_placement'): return []
    p,_=C.build_scaled_problem(g['size'],int(g['seed']));b5_lock=B5.load_lock();b5_delta=B5.near_margin(b5_lock)
    nominal={k:g['selections'][k]['placement'] for k in ['B3_U_ONLY','B5_CONFLICT_RANK']}
    cases=[]
    for eps in CFG['eps']:
        for rep in range(int(CFG['realizations_per_eps'])):
            seed=int(CFG['seed_base'])+int(g['seed'])*31+rep+int(round(float(eps)*1000))
            cases.append({'eps':float(eps),'rep':rep,'problem':perturb_problem(p,float(eps),seed),
                          'best_b3':None,'b5_min':float('inf'),'b5_near':[]})
    raw=adm=0; t0=time.time()
    # IMPORTANT: the hard-admission set is frozen. Enumerate and test nominal admission ONCE,
    # then rescore each admissible candidate under all telemetry perturbations. This is
    # scientifically equivalent to the previous implementation but avoids 15 redundant
    # exact-neighborhood/admission passes per graph.
    for pl,mv in C.candidates(p,p.max_relocations or 0):
        raw+=1
        if not C.cluster_ok(p,pl): continue
        ev=C.evaluate_placement(p,pl,C.RISK)
        if not ev.feasible: continue
        adm+=1; key=C.pkey(pl)
        for case in cases:
            cs,_=C.calibrated_scores(case['problem'],pl,coeffs);b5s,_=B5.placement_scores(case['problem'],pl,b5_lock)
            c3=(float(cs['B3_U_ONLY']),int(mv),key,dict(pl))
            if case['best_b3'] is None or c3[:3]<case['best_b3'][:3]:case['best_b3']=c3
            bs=float(b5s['B5_CONFLICT_RANK']);bev=C.evaluate_placement(case['problem'],pl,C.RISK);b1=float(bev.total_objective)
            if bs<case['b5_min']:
                case['b5_min']=bs;case['b5_near']=[x for x in case['b5_near'] if x[0]<=bs+b5_delta+C.EPS]
            if bs<=case['b5_min']+b5_delta+C.EPS:case['b5_near'].append((bs,b1,int(mv),key,dict(pl)))
    out=[]
    for case in cases:
        if case['best_b3'] is None or not case['b5_near']:
            raise RuntimeError(f"robustness graph lost all frozen-admissible candidates: {g['size']}/{g['seed']}")
        elig=[x for x in case['b5_near'] if x[0]<=case['b5_min']+b5_delta+C.EPS];b5=min(elig,key=lambda x:(x[1],x[2],x[3]));b3=case['best_b3']
        out.append({'size':g['size'],'seed':g['seed'],'eps':case['eps'],'rep':case['rep'],
                    'B3_stable':b3[3]==nominal['B3_U_ONLY'],
                    'B5_stable':b5[4]==nominal['B5_CONFLICT_RANK'],
                    'B3_B5_same':b3[3]==b5[4],
                    'raw_candidates_visited':raw,'frozen_admissible_candidates':adm})
    return out
def run(workers=None):
    coeffs,_=C.load_coeffs(); gps=[]
    for gp in sorted((ROOT/'stage_c_results/graphs').glob('*.json')):
        g=json.loads(gp.read_text())
        if g.get('valid') and not g.get('no_admissible_placement'): gps.append(gp)
    w=int(workers or FULL.get('stage_c_robustness_workers',3)); records=[];t0=time.time();done=0
    from concurrent.futures import ProcessPoolExecutor
    with ProcessPoolExecutor(max_workers=w) as ex:
        for rr in ex.map(_solve_graph,[(str(gp),coeffs) for gp in gps]):
            records.extend(rr);done+=1
            if done%5==0 or done==len(gps): print(f"[Robustness {done}/{len(gps)} graphs] {(time.time()-t0)/60:.1f} min",flush=True)
    rep={'implementation':{'workers':w,'policy':'nominal hard admission enumerated once per graph; all 15 perturbations rescore the identical frozen X_adm'}}
    for eps in CFG['eps']:
        rr=[x for x in records if float(x['eps'])==float(eps)]
        rep[str(eps)]={'n':len(rr),'B3_stability':float(np.mean([x['B3_stable'] for x in rr])),'B5_stability':float(np.mean([x['B5_stable'] for x in rr])),
                       'B3_B5_same_fraction':float(np.mean([x['B3_B5_same'] for x in rr]))}
    OUT.mkdir(parents=True,exist_ok=True);dump(OUT/'ROBUSTNESS_RECORDS.json',records);dump(OUT/'ROBUSTNESS_SUMMARY.json',rep);return rep
def main():
    import argparse
    ap=argparse.ArgumentParser();ap.add_argument('--workers',type=int);a=ap.parse_args();print(json.dumps(run(a.workers),indent=2))
if __name__=='__main__':main()
