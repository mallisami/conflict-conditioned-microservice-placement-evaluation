#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, itertools, json, math, os, sys, time
from dataclasses import replace
from multiprocessing import Pool
from pathlib import Path
try:
    import resource
except ImportError:
    resource=None
from typing import Any

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'deps'))
from mape_cap_bplus.generators import generate_problem
from mape_cap_bplus.models import RelocationCost, RiskConfig, LinkState, Scenario
from mape_cap_bplus.objective import evaluate_placement
import b5_model as B5

CFG=json.loads((ROOT/'config/stage_c.json').read_text())
FULL=json.loads((ROOT/'config/full_campaign.json').read_text())
VM_CFG=json.loads((ROOT/'config/vm_execution.json').read_text()) if (ROOT/'config/vm_execution.json').exists() else None
STATE_CSV=ROOT/'deps/ns3_simulation_backed_traces.csv'
RISK=RiskConfig(cvar_quantile=0.8,cvar_weight=1.5,relocation_weight=1.0,slo_slack_weight=1000.0)
EPS=1e-12
TINY=1e-6
OUT=ROOT/'stage_c_results'
PAIR_ORDER=['rack-a>rack-b','rack-b>rack-a','rack-a>rack-c','rack-c>rack-a','rack-b>rack-c','rack-c>rack-b']
SIZES=[(x['label'],int(x['replicas']),int(x['nodes_per_rack']),int(x['move_budget']),range(int(x['seed_start']),int(x['seed_end'])+1)) for x in CFG['sizes']]
P1_SEEDS={6:range(11001,11051),7:range(22001,22051),8:range(33001,33051)}
P1_TARGETS=(1.00,1.10,1.25,1.50)
P1_EXPECTED={1.00:7,1.10:12,1.25:24,1.50:35}


def sha_bytes(b:bytes)->str:return hashlib.sha256(b).hexdigest()
def sha_file(p:Path)->str:return sha_bytes(p.read_bytes())
def dump(p:Path,obj:Any):
    p.parent.mkdir(parents=True,exist_ok=True); tmp=p.with_suffix(p.suffix+'.tmp')
    tmp.write_text(json.dumps(obj,indent=2,sort_keys=True),encoding='utf-8'); os.replace(tmp,p)

def load_states():
    import csv
    rows=list(csv.DictReader(STATE_CSV.open(newline='',encoding='utf-8')))
    wanted=['conflict-dense','partial-blockage','persistent-degradation']
    by={k:[] for k in wanted}
    for r in rows:
        if r['scenario_id'] in by: by[r['scenario_id']].append(r)
    sc=[]
    for sid in wanted:
        rr=by[sid]
        if not rr: raise RuntimeError(f'missing state {sid}')
        links={}; budgets={}
        for r in rr:
            cg=r['conflict_group'].strip() or None
            links[(r['source_rack'],r['destination_rack'])]=LinkState(
                r['source_rack'],r['destination_rack'],float(r['latency_ms']),float(r['goodput_bps']),
                r['available'].lower()=='true',r['path_id'],cg,r['provenance'])
            if cg and r['budget_seconds'].strip(): budgets[cg]=float(r['budget_seconds'])
        sc.append(Scenario(sid,float(rr[0]['weight']),links,budgets,regime_duration_seconds=float(rr[0]['regime_duration_seconds']),metadata={'source':'paper1-frozen-state-library'}))
    tot=sum(s.weight for s in sc)
    return tuple(replace(s,weight=s.weight/tot) for s in sc)
PLAN=load_states()

def base_problem(nrep,npr,mmax,seed):
    p=generate_problem(replica_count=nrep,rack_count=3,nodes_per_rack=npr,scenario_count=3,seed=seed,decision_window_seconds=60.0)
    rack_map={'rack-0':'rack-a','rack-1':'rack-b','rack-2':'rack-c'}
    nodes=tuple(replace(n,rack_id=rack_map[n.rack_id]) for n in p.nodes)
    costs={r.replica_id:RelocationCost(r.replica_id,4062.0,4.062,690.0,'frozen-kind-pilot-mean') for r in p.replicas}
    return replace(p,nodes=nodes,scenarios=PLAN,relocation_costs=costs,max_relocations=mmax)

