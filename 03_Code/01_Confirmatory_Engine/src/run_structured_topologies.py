#!/usr/bin/env python3
from __future__ import annotations
import argparse,csv,hashlib,json,math,os,random,sys,time
try:
    import resource
except ImportError:
    resource=None
from dataclasses import replace
from pathlib import Path
from typing import Any
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'));sys.path.insert(0,str(ROOT/'deps'))
import run_stage_a as A
import run_stage_c as C
import run_stage_d as D
from mape_cap_bplus.models import FlowSpec
from mape_cap_bplus.objective import evaluate_placement
import b5_model as B5

CFG=json.loads((ROOT/'config/structured_topologies.json').read_text())
FULL=json.loads((ROOT/'config/full_campaign.json').read_text())
OUT=ROOT/'structured_topology_results'
METHODS=D.METHODS
EPS=1e-12

def dump(p:Path,o:Any):
    p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(json.dumps(o,indent=2,sort_keys=True),encoding='utf-8')

def psha(o):
    return hashlib.sha256(json.dumps(o,sort_keys=True,separators=(',',':')).encode()).hexdigest()

def seed_range(topology,label):
    a,b=CFG['seed_blocks'][topology][label]
    return range(int(a),int(b)+1)

def grid_dims(n):
    for r in range(int(math.sqrt(n)),0,-1):
        if n%r==0:return r,n//r
    return 1,n

def edges(topology,n):
    if topology=='pipeline':
        return [(i,i+1) for i in range(n-1)]
    if topology=='fanout_fanin':
        if n<3:raise ValueError('fanout_fanin requires n>=3')
        root=0;sink=n-1
        return [(root,i) for i in range(1,n-1)]+[(i,sink) for i in range(1,n-1)]
    if topology=='hub_spoke':
        return [(0,i) for i in range(1,n)]+[(i,0) for i in range(1,n)]
    if topology=='mesh':
        rows,cols=grid_dims(n)
        e=[]
        def idx(r,c):return r*cols+c
        for r in range(rows):
            for c in range(cols):
                u=idx(r,c)
                if c+1<cols:
                    v=idx(r,c+1);e.extend([(u,v),(v,u)])
                if r+1<rows:
                    v=idx(r+1,c);e.extend([(u,v),(v,u)])
        return e
    raise ValueError(topology)

def structured_problem(topology,label,seed):
    spec=next(x for x in CFG['sizes'] if x['label']==label)
    p=C.base_problem(int(spec['replicas']),int(spec['nodes_per_rack']),int(CFG['move_budget']),int(seed))
    reps=sorted(r.replica_id for r in p.replicas)
    rr=random.Random(int(seed)*1009 + {'pipeline':1,'fanout_fanin':2,'hub_spoke':3,'mesh':4}[topology])
    flows=[]
    for j,(a,b) in enumerate(edges(topology,len(reps))):
        jitter=rr.uniform(1-float(CFG['traffic_jitter_fraction']),1+float(CFG['traffic_jitter_fraction']))
        flows.append(FlowSpec(
            flow_id=f'{topology}-f{j:03d}',
            source_replica=reps[a],
            destination_replica=reps[b],
            requests_per_window=1000.0*jitter,
            bits_per_window=100_000_000.0*jitter,
            criticality=1.0,
            max_expected_latency_ms=None
        ))
    p=replace(p,flows=tuple(flows),max_relocations=int(CFG['move_budget']),
              metadata={**p.metadata,'paper2_structured_topology':topology,'paper2_structured_seed':int(seed)})
    cur=dict(p.current_placement)
    if not C.cluster_ok(p,cur):
        return None,{'invalid_reason':'current_cluster_infeasible'}
    tiny=C.scale_problem(p,C.TINY)
    ev=evaluate_placement(tiny,cur,C.RISK)
    if not ev.feasible:
        return None,{'invalid_reason':'current_non_airtime_or_availability_infeasible','reasons':ev.reasons}
    unit=C.worst_util(tiny,ev)/C.TINY
    if not math.isfinite(unit) or unit<=0:
        return None,{'invalid_reason':'zero_or_invalid_current_utilization'}
    factor=float(CFG['target_current_worst_utilization'])/unit
    return C.scale_problem(p,factor),{'unit_current_utilization':unit,'payload_scale':factor}

