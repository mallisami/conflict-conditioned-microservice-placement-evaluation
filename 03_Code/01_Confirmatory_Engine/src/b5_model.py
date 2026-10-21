#!/usr/bin/env python3
"""Frozen B5 conflict-conditioned decision-aware ranking model.

B5 is developed only from the completed B4 campaign. Confirmatory runners load
an immutable model lock and never refit from confirmatory outcomes.
"""
from __future__ import annotations
import hashlib, json, math
from pathlib import Path
from typing import Any, Mapping

ROOT=Path(__file__).resolve().parents[1]
LOCK=ROOT/'b5_lock/B5_MODEL_LOCK.json'
LOCK_HASH=ROOT/'b5_lock/B5_MODEL_LOCK.sha256'
PAIR_REVERSES=(('rack-a>rack-b','rack-b>rack-a'),('rack-a>rack-c','rack-c>rack-a'),('rack-b>rack-c','rack-c>rack-b'))

# Full dictionaries are retained for auditability. Individual frozen models list
# the subset they actually consume in B5_MODEL_LOCK.json.
CONFLICT_FEATURES=(
    'intercept','u_max','u_weighted','pair_mass_weighted','log_pair_eff_weighted',
    'bidir_balance_weighted','stream_balance_weighted','u_pair_interaction','shared_fraction'
)
GLOBAL_FEATURES=(
    'intercept','u_max','global_pair_mass','log_neff_global','log_m_global',
    'u_global_pair_interaction'
)


def sha256_file(p:Path)->str:
    h=hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda:f.read(1<<20),b''): h.update(b)
    return h.hexdigest()


def load_lock()->dict[str,Any]:
    if not LOCK.exists() or not LOCK_HASH.exists():
        raise RuntimeError('B5 model lock missing; confirmatory science is blocked.')
    token=LOCK_HASH.read_text(encoding='utf-8').strip().split()[0]
    actual=sha256_file(LOCK)
    if token!=actual: raise RuntimeError('B5 model lock hash mismatch')
    obj=json.loads(LOCK.read_text(encoding='utf-8'))
    if obj.get('status')!='FROZEN_PRE_CONFIRMATION':
        raise RuntimeError('B5 lock is not FROZEN_PRE_CONFIRMATION')
    return obj


def _group_shape(pairs:Mapping[str,float])->dict[str,float]:
    vals={str(k):float(v) for k,v in pairs.items() if float(v)>0}
    total=sum(vals.values())
    if total<=0:
        return {'pair_mass':0.0,'pair_eff':0.0,'bidir_balance':0.0,'stream_balance':0.0,'n_eff':0.0,'m':0.0}
    probs={k:v/total for k,v in vals.items()}
    p=list(probs.values())
    hhi=sum(x*x for x in p)
    products=[p[i]*p[j] for i in range(len(p)) for j in range(i+1,len(p))]
    pair_sum=sum(products); pair_sq=sum(x*x for x in products)
    pair_eff=(pair_sum*pair_sum/pair_sq) if pair_sq>0 else 0.0
    # 2 * sum_{i<j} p_i p_j = 1-HHI. Higher values mean more load is
    # simultaneously distributed across multiple streams in a conflict group.
    pair_mass=2.0*pair_sum
    asym=sum(abs(probs.get(a,0.0)-probs.get(b,0.0)) for a,b in PAIR_REVERSES)
    return {
        'pair_mass':pair_mass,
        'pair_eff':pair_eff,
        'bidir_balance':max(0.0,1.0-asym),
        'stream_balance':max(0.0,1.0-max(p)),
        'n_eff':1.0/hhi if hhi>0 else 0.0,
        'm':float(len(p)),
    }


def state_group_detail(problem,placement,scenario)->tuple[dict[str,dict[str,Any]],float]:
    nodes=problem.node_by_id
    groups={g:{'pairs':{},'bits':0.0,'airtime':0.0,'budget':float(b)} for g,b in scenario.conflict_budgets_seconds.items()}
    total_cross=0.0
    for flow in problem.flows:
        sr=nodes[placement[flow.source_replica]].rack_id
        dr=nodes[placement[flow.destination_replica]].rack_id
        if sr==dr: continue
        bits=float(flow.bits_per_window); total_cross+=bits
        link=scenario.links[(sr,dr)]
        if not link.available or not link.conflict_group: continue
        rec=groups.setdefault(link.conflict_group,{'pairs':{},'bits':0.0,'airtime':0.0,'budget':float(scenario.conflict_budgets_seconds[link.conflict_group])})
        pair=f'{sr}>{dr}'; air=bits/float(link.goodput_bps)
        rec['pairs'][pair]=rec['pairs'].get(pair,0.0)+air
        rec['bits']+=bits; rec['airtime']+=air
    for rec in groups.values():
        rec['U']=rec['airtime']/rec['budget'] if rec['budget']>0 else 0.0
    return groups,total_cross


