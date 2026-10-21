#!/usr/bin/env python3
"""B3-only Stage-E load pilot.

Development-only: uses old 710xx graph identities and never evaluates B5. It
freezes three ordered offered-load multipliers before confirmatory RQ3 starts.
"""
from __future__ import annotations
import argparse,itertools,json,random,sys,time
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
import run_stage_c as C
import run_stage_e as E
FULL=json.loads((ROOT/'config/full_campaign.json').read_text());CFG=FULL['stage_e_load_pilot']; OUT=ROOT/'stage_e_load_pilot_results'

def dump(p,o):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(o,indent=2,sort_keys=True)+'\n',encoding='utf-8')
def distance_to_band(x,band):
    lo,hi=map(float,band)
    if lo<=x<=hi:return 0.0
    return lo-x if x<lo else x-hi

def build_pilot_selections():
    coeffs,aroot=C.load_coeffs();cp=aroot/'frozen_coefficients.json';out={}
    for seed in CFG['seeds']:
        r=C.solve_graph(('n8',int(seed),str(cp)))
        if not r.get('valid') or r.get('no_admissible_placement'):raise RuntimeError(f'pilot seed {seed} structurally unusable')
        out[str(seed)]={'placement':r['selections']['B3_U_ONLY']['placement'],'x_adm_sha256':r['x_adm_sha256']}
    dump(OUT/'B3_PILOT_SELECTIONS.json',out);return out

def run_one(seed,mult,placement,info):
    E.setup_lc();problem,node_map=E.execution_problem(seed,info,float(mult));pl={rid:node_map[nid] for rid,nid in placement.items()};sc=next(s for s in problem.scenarios if s.scenario_id=='conflict-dense')
    root=OUT/'cells'/f'm{str(mult).replace(".","p")}'/f'seed-{seed}';accepted=root/'accepted.json'
    if accepted.exists():return json.loads(accepted.read_text())
    root.mkdir(parents=True,exist_ok=True);run_id=f'p2b5-loadpilot:{mult}:{seed}'
    rollout=E.lc.apply_placement(problem,pl,run_id);actual=E.lc.current_live_placement(problem)
    if actual!=pl:raise RuntimeError('pilot actual placement mismatch')
    time.sleep(float(FULL['stage_e']['settle_seconds']))
    traffic=E.lc.configure_and_run_for_scenario(problem,pl,run_id,int(FULL['stage_e']['measurement_seconds']),sc)
    metrics=E.lc.aggregate_metrics(problem,pl,traffic)
    rec={'seed':int(seed),'multiplier':float(mult),'method':'B3_U_ONLY','scheduled_completion_fraction':float(metrics['scheduled_completion_fraction']),'attempted_requests':int(metrics['attempted_requests']),'expected_scheduled_requests':int(metrics['expected_scheduled_requests']),'rollout':rollout}
    dump(accepted,rec);return rec

def choose_lock(rows):
    by={}
    for m in CFG['candidate_multipliers']:
        rr=[x for x in rows if float(x['multiplier'])==float(m)]
        if len(rr)!=len(CFG['seeds']):raise RuntimeError(f'incomplete load pilot at multiplier {m}')
        by[float(m)]=float(np.mean([x['scheduled_completion_fraction'] for x in rr]))
    names=['moderate','high','near_capacity'];targets=CFG['targets'];mults=sorted(by)
    candidates=[]
    for a,b,c in itertools.combinations(mults,3):
        triple={'moderate':a,'high':b,'near_capacity':c};cost=0.0;midcost=0.0
        for name in names:
            y=by[triple[name]];band=targets[name];cost+=distance_to_band(y,band);mid=(float(band[0])+float(band[1]))/2;midcost+=abs(y-mid)
        candidates.append((cost,midcost,a,b,c,triple))
    if not candidates:raise RuntimeError('load pilot needs at least three multipliers')
    _,_,_,_,_,chosen=min(candidates,key=lambda z:z[:5])
    bands={name:{'multiplier':chosen[name],'mean_completion':by[chosen[name]],'target_band':targets[name],'in_target_band':bool(float(targets[name][0])<=by[chosen[name]]<=float(targets[name][1]))} for name in names}
    # The primary high-load endpoint is allowed to start only if the B3 pilot
    # actually generated a discriminating regime. Moderate/near are secondary
    # sensitivity regimes and are reported even if their target band is missed.
    if not bands['high']['in_target_band']:
        raise RuntimeError(f"B3-only pilot failed to find a high-load completion regime in {targets['high']}; observed={by}")
    return {'status':'FROZEN_PRE_RQ3','development_only':True,'method_used':'B3_U_ONLY','B5_evaluated':False,'multipliers':chosen,'selection_details':bands,'all_multiplier_mean_completion':{str(k):v for k,v in by.items()},'pilot_seeds':CFG['seeds'],'candidate_multipliers':CFG['candidate_multipliers']}

def run():
    E.setup_lc();info=E.cluster_info();E.image_probe(info);E.fingerprint_probe(info);E.lc.ensure_wireless_medium(info)
    selections=json.loads((OUT/'B3_PILOT_SELECTIONS.json').read_text()) if (OUT/'B3_PILOT_SELECTIONS.json').exists() else build_pilot_selections();rows=[]
    # Higher loads are tried last, preventing an overloaded cell from delaying all
    # lower-regime calibration if infrastructure recovery is needed.
    for mult in CFG['candidate_multipliers']:
        for seed in CFG['seeds']:rows.append(run_one(int(seed),float(mult),selections[str(seed)]['placement'],info))
    lock=choose_lock(rows);p=ROOT/FULL['stage_e']['load_lock_file'];dump(p,lock)
    import hashlib
    (p.with_suffix(p.suffix+'.sha256')).write_text(hashlib.sha256(p.read_bytes()).hexdigest()+'  '+p.name+'\n',encoding='utf-8')
    dump(OUT/'LOAD_PILOT_SUMMARY.json',lock);return lock

def main():
    ap=argparse.ArgumentParser();ap.add_argument('command',choices=['build-selections','run']);a=ap.parse_args()
    print(json.dumps(build_pilot_selections() if a.command=='build-selections' else run(),indent=2))
if __name__=='__main__':main()