def solve(topology,label,seed,coeffs):
    t0=time.time(); ranking_seconds=0.0; p,cal=structured_problem(topology,label,seed)
    if p is None:
        return {'topology':topology,'size':label,'seed':seed,'valid':False,**cal,'elapsed_seconds':time.time()-t0}
    h=hashlib.sha256(); n_adm=0; b5_lock=B5.load_lock(); b5_delta=B5.near_margin(b5_lock)
    legacy=[m for m in METHODS if m not in ('B5_CONFLICT_RANK','B5_MAE_ONLY','B5_GLOBAL_RANK')]
    best={k:None for k in legacy}; b5_models=[m for m in ('B5_CONFLICT_RANK','B5_MAE_ONLY','B5_GLOBAL_RANK') if m in METHODS]
    near={m:[] for m in b5_models}; minima={m:float('inf') for m in b5_models}
    for pl,mv in C.candidates(p,int(CFG['move_budget'])):
        if not C.cluster_ok(p,pl): continue
        ev=evaluate_placement(p,pl,C.RISK)
        if not ev.feasible: continue
        n_adm+=1; key=C.pkey(pl); h.update((json.dumps(key,separators=(',',':'))+'\n').encode())
        rt=time.perf_counter(); xb=C.cross_bits(p,pl); wu=C.worst_util(p,ev); cs,detail=C.calibrated_scores(p,pl,coeffs); b5s,b5detail=B5.placement_scores(p,pl,b5_lock)
        common={'moves':mv,'cross_rack_bits':xb,'worst_u':wu,'mape_objective':float(ev.total_objective),'contention':detail,'b5':b5detail}
        if 'B0_AFFINITY_ADMISSION' in best: best['B0_AFFINITY_ADMISSION']=C.choose(best['B0_AFFINITY_ADMISSION'],xb,mv,key,pl,common)
        if 'B1_MAPE_CAP_WS' in best: best['B1_MAPE_CAP_WS']=C.choose(best['B1_MAPE_CAP_WS'],float(ev.total_objective),mv,key,pl,common)
        if 'B2_MAX_HEADROOM' in best: best['B2_MAX_HEADROOM']=C.choose(best['B2_MAX_HEADROOM'],wu,mv,key,pl,common)
        if 'B3_U_ONLY' in best: best['B3_U_ONLY']=C.choose(best['B3_U_ONLY'],cs['B3_U_ONLY'],mv,key,pl,{**common,'rank_score':cs['B3_U_ONLY']})
        if 'A1_U_NEFF' in best: best['A1_U_NEFF']=C.choose(best['A1_U_NEFF'],cs['A1_U_NEFF'],mv,key,pl,{**common,'rank_score':cs['A1_U_NEFF']})
        if 'B4_FULL_SHAPE' in best: best['B4_FULL_SHAPE']=C.choose(best['B4_FULL_SHAPE'],cs['B4_FULL_SHAPE'],mv,key,pl,{**common,'rank_score':cs['B4_FULL_SHAPE']})
        if 'B5_NOTIE' in best: best['B5_NOTIE']=C.choose(best['B5_NOTIE'],b5s['B5_CONFLICT_RANK'],mv,key,pl,{**common,'rank_score':b5s['B5_CONFLICT_RANK']})
        for model in b5_models:
            score=float(b5s[model])
            if score<minima[model]:
                minima[model]=score; near[model]=[x for x in near[model] if x[0]<=score+b5_delta+EPS]
            if score<=minima[model]+b5_delta+EPS:
                near[model].append((score,float(ev.total_objective),int(mv),key,dict(pl),{**common,'rank_score':score}))
        ranking_seconds += time.perf_counter()-rt
    if n_adm==0:
        return {'topology':topology,'size':label,'seed':seed,'valid':True,'n_admissible':0,'no_admissible_placement':True,'x_adm_sha256':h.hexdigest(),**cal,'elapsed_seconds':time.time()-t0}
    for model in b5_models:
        elig=[x for x in near[model] if x[0]<=minima[model]+b5_delta+EPS]
        if not elig: raise RuntimeError(f'{topology}/{label}/{seed}/{model}: near set unexpectedly empty')
        bx=min(elig,key=lambda x:(x[1],x[2],x[3]))
        best[model]={'order':(bx[0],bx[2],bx[3]),'placement':bx[4],'meta':{**bx[5],'b1_tiebreak_objective':bx[1],'near_margin':b5_delta,'near_candidate_count':len(elig),'strict_min_score':minima[model]}}
    sel={}
    for name,b in best.items():
        ev=evaluate_placement(p,b['placement'],C.RISK)
        if not ev.feasible: raise RuntimeError(f'{topology}/{label}/{seed}/{name} selected infeasible')
        sel[name]={'placement':b['placement'],'score':b['order'][0],'moves':b['order'][1],'placement_key':list(b['order'][2]),**b['meta']}
    elapsed=time.time()-t0; peak_rss_mb=None
    if resource is not None:
        v=float(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss); peak_rss_mb=v/1024.0 if sys.platform!='darwin' else v/(1024.0*1024.0)
    return {'topology':topology,'size':label,'seed':seed,'valid':True,'n_admissible':n_adm,'no_admissible_placement':False,
            'x_adm_sha256':h.hexdigest(),'selections':sel,**cal,'elapsed_seconds':elapsed,
            'ranking_score_seconds':ranking_seconds,'enumeration_admission_and_bookkeeping_seconds':max(0.0,elapsed-ranking_seconds),'peak_rss_mb':peak_rss_mb}