def scale_problem(p,factor):
    return replace(p,flows=tuple(replace(f,bits_per_window=f.bits_per_window*factor) for f in p.flows),metadata={**p.metadata,'paper2_payload_scale':factor})

def cluster_ok(p,pl):
    nodes=p.node_by_id; reps=p.replica_by_id; cpu={n:0.0 for n in nodes}; mem={n:0.0 for n in nodes}; groups={n:set() for n in nodes}; mv=0
    for rid,nid in pl.items():
        r=reps[rid]
        if nid not in p.allowed_nodes_for(rid): return False
        cpu[nid]+=r.cpu_request; mem[nid]+=r.memory_request_mb
        if r.anti_affinity_group:
            if r.anti_affinity_group in groups[nid]: return False
            groups[nid].add(r.anti_affinity_group)
        mv+=int(p.current_placement.get(rid)!=nid)
    if p.max_relocations is not None and mv>p.max_relocations:return False
    return all(cpu[n]<=nodes[n].cpu_capacity+EPS and mem[n]<=nodes[n].memory_capacity_mb+EPS for n in nodes)

def candidates(p,mmax):
    reps=[r.replica_id for r in p.replicas]; cur=dict(p.current_placement)
    alt={r:[n for n in p.allowed_nodes_for(r) if n!=cur[r]] for r in reps}
    for m in range(mmax+1):
        for sub in itertools.combinations(reps,m):
            choices=[alt[r] for r in sub]
            if any(not x for x in choices): continue
            for vals in itertools.product(*choices):
                pl=dict(cur); pl.update(zip(sub,vals)); yield pl,m

def worst_util(p,ev):
    vals=[]
    for sc in p.scenarios:
        am=ev.scenario_airtime_by_group.get(sc.scenario_id,{})
        for g,b in sc.conflict_budgets_seconds.items():
            if b>0: vals.append(float(am.get(g,0.0))/float(b))
    return max(vals,default=0.0)

def cross_bits(p,pl):
    nodes=p.node_by_id
    return sum(float(f.bits_per_window) for f in p.flows if nodes[pl[f.source_replica]].rack_id!=nodes[pl[f.destination_replica]].rack_id)

def move_count(p,pl): return sum(int(p.current_placement.get(r)!=n) for r,n in pl.items())
def pkey(pl): return tuple(sorted((str(k),str(v)) for k,v in pl.items()))

def coeff_run_root(stage_a_root:Path|None=None):
    if stage_a_root: return stage_a_root
    cur=ROOT/'stage_a_results/CURRENT_RUN.txt'
    if not cur.exists(): raise RuntimeError('Stage-A CURRENT_RUN missing')
    return Path(cur.read_text().strip())

def load_coeffs(stage_a_root:Path|None=None):
    root=coeff_run_root(stage_a_root); p=root/'frozen_coefficients.json'; h=root/'frozen_coefficients.sha256'
    if not p.exists() or not h.exists(): raise RuntimeError('Stage-A frozen coefficients missing')
    tok=h.read_text().strip().split()[0]
    if tok!=sha_file(p): raise RuntimeError('Stage-A coefficient freeze hash invalid')
    return json.loads(p.read_text()),root

def design_u(U): return [1.0,U,U*U]
def design_neff(U,n):
    z=math.log(max(1.0,n)); return [1.0,U,U*U,z,U*z]
def design_full(U,n,m):
    z=math.log(max(1.0,n)); q=math.log(max(1,m)); return [1.0,U,U*U,z,U*z,q,U*q]
def pred(coef,x): return min(1.0,max(0.0,sum(float(a)*float(b) for a,b in zip(coef,x))))