def conflict_feature_dict_from_groups(groups:Mapping[str,Mapping[str,Any]],total_cross:float)->dict[str,float]:
    den=float(total_cross) if float(total_cross)>0 else max(1.0,sum(float(g.get('bits',0.0)) for g in groups.values()))
    weighted=[]
    for g in groups.values():
        bits=float(g.get('bits',0.0)); w=bits/den
        sh=_group_shape(g.get('pairs',{})); u=float(g.get('U',0.0))
        weighted.append((w,u,sh))
    u_max=max((u for _,u,_ in weighted),default=0.0)
    u_w=sum(w*u for w,u,_ in weighted)
    pair_mass=sum(w*s['pair_mass'] for w,_,s in weighted)
    log_pair_eff=sum(w*math.log1p(s['pair_eff']) for w,_,s in weighted)
    bidir=sum(w*s['bidir_balance'] for w,_,s in weighted)
    stream_bal=sum(w*s['stream_balance'] for w,_,s in weighted)
    shared=sum(w for w,_,_ in weighted)
    return {
        'intercept':1.0,
        'u_max':u_max,
        'u_weighted':u_w,
        'pair_mass_weighted':pair_mass,
        'log_pair_eff_weighted':log_pair_eff,
        'bidir_balance_weighted':bidir,
        'stream_balance_weighted':stream_bal,
        'u_pair_interaction':u_max*pair_mass,
        'shared_fraction':shared,
    }


def global_feature_dict_from_groups(groups:Mapping[str,Mapping[str,Any]],total_cross:float)->dict[str,float]:
    vals=[]; u_max=0.0
    for g in groups.values():
        u_max=max(u_max,float(g.get('U',0.0)))
        vals.extend(float(v) for v in g.get('pairs',{}).values() if float(v)>0)
    total=sum(vals)
    if total>0:
        p=[v/total for v in vals]; hhi=sum(x*x for x in p)
        neff=1.0/hhi; m=len(p); pair_mass=max(0.0,1.0-hhi)
    else:
        neff=0.0; m=0; pair_mass=0.0
    return {
        'intercept':1.0,
        'u_max':u_max,
        'global_pair_mass':pair_mass,
        'log_neff_global':math.log(max(1.0,neff)),
        'log_m_global':math.log(max(1,m)),
        'u_global_pair_interaction':u_max*pair_mass,
    }


def feature_dict(problem,placement,scenario,feature_set='conflict')->dict[str,float]:
    groups,total=state_group_detail(problem,placement,scenario)
    if feature_set=='conflict': return conflict_feature_dict_from_groups(groups,total)
    if feature_set=='global': return global_feature_dict_from_groups(groups,total)
    raise ValueError(feature_set)


def vector_for_model(model:Mapping[str,Any],features:Mapping[str,float])->list[float]:
    names=list(model['feature_names'])
    missing=[k for k in names if k not in features]
    if missing: raise RuntimeError(f'B5 feature(s) missing: {missing}')
    return [float(features[k]) for k in names]


def predict_vector(model:Mapping[str,Any],x:list[float])->float:
    b=[float(v) for v in model['coefficients']]
    if len(b)!=len(x): raise RuntimeError('B5 coefficient/feature length mismatch')
    return min(1.0,max(0.0,sum(a*c for a,c in zip(b,x))))


def state_predictions(problem,placement,lock:Mapping[str,Any]|None=None)->dict[str,dict[str,float]]:
    lock=lock or load_lock(); out={}
    for sc in problem.scenarios:
        cache={}
        out[sc.scenario_id]={}
        for name,model in lock['models'].items():
            fs=model['feature_set']
            if fs not in cache: cache[fs]=feature_dict(problem,placement,sc,fs)
            x=vector_for_model(model,cache[fs])
            out[sc.scenario_id][name]=predict_vector(model,x)
    return out


def placement_scores(problem,placement,lock:Mapping[str,Any]|None=None)->tuple[dict[str,float],dict[str,Any]]:
    lock=lock or load_lock(); state=state_predictions(problem,placement,lock)
    scores={k:0.0 for k in lock['models']}
    for sc in problem.scenarios:
        for k in scores: scores[k]+=float(sc.weight)*float(state[sc.scenario_id][k])
    return scores,{'state_predictions':state}


def near_margin(lock:Mapping[str,Any]|None=None)->float:
    return float((lock or load_lock())['selection']['near_margin'])