def build_graphs(workers=3):
    coeffs,_=C.load_coeffs();OUT.mkdir(parents=True,exist_ok=True);(OUT/'graphs').mkdir(exist_ok=True)
    jobs=[]
    for top in CFG['topologies']:
        for s in CFG['sizes']:
            for seed in seed_range(top,s['label']):
                p=OUT/'graphs'/f"{top}-{s['label']}-{seed}.json"
                if not p.exists():jobs.append((top,s['label'],seed))
    # Structured graphs are intentionally modest; thread pool avoids pickling coeff structures.
    from concurrent.futures import ThreadPoolExecutor
    def one(j):
        top,label,seed=j;r=solve(top,label,seed,coeffs);dump(OUT/'graphs'/f'{top}-{label}-{seed}.json',r);return r
    with ThreadPoolExecutor(max_workers=int(workers)) as ex:list(ex.map(one,jobs))
    return graph_summary()

def graph_summary():
    rows=[json.loads(p.read_text()) for p in sorted((OUT/'graphs').glob('*.json'))]
    valid=[x for x in rows if x.get('valid') and not x.get('no_admissible_placement')]
    rep={'scheduled':len(rows),'valid_with_admissible_set':len(valid),'by_topology':{},'by_size':{}}
    for top in CFG['topologies']:
        rr=[x for x in rows if x['topology']==top]
        rep['by_topology'][top]={'scheduled':len(rr),'valid':sum(x.get('valid') and not x.get('no_admissible_placement') for x in rr)}
    for s in CFG['sizes']:
        rr=[x for x in rows if x['size']==s['label']]
        rep['by_size'][s['label']]={'scheduled':len(rr),'valid':sum(x.get('valid') and not x.get('no_admissible_placement') for x in rr)}
    dump(OUT/'STRUCTURED_GRAPH_SUMMARY.json',rep);return rep

def build_packet_plan():
    good=D.solo_goodputs();graphs=[];unique={}
    for gp in sorted((OUT/'graphs').glob('*.json')):
        g=json.loads(gp.read_text())
        if not g.get('valid') or g.get('no_admissible_placement'):continue
        p,_=structured_problem(g['topology'],g['size'],int(g['seed']))
        gr={'topology':g['topology'],'size':g['size'],'seed':g['seed'],'x_adm_sha256':g['x_adm_sha256'],'methods':{}}
        for m in METHODS:
            pl=g['selections'][m]['placement'];cells,summ=D.make_group_cells(p,pl,CFG['execution_state'],good);refs=[]
            for cell in cells:
                key={'topology':g['topology'],'size':g['size'],'seed':g['seed'],'state':CFG['execution_state'],'group':cell['group'],
                     'duty_fraction':cell['duty_fraction'],'rates_mbps':[round(x,9) for x in cell['rates_mbps']]}
                cid='s-'+psha(key)[:20]
                if cid not in unique:unique[cid]={'cell_id':cid,**key,**cell}
                refs.append(cid)
            gr['methods'][m]={'placement':pl,'cell_ids':refs,**summ}
        graphs.append(gr)
    plan={'protocol':'paper2-v1.6-structured','rng_runs':CFG['rng_runs'],'state':CFG['execution_state'],'graphs':graphs,
          'unique_cells':sorted(unique.values(),key=lambda x:x['cell_id'])}
    dump(OUT/'STRUCTURED_PACKET_PLAN.json',plan);return plan

def run_packets(workers=4):
    plan=json.loads((OUT/'STRUCTURED_PACKET_PLAN.json').read_text()) if (OUT/'STRUCTURED_PACKET_PLAN.json').exists() else build_packet_plan()
    root=OUT/'packet_run';todo=[(c,r) for c in plan['unique_cells'] for r in plan['rng_runs']]
    rnd=random.Random(20261016);rnd.shuffle(todo)
    from concurrent.futures import ThreadPoolExecutor
    def one(z):
        c,rng=z
        return A.run_cell(root,'science',f"{c['cell_id']}-rng{rng}",c['rates_mbps'],int(rng),float(c['duty_fraction']),
                          {'base_cell_id':c['cell_id'],'topology':c['topology'],'size':c['size'],'planner_group_u':c['planner_group_u'],'direction_bits':c['direction_bits']})
    with ThreadPoolExecutor(max_workers=int(workers)) as ex:list(ex.map(one,todo))
    return analyze()

