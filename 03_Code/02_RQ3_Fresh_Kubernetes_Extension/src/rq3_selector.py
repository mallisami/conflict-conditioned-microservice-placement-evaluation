#!/usr/bin/env python3
from __future__ import annotations
import hashlib,json,math,sys,time
from pathlib import Path
from typing import Any

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'));sys.path.insert(0,str(ROOT/'deps'))
import run_stage_c as C
import b5_model as B5

EPS=1e-12
B3_FILE=ROOT/'b3_lock/frozen_coefficients.json'


def sha_file(p:Path)->str:
    return hashlib.sha256(p.read_bytes()).hexdigest()

def _pkey(pl): return C.pkey(pl)

def solve_seed(seed:int)->dict[str,Any]:
    t0=time.time(); coeffs=json.loads(B3_FILE.read_text()); p,cal=C.build_scaled_problem('n8',int(seed))
    if p is None:return {'size':'n8','seed':int(seed),'valid':False,**cal,'elapsed_seconds':time.time()-t0}
    b5_lock=B5.load_lock(); delta=B5.near_margin(b5_lock)
    h=hashlib.sha256(); n_adm=0
    strict_b3=None; strict_b5=None
    b3_min=float('inf');b5_min=float('inf');b3_near=[];b5_near=[]
    for pl,mv in C.candidates(p,p.max_relocations or 0):
        if not C.cluster_ok(p,pl):continue
        ev=C.evaluate_placement(p,pl,C.RISK)
        if not ev.feasible:continue
        n_adm+=1;key=_pkey(pl);h.update((json.dumps(key,separators=(',',':'))+'\n').encode())
        cs,detail=C.calibrated_scores(p,pl,coeffs);b5s,b5detail=B5.placement_scores(p,pl,b5_lock)
        b3=float(cs['B3_U_ONLY']); b5=float(b5s['B5_CONFLICT_RANK']); jsa=float(ev.total_objective)
        common={'moves':int(mv),'placement_key':list(key),'mape_objective':jsa,'cross_rack_bits':C.cross_bits(p,pl),'worst_u':C.worst_util(p,ev),'contention':detail,'b5':b5detail}
        strict_b3=C.choose(strict_b3,b3,mv,key,pl,{**common,'rank_score':b3})
        strict_b5=C.choose(strict_b5,b5,mv,key,pl,{**common,'rank_score':b5})
        if b3 < b3_min:
            b3_min=b3;b3_near=[x for x in b3_near if x[0]<=b3+delta+EPS]
        if b3<=b3_min+delta+EPS:b3_near.append((b3,jsa,int(mv),key,dict(pl),{**common,'rank_score':b3}))
        if b5 < b5_min:
            b5_min=b5;b5_near=[x for x in b5_near if x[0]<=b5+delta+EPS]
        if b5<=b5_min+delta+EPS:b5_near.append((b5,jsa,int(mv),key,dict(pl),{**common,'rank_score':b5}))
    if n_adm==0:return {'size':'n8','seed':int(seed),'valid':True,'n_admissible':0,'x_adm_sha256':h.hexdigest(),'no_admissible_placement':True,**cal,'elapsed_seconds':time.time()-t0}
    b3elig=[x for x in b3_near if x[0]<=b3_min+delta+EPS];b5elig=[x for x in b5_near if x[0]<=b5_min+delta+EPS]
    b3s=min(b3elig,key=lambda x:(x[1],x[2],x[3]));b5c=min(b5elig,key=lambda x:(x[1],x[2],x[3]))
    def strict_record(rec,name):
        return {'placement':rec['placement'],'score':float(rec['order'][0]),'moves':int(rec['order'][1]),'placement_key':list(rec['order'][2]),**rec['meta'],'selection_rule':name}
    def stab_record(x,n,minscore,name):
        return {'placement':x[4],'score':float(x[0]),'moves':int(x[2]),'placement_key':list(x[3]),**x[5],'strict_min_score':float(minscore),'near_margin':float(delta),'near_candidate_count':int(n),'b1_tiebreak_objective':float(x[1]),'selection_rule':name}
    selections={
      'B3_STRICT':strict_record(strict_b3,'strict minimum B3 score; moves; key'),
      'B3_STABILIZED':stab_record(b3s,len(b3elig),b3_min,'B3 within min+frozen B5 delta; JSA; moves; key'),
      'B5_NOTIE':strict_record(strict_b5,'strict minimum B5 score; moves; key'),
      'B5_COMPLETE':stab_record(b5c,len(b5elig),b5_min,'B5 within min+frozen delta; JSA; moves; key'),
    }
    for name,r in selections.items():
        ev=C.evaluate_placement(p,r['placement'],C.RISK)
        if not ev.feasible:raise RuntimeError(f'{seed}/{name}: selected placement failed feasibility re-evaluation')
    return {'size':'n8','seed':int(seed),'valid':True,'no_admissible_placement':False,'n_admissible':n_adm,'x_adm_sha256':h.hexdigest(),'b3_coefficient_sha256':sha_file(B3_FILE),'b5_lock_sha256':B5.sha256_file(B5.LOCK),'near_margin':float(delta),'selections':selections,**cal,'elapsed_seconds':time.time()-t0}

if __name__=='__main__':
    import argparse
    ap=argparse.ArgumentParser();ap.add_argument('seed',type=int);a=ap.parse_args();print(json.dumps(solve_seed(a.seed),indent=2,sort_keys=True))