def group_features(p,pl,sc):
    nodes=p.node_by_id
    groups={g:{'pairs':{},'bits':0.0,'airtime':0.0} for g in sc.conflict_budgets_seconds}
    total_cross=0.0
    for f in p.flows:
        sr=nodes[pl[f.source_replica]].rack_id; dr=nodes[pl[f.destination_replica]].rack_id
        if sr==dr: continue
        bits=float(f.bits_per_window); total_cross+=bits
        link=sc.links[(sr,dr)]
        if not link.available: continue
        if not link.conflict_group: continue
        g=link.conflict_group
        rec=groups.setdefault(g,{'pairs':{},'bits':0.0,'airtime':0.0})
        pair=f'{sr}>{dr}'; air=bits/float(link.goodput_bps)
        rec['pairs'][pair]=rec['pairs'].get(pair,0.0)+air
        rec['bits']+=bits; rec['airtime']+=air
    out={}
    for g,budget in sc.conflict_budgets_seconds.items():
        rec=groups.get(g,{'pairs':{},'bits':0.0,'airtime':0.0})
        vals=[v for v in rec['pairs'].values() if v>0]
        if vals:
            total=sum(vals); probs=[v/total for v in vals]; hhi=sum(x*x for x in probs); neff=1.0/hhi; m=len(vals)
        else: hhi=0.0; neff=0.0; m=0
        out[g]={'U':rec['airtime']/float(budget) if budget>0 else 0.0,'bits':rec['bits'],'m':m,'n_eff':neff,'hhi':hhi,'resource_share':float(budget)/float(p.decision_window_seconds),'pairs':rec['pairs']}
    return out,total_cross

def calibrated_scores(p,pl,coeffs):
    scores={'B3_U_ONLY':0.0,'A1_U_NEFF':0.0,'B4_FULL_SHAPE':0.0}; detail={}
    for sc in p.scenarios:
        feats,total_cross=group_features(p,pl,sc); lost={k:0.0 for k in scores}
        for g,r in feats.items():
            if r['bits']<=0: continue
            share=str(float(r['resource_share']))
            if share not in coeffs['fits']:
                # tolerate JSON key formatting 0.5 vs 0.50
                match=[k for k in coeffs['fits'] if math.isclose(float(k),float(r['resource_share']),abs_tol=1e-12)]
                if not match: raise RuntimeError(f'no calibration stratum for share {r["resource_share"]}')
                share=match[0]
            fit=coeffs['fits'][share]
            U=float(r['U']); n=float(r['n_eff'] or 1.0); m=int(r['m'] or 1)
            l3=pred(fit['B3_U_only'],design_u(U)); la=pred(fit['A1_U_Neff'],design_neff(U,n)); l4=pred(fit['B4_full_shape'],design_full(U,n,m))
            lost['B3_U_ONLY']+=r['bits']*l3; lost['A1_U_NEFF']+=r['bits']*la; lost['B4_FULL_SHAPE']+=r['bits']*l4
            r.update({'pred_B3':l3,'pred_A1':la,'pred_B4':l4})
        denom=total_cross
        scen={k:(lost[k]/denom if denom>0 else 0.0) for k in scores}
        for k in scores:scores[k]+=float(sc.weight)*scen[k]
        detail[sc.scenario_id]={'weight':float(sc.weight),'total_cross_bits':total_cross,'groups':feats,'predicted_loss_fraction':scen}
    return scores,detail

def choose(best,score,moves,key,pl,meta):
    rec=(float(score),int(moves),key)
    if best is None or rec<best['order']:
        return {'order':rec,'placement':dict(pl),'meta':meta}
    return best

def build_scaled_problem(label,seed):
    cfg=next(x for x in SIZES if x[0]==label); _,nrep,npr,mmax,_=cfg
    p=base_problem(nrep,npr,mmax,seed); tiny=scale_problem(p,TINY)
    cur=dict(p.current_placement)
    if not cluster_ok(p,cur): return None,{'invalid_reason':'current_cluster_infeasible'}
    ev=evaluate_placement(tiny,cur,RISK)
    if not ev.feasible: return None,{'invalid_reason':'current_non_airtime_or_availability_infeasible','reasons':ev.reasons}
    unit=worst_util(tiny,ev)/TINY
    if not math.isfinite(unit) or unit<=0:return None,{'invalid_reason':'zero_or_invalid_current_utilization'}
    factor=float(CFG['target_current_worst_utilization'])/unit
    return scale_problem(p,factor),{'unit_current_utilization':unit,'payload_scale':factor,'target':float(CFG['target_current_worst_utilization'])}