def cell_means(plan):
    out={}
    for c in plan['unique_cells']:
        rr=[json.loads((OUT/'packet_run/cells/science'/f"{c['cell_id']}-rng{r}"/'accepted.json').read_text()) for r in plan['rng_runs']]
        per=[[] for _ in range(6)]
        for x in rr:
            for z in x['packets']:per[int(z['sta_index'])].append(float(z['delivered_fraction']))
        out[c['cell_id']]=[float(np.mean(v)) if v else 1.0 for v in per]
    return out

def placement_D(mrec,means,lookup):
    total=float(mrec['total_cross_bits'])
    if total<=0:return 1.0
    d=float(mrec.get('nonshared_cross_bits',0.0))
    for cid in mrec['cell_ids']:
        c=lookup[cid];d+=sum(float(b)*float(x) for b,x in zip(c['direction_bits'],means[cid]))
    return d/total

def boot(vals,seed):
    x=np.asarray(vals,float)
    if len(x)==0:return None,None
    rng=np.random.default_rng(seed);B=int(CFG['bootstrap_resamples']);chunks=[];left=B
    while left:
        n=min(5000,left);idx=rng.integers(0,len(x),(n,len(x)));chunks.append(x[idx].mean(axis=1));left-=n
    b=np.concatenate(chunks);return float(x.mean()),[float(np.quantile(b,.025)),float(np.quantile(b,.975))]

def analyze():
    plan=json.loads((OUT/'STRUCTURED_PACKET_PLAN.json').read_text());means=cell_means(plan);lookup={x['cell_id']:x for x in plan['unique_cells']}
    rows=[]
    for g in plan['graphs']:
        for m,mr in g['methods'].items():
            rows.append({'topology':g['topology'],'size':g['size'],'seed':g['seed'],'method':m,'D':placement_D(mr,means,lookup)})
    by={(x['topology'],x['size'],x['seed'],x['method']):x for x in rows}
    diffs=[]
    for g in plan['graphs']:
        a=by[(g['topology'],g['size'],g['seed'],'B5_CONFLICT_RANK')]['D'];b=by[(g['topology'],g['size'],g['seed'],'B3_U_ONLY')]['D']
        diffs.append({'topology':g['topology'],'size':g['size'],'seed':g['seed'],'diff':a-b})
    mean,ci=boot([x['diff'] for x in diffs],int(CFG['bootstrap_seed']))
    rep={'overall':{'n_graphs':len(diffs),'mean_B5_minus_B3':mean,'ci95':ci,'supported':bool(ci and ci[0]>0)},'by_topology':{},'by_size':{}}
    for top in CFG['topologies']:
        d=[x['diff'] for x in diffs if x['topology']==top];m,c=boot(d,int(CFG['bootstrap_seed'])+sum(ord(q) for q in top));rep['by_topology'][top]={'n':len(d),'mean_B5_minus_B3':m,'ci95':c}
    for s in CFG['sizes']:
        d=[x['diff'] for x in diffs if x['size']==s['label']];m,c=boot(d,int(CFG['bootstrap_seed'])+int(s['replicas']));rep['by_size'][s['label']]={'n':len(d),'mean_B5_minus_B3':m,'ci95':c}
    dump(OUT/'STRUCTURED_TOPOLOGY_SUMMARY.json',rep)
    if rows:
        with (OUT/'STRUCTURED_GRAPH_METHOD.csv').open('w',newline='',encoding='utf-8') as f:
            w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    return rep

def main():
    ap=argparse.ArgumentParser();ap.add_argument('command',choices=['build-graphs','build-plan','run','analyze']);ap.add_argument('--workers',type=int,default=3);a=ap.parse_args()
    if a.command=='build-graphs':print(json.dumps(build_graphs(a.workers),indent=2));return
    if a.command=='build-plan':
        if not list((OUT/'graphs').glob('*.json')):build_graphs(a.workers)
        p=build_packet_plan();print(json.dumps({'graphs':len(p['graphs']),'unique_cells':len(p['unique_cells'])},indent=2));return
    print(json.dumps(run_packets(a.workers) if a.command=='run' else analyze(),indent=2))
if __name__=='__main__':main()