def solve_graph(job):
    label,seed,coef_path=job; t0=time.time(); ranking_seconds=0.0
    coeffs=json.loads(Path(coef_path).read_text()); p,cal=build_scaled_problem(label,seed)
    if p is None:return {'size':label,'seed':seed,'valid':False,**cal,'elapsed_seconds':time.time()-t0}
    legacy=['B0_AFFINITY_ADMISSION','B1_MAPE_CAP_WS','B2_MAX_HEADROOM','B3_U_ONLY','A1_U_NEFF','B4_FULL_SHAPE','B5_NOTIE']
    best={k:None for k in legacy}
    b5_models=['B5_CONFLICT_RANK','B5_MAE_ONLY','B5_GLOBAL_RANK']
    near_records={k:[] for k in b5_models}; minima={k:float('inf') for k in b5_models}
    h=hashlib.sha256(); n_adm=0; b5_lock=B5.load_lock(); b5_delta=B5.near_margin(b5_lock)
    for pl,mv in candidates(p,p.max_relocations or 0):
        if not cluster_ok(p,pl): continue
        ev=evaluate_placement(p,pl,RISK)
        if not ev.feasible: continue
        n_adm+=1; key=pkey(pl); h.update((json.dumps(key,separators=(',',':'))+'\n').encode())
        rt=time.perf_counter(); xb=cross_bits(p,pl); wu=worst_util(p,ev); cs,detail=calibrated_scores(p,pl,coeffs); b5s,b5detail=B5.placement_scores(p,pl,b5_lock)
        common={'moves':mv,'cross_rack_bits':xb,'worst_u':wu,'mape_objective':float(ev.total_objective),'contention':detail,'b5':b5detail}
        best['B0_AFFINITY_ADMISSION']=choose(best['B0_AFFINITY_ADMISSION'],xb,mv,key,pl,common)
        best['B1_MAPE_CAP_WS']=choose(best['B1_MAPE_CAP_WS'],float(ev.total_objective),mv,key,pl,common)
        best['B2_MAX_HEADROOM']=choose(best['B2_MAX_HEADROOM'],wu,mv,key,pl,common)
        best['B3_U_ONLY']=choose(best['B3_U_ONLY'],cs['B3_U_ONLY'],mv,key,pl,{**common,'rank_score':cs['B3_U_ONLY']})
        best['A1_U_NEFF']=choose(best['A1_U_NEFF'],cs['A1_U_NEFF'],mv,key,pl,{**common,'rank_score':cs['A1_U_NEFF']})
        best['B4_FULL_SHAPE']=choose(best['B4_FULL_SHAPE'],cs['B4_FULL_SHAPE'],mv,key,pl,{**common,'rank_score':cs['B4_FULL_SHAPE']})
        # B5_NOTIE is the strict top-1 ablation of the primary score.
        best['B5_NOTIE']=choose(best['B5_NOTIE'],b5s['B5_CONFLICT_RANK'],mv,key,pl,{**common,'rank_score':b5s['B5_CONFLICT_RANK']})
        # Primary B5 plus feature/training ablations use the identical frozen
        # uncertainty-aware near margin and B1 tie-break so each ablation changes
        # only the intended component.
        for model in b5_models:
            score=float(b5s[model])
            if score < minima[model]:
                minima[model]=score
                near_records[model]=[x for x in near_records[model] if x[0] <= score+b5_delta+EPS]
            if score <= minima[model]+b5_delta+EPS:
                near_records[model].append((score,float(ev.total_objective),int(mv),key,dict(pl),{**common,'rank_score':score}))
        ranking_seconds += time.perf_counter()-rt
    if n_adm==0:return {'size':label,'seed':seed,'valid':True,'n_admissible':0,'x_adm_sha256':h.hexdigest(),'no_admissible_placement':True,**cal,'elapsed_seconds':time.time()-t0}
    for model in b5_models:
        eligible=[x for x in near_records[model] if x[0] <= minima[model]+b5_delta+EPS]
        if not eligible: raise RuntimeError(f'{label}/{seed}/{model}: near set unexpectedly empty')
        bx=min(eligible,key=lambda x:(x[1],x[2],x[3]))
        best[model]={'order':(bx[0],bx[2],bx[3]),'placement':bx[4],'meta':{**bx[5],'b1_tiebreak_objective':bx[1],'near_margin':b5_delta,'near_candidate_count':len(eligible),'strict_min_score':minima[model]}}
    selections={}
    for name,b in best.items():
        pl=b['placement']; ev=evaluate_placement(p,pl,RISK)
        if not ev.feasible: raise RuntimeError(f'{label}/{seed}/{name}: selected placement failed independent feasibility re-evaluation')
        selections[name]={'placement':pl,'score':b['order'][0],'moves':b['order'][1],'placement_key':list(b['order'][2]),**b['meta']}
    elapsed=time.time()-t0; peak_rss_mb=None
    if resource is not None:
        v=float(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss); peak_rss_mb=v/1024.0 if sys.platform!='darwin' else v/(1024.0*1024.0)
    return {'size':label,'seed':seed,'valid':True,'n_admissible':n_adm,'x_adm_sha256':h.hexdigest(),'no_admissible_placement':False,
            'coefficient_sha256':sha_file(Path(coef_path)),'b5_lock_sha256':B5.sha256_file(B5.LOCK),'selections':selections,**cal,'elapsed_seconds':elapsed,
            'ranking_score_seconds':ranking_seconds,'enumeration_admission_and_bookkeeping_seconds':max(0.0,elapsed-ranking_seconds),'peak_rss_mb':peak_rss_mb}

def reproduction_gate_one(nrep,seed,target):
    p=base_problem(nrep,1,2,seed); tiny=scale_problem(p,TINY); cur=dict(p.current_placement)
    if not cluster_ok(p,cur):return None
    ev=evaluate_placement(tiny,cur,RISK)
    if not ev.feasible:return None
    unit=worst_util(tiny,ev)/TINY
    if unit<=0:return None
    factor=float(target)/unit; sp=scale_problem(p,factor)
    aff=None; admissible_exists=False
    for pl,mv in candidates(sp,sp.max_relocations or 0):
        if not cluster_ok(sp,pl):continue
        e=evaluate_placement(sp,pl,RISK)
        # affinity selection is over cluster-feasible placements even if airtime-inadmissible; evaluate tiny to screen non-airtime invalidity
        et=evaluate_placement(scale_problem(p,TINY),pl,RISK)
        if not et.feasible:continue
        xb=cross_bits(sp,pl); key=pkey(pl); rec=(xb,mv,key,pl)
        if aff is None or rec[:3]<aff[:3]:aff=rec
        if e.feasible: admissible_exists=True
    if aff is None:return None
    ae=evaluate_placement(sp,aff[3],RISK)
    return (not ae.feasible) and admissible_exists

def reproduction_gate():
    existing=OUT/'REPRODUCTION_GATE.json'
    if existing.exists():
        d=json.loads(existing.read_text())
        if d.get('passed') and {float(k):int(v) for k,v in d.get('counts',{}).items()}==P1_EXPECTED:
            return {float(k):int(v) for k,v in d['counts'].items()}
    counts={t:0 for t in P1_TARGETS}
    for nrep,seeds in P1_SEEDS.items():
        for seed in seeds:
            for t in P1_TARGETS:
                x=reproduction_gate_one(nrep,seed,t)
                if x: counts[t]+=1
    if counts!=P1_EXPECTED: raise RuntimeError(f'enumerator reproduction gate failed: {counts} != {P1_EXPECTED}')
    dump(OUT/'REPRODUCTION_GATE.json',{'counts':counts,'expected':P1_EXPECTED,'passed':True,'role':'implementation verification only; not Paper-II evidence'})
    return counts

def vm_allowed_seeds(vm_role):
    if not vm_role:
        return None
    if VM_CFG is None:
        raise RuntimeError('vm_execution.json missing but --vm-role was supplied')
    part=VM_CFG.get('random_graph_partition',{}).get(vm_role)
    if not part:
        raise RuntimeError(f'role {vm_role} has no random Stage-C shard')
    allowed=set()
    for label,bounds in part.items():
        lo,hi=map(int,bounds); allowed.update((label,x) for x in range(lo,hi+1))
    return allowed

def run(stage_a_root=None,workers=None,smoke=False,vm_role=None):
    coeffs,aroot=load_coeffs(stage_a_root); cp=aroot/'frozen_coefficients.json'
    OUT.mkdir(parents=True,exist_ok=True); (OUT/'graphs').mkdir(exist_ok=True)
    if not smoke and not (OUT/'REPRODUCTION_GATE.json').exists(): reproduction_gate()
    jobs=[]
    allowed=vm_allowed_seeds(vm_role)
    for label,nrep,npr,mmax,seeds in SIZES:
        ss=list(seeds)[:1] if smoke else list(seeds)
        for seed in ss:
            if allowed is not None and (label,int(seed)) not in allowed: continue
            dest=OUT/'graphs'/f'{label}-{seed}.json'
            if not dest.exists(): jobs.append((label,seed,str(cp)))
    w=int(workers or FULL.get('stage_c_workers',3))
    if w<=1:
        for j in jobs: dump(OUT/'graphs'/f'{j[0]}-{j[1]}.json',solve_graph(j))
    else:
        with Pool(w) as pool:
            for res in pool.imap_unordered(solve_graph,jobs): dump(OUT/'graphs'/f"{res['size']}-{res['seed']}.json",res)
    return analyze(smoke=smoke)

def analyze(smoke=False):
    rows=[json.loads(p.read_text()) for p in sorted((OUT/'graphs').glob('*.json'))]
    if not rows: raise RuntimeError('no Stage-C graph results')
    valid=[r for r in rows if r.get('valid') and not r.get('no_admissible_placement')]
    methods=list(FULL.get('confirmatory_methods',[]))
    summ={'graphs_present':len(rows),'valid_with_admissible_set':len(valid),'invalid_or_empty':len(rows)-len(valid),'by_size':{},'pairwise_selection_difference':{}}
    for label,*_ in SIZES:
        rr=[r for r in rows if r['size']==label]
        summ['by_size'][label]={'scheduled':len(rr),'valid':sum(x.get('valid') and not x.get('no_admissible_placement') for x in rr),'median_n_admissible':None}
        vals=sorted(x['n_admissible'] for x in rr if x.get('valid') and x.get('n_admissible') is not None)
        if vals:summ['by_size'][label]['median_n_admissible']=vals[len(vals)//2]
    pairs=[('B5_CONFLICT_RANK','B3_U_ONLY'),('B5_CONFLICT_RANK','B4_FULL_SHAPE'),('B5_CONFLICT_RANK','B1_MAPE_CAP_WS'),
           ('B5_CONFLICT_RANK','B5_MAE_ONLY'),('B5_CONFLICT_RANK','B5_GLOBAL_RANK'),('B5_CONFLICT_RANK','B5_NOTIE')]
    for a,b in pairs:
        diff=sum(r['selections'][a]['placement']!=r['selections'][b]['placement'] for r in valid)
        summ['pairwise_selection_difference'][f'{a}_vs_{b}']={'different':diff,'denominator':len(valid)}
    dump(OUT/'STAGE_C_SUMMARY.json',summ); return summ

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('command',choices=['gate','smoke','run','analyze']); ap.add_argument('--workers',type=int); ap.add_argument('--stage-a-root',type=Path); ap.add_argument('--vm-role',choices=['vm1','vm2'])
    a=ap.parse_args()
    if a.command=='gate':print(json.dumps(reproduction_gate(),indent=2));return
    if a.command=='smoke':print(json.dumps(run(a.stage_a_root,a.workers,True,a.vm_role),indent=2));return
    if a.command=='run':print(json.dumps(run(a.stage_a_root,a.workers,False,a.vm_role),indent=2));return
    print(json.dumps(analyze(),indent=2))
if __name__=='__main__':main()
