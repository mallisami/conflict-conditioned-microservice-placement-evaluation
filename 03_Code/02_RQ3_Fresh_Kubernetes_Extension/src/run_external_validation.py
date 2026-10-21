#!/usr/bin/env python3
from __future__ import annotations
import argparse,csv,json,math,re,sys,hashlib
from dataclasses import replace
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
import run_stage_c as C
import run_stage_d as D
import run_stage_a as A
import b5_model as B5
FULL=json.loads((ROOT/'config/full_campaign.json').read_text());CFG=FULL['external_validation'];OUT=ROOT/'external_validation_results'
def dump(p,o):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(o,indent=2,sort_keys=True),encoding='utf-8')
def find_dataset():
    root=ROOT/'external_data/SNOB5GData'
    p=root/str(CFG.get('dataset_file','dataset_complete.csv'))
    if not p.exists():raise RuntimeError('Pinned SNOB5G dataset CSV missing. Run external/01_FETCH_SNOB5G.sh before campaign.')
    fix=root/'FROZEN_DATASET_FIXITY.json'
    if not fix.exists():raise RuntimeError('SNOB5G fixity manifest missing; fetch script must verify the pinned commit/blob first.')
    fx=json.loads(fix.read_text())
    actual=hashlib.sha256(p.read_bytes()).hexdigest()
    if fx.get('source_commit')!=CFG.get('source_commit') or fx.get('git_blob_sha1')!=CFG.get('expected_git_blob_sha1') or fx.get('sha256')!=actual:
        raise RuntimeError('SNOB5G fixity verification failed')
    return p
def norm(s):return re.sub(r'[^a-z0-9]+','',s.lower())
def col(fieldnames,cands):
    mm={norm(x):x for x in fieldnames}
    for c in cands:
        if norm(c) in mm:return mm[norm(c)]
    for k,v in mm.items():
        if any(norm(c) in k for c in cands):return v
    return None
def condition(v):
    s=str(v).lower()
    if 'short' in s:return 'short_blockage'
    if 'long' in s or 'blocked' in s:return 'long_blockage'
    if 'normal' in s or 'los' in s:return 'normal'
    return None
def prepare():
    p=find_dataset()
    with p.open(newline='',encoding='utf-8-sig',errors='replace') as f:
        r=csv.DictReader(f);fn=r.fieldnames or []
        c_s=col(fn,['scenario','scenario id']); c_l=col(fn,['link']); c_rx=col(fn,['received (mbps)','received mbps','received']); c_m=col(fn,['mcs mode','mode'])
        if not all([c_s,c_l,c_rx]):raise RuntimeError(f'cannot identify scenario/link/received columns from {fn}')
        rows=[]
        for x in r:
            co=condition(x.get(c_s,''))
            if not co:continue
            if c_m and x.get(c_m) and str(x.get(c_m)).lower() not in ('auto','automatic','9','mcs9'):
                # Prefer auto where available; complete datasets may encode the mode numerically/textually.
                continue
            try:y=float(x[c_rx])
            except:continue
            if not math.isfinite(y) or y<=0:continue
            rows.append((co,str(x[c_l]),y))
    if not rows:raise RuntimeError('no usable SNOB5G rows after filtering')
    links=sorted({l for _,l,_ in rows})
    # normal median per link
    med={}
    for l in links:
        vals=[y for c,ll,y in rows if c=='normal' and ll==l]
        if vals:med[l]=float(np.median(vals))
    links=[l for l in links if l in med and med[l]>0]
    if not links:raise RuntimeError('no links with normal baseline')
    use=(links*6)[:6] if len(links)<6 else links[:6]
    vectors=[]
    for co in CFG['conditions']:
        for q in CFG['quantiles']:
            vals=[]
            for l in use:
                vv=[y/med[l] for c,ll,y in rows if c==co and ll==l and med[l]>0]
                vals.append(float(np.quantile(vv,float(q))) if vv else 1.0)
            vals=[min(1.5,max(0.05,x)) for x in vals]
            vectors.append({'condition':co,'quantile':q,'physical_links':use,'direction_multipliers':vals})
    rec={'dataset_path':str(p),'dataset_sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'usable_rows':len(rows),'links':use,'vectors':vectors,
         'boundary':'External physical rate/state input only; SNOB5G has no co-channel contention experiment.'}
    dump(OUT/'EXTERNAL_RATE_VECTORS.json',rec);return rec
def scaled_conflict_problem(p,mults):
    scenarios=[]
    for sc in p.scenarios:
        if sc.scenario_id!='conflict-dense':
            scenarios.append(sc);continue
        links={}
        for i,pair in enumerate(C.PAIR_ORDER):
            a,b=pair.split('>');ln=sc.links[(a,b)]
            links[(a,b)]=replace(ln,goodput_bps=max(1.,float(ln.goodput_bps)*float(mults[i])))
        scenarios.append(replace(sc,links=links))
    return replace(p,scenarios=tuple(scenarios))
def rank_graph(label,seed,mults,coeffs):
    p,_=C.build_scaled_problem(label,seed); pp=scaled_conflict_problem(p,mults)
    methods=list(CFG['methods']); best={k:None for k in methods if k!='B5_CONFLICT_RANK'}
    b5_lock=B5.load_lock(); delta=B5.near_margin(b5_lock); b5_min=float('inf'); b5_near=[]; n=0
    for pl,mv in C.candidates(pp,pp.max_relocations or 0):
        if not C.cluster_ok(pp,pl): continue
        ev=C.evaluate_placement(pp,pl,C.RISK)
        if not ev.feasible: continue
        n+=1; key=C.pkey(pl); cs,_=C.calibrated_scores(pp,pl,coeffs); b5s,_=B5.placement_scores(pp,pl,b5_lock)
        scores={'B1_MAPE_CAP_WS':float(ev.total_objective),'B3_U_ONLY':cs['B3_U_ONLY'],'B4_FULL_SHAPE':cs['B4_FULL_SHAPE']}
        for m in best:
            cand=(float(scores[m]),int(mv),key,dict(pl))
            if best[m] is None or cand[:3]<best[m][:3]: best[m]=cand
        if 'B5_CONFLICT_RANK' in methods:
            score=float(b5s['B5_CONFLICT_RANK'])
            if score<b5_min:
                b5_min=score; b5_near=[x for x in b5_near if x[0]<=score+delta+1e-12]
            if score<=b5_min+delta+1e-12:
                b5_near.append((score,float(ev.total_objective),int(mv),key,dict(pl)))
    out={m:(best[m][3] if best.get(m) else None) for m in best}
    if 'B5_CONFLICT_RANK' in methods:
        elig=[x for x in b5_near if x[0]<=b5_min+delta+1e-12]
        out['B5_CONFLICT_RANK']=min(elig,key=lambda x:(x[1],x[2],x[3]))[4] if elig else None
    return pp,n,out

def replay_plan():
    ext=json.loads((OUT/'EXTERNAL_RATE_VECTORS.json').read_text()) if (OUT/'EXTERNAL_RATE_VECTORS.json').exists() else prepare()
    coeffs,_=C.load_coeffs();good=D.solo_goodputs();graphs=[];unique={}
    for label,*rest in C.SIZES:
        bounds=CFG['graph_seed_blocks'][label]; seeds=range(int(bounds[0]),int(bounds[1])+1)
        if len(list(seeds))!=int(CFG['graph_seeds_per_size']): raise RuntimeError(f'external seed block mismatch for {label}')
        for seed in seeds:
            for vi,v in enumerate(ext['vectors']):
                pp,n,sel=rank_graph(label,int(seed),v['direction_multipliers'],coeffs)
                rec={'size':label,'seed':int(seed),'vector_index':vi,'condition':v['condition'],'quantile':v['quantile'],'n_admissible':n,'methods':{}}
                for m,pl in sel.items():
                    if pl is None:rec['methods'][m]={'placement':None,'cell_ids':[]};continue
                    cells,summ=D.make_group_cells(pp,pl,'conflict-dense',good);refs=[]
                    for c in cells:
                        k={'size':label,'seed':seed,'vector_index':vi,'method':m,'group':c['group'],'duty_fraction':c['duty_fraction'],'rates_mbps':[round(x,9) for x in c['rates_mbps']]}
                        cid='x-'+hashlib.sha256(json.dumps(k,sort_keys=True).encode()).hexdigest()[:20]
                        if cid not in unique:unique[cid]={'cell_id':cid,**k,**c}
                        refs.append(cid)
                    rec['methods'][m]={'placement':pl,'cell_ids':refs,**summ}
                graphs.append(rec)
    plan={'vectors':ext['vectors'],'rng_runs':CFG['rng_runs'],'graphs':graphs,'unique_cells':list(unique.values())}
    dump(OUT/'EXTERNAL_REPLAY_PLAN.json',plan);return plan
def run(workers=4):
    plan=json.loads((OUT/'EXTERNAL_REPLAY_PLAN.json').read_text()) if (OUT/'EXTERNAL_REPLAY_PLAN.json').exists() else replay_plan()
    root=OUT/'packet_run';todo=[(c,rng) for c in plan['unique_cells'] for rng in plan['rng_runs']]
    from concurrent.futures import ThreadPoolExecutor
    def one(z):
        c,rng=z
        return A.run_cell(root,'science',f"{c['cell_id']}-rng{rng}",c['rates_mbps'],int(rng),float(c['duty_fraction']),{'condition':next(g['condition'] for g in plan['graphs'] if g['size']==c['size'] and g['seed']==c['seed'] and g['vector_index']==c['vector_index']),'direction_bits':c['direction_bits']})
    with ThreadPoolExecutor(max_workers=int(workers)) as ex:list(ex.map(one,todo))
    return analyze()
def boot(vals,seed):
    x=np.asarray(vals,float)
    if len(x)==0:return None,[None,None]
    rng=np.random.default_rng(seed);B=int(FULL['bootstrap_resamples']);chunks=[];left=B
    while left:
        n=min(5000,left);idx=rng.integers(0,len(x),(n,len(x)));chunks.append(x[idx].mean(axis=1));left-=n
    z=np.concatenate(chunks);return float(x.mean()),[float(np.quantile(z,.025)),float(np.quantile(z,.975))]

def analyze():
    plan=json.loads((OUT/'EXTERNAL_REPLAY_PLAN.json').read_text()); lookup={c['cell_id']:c for c in plan['unique_cells']}
    means={}
    for c in plan['unique_cells']:
        rr=[json.loads((OUT/'packet_run/cells/science'/f"{c['cell_id']}-rng{r}"/'accepted.json').read_text()) for r in plan['rng_runs']]
        ds=[[] for _ in range(6)]
        for x in rr:
            for z in x['packets']: ds[int(z['sta_index'])].append(float(z['delivered_fraction']))
        means[c['cell_id']]=[float(np.mean(v)) if v else 1. for v in ds]
    rows=[]
    for g in plan['graphs']:
        for m,mr in g['methods'].items():
            if mr.get('placement') is None: continue
            total=float(mr['total_cross_bits']); deliv=float(mr.get('nonshared_cross_bits',0))
            for cid in mr['cell_ids']:
                c=lookup[cid]; deliv+=sum(float(b)*float(d) for b,d in zip(c['direction_bits'],means[cid]))
            rows.append({'size':g['size'],'seed':g['seed'],'condition':g['condition'],'quantile':g['quantile'],'method':m,'D':deliv/total if total>0 else 1.0})
    by={(x['size'],x['seed'],x['condition'],float(x['quantile']),x['method']):x for x in rows}
    out={}
    for ci,co in enumerate(CFG['conditions']):
        graph_ids=sorted({(x['size'],int(x['seed'])) for x in rows if x['condition']==co})
        contrasts={}
        for method,label in [('B5_CONFLICT_RANK','B5_minus_B3'),('B4_FULL_SHAPE','B4_minus_B3')]:
            graph_d=[]; quantile_desc={}
            for size,seed in graph_ids:
                vals=[]
                for q in CFG['quantiles']:
                    km=(size,seed,co,float(q),method); k3=(size,seed,co,float(q),'B3_U_ONLY')
                    if km in by and k3 in by: vals.append(by[km]['D']-by[k3]['D'])
                if vals: graph_d.append(float(np.mean(vals)))
            for q in CFG['quantiles']:
                vals=[]
                for size,seed in graph_ids:
                    km=(size,seed,co,float(q),method); k3=(size,seed,co,float(q),'B3_U_ONLY')
                    if km in by and k3 in by: vals.append(by[km]['D']-by[k3]['D'])
                quantile_desc[str(q)]={'n_graphs':len(vals),'mean_difference':float(np.mean(vals)) if vals else None}
            m,ci95=boot(graph_d,int(FULL['bootstrap_seed'])+200+ci+(0 if method.startswith('B5') else 20))
            contrasts[label]={'inferential_unit':'graph_identity','n_graphs':len(graph_d),'mean_across_within_graph_quantile_sensitivity':m,'ci95':ci95,'quantile_sensitivity_descriptive':quantile_desc}
        out[co]=contrasts
    rep={'physical_rate_transfer':out,'primary_external_contrast':'B5_minus_B3',
         'boundary':'Measured IEEE 802.11ad/mmWave rate-state inputs only. Quantile vectors are within-graph sensitivity points; packet contention remains ns-3 and this is not physical concurrent-link validation.'}
    dump(OUT/'EXTERNAL_VALIDATION_SUMMARY.json',rep); return rep

def main():
    ap=argparse.ArgumentParser();ap.add_argument('command',choices=['prepare','build-plan','run','analyze']);ap.add_argument('--workers',type=int,default=4);a=ap.parse_args()
    if a.command=='prepare':print(json.dumps(prepare(),indent=2));return
    if a.command=='build-plan':p=replay_plan();print(json.dumps({'graphs':len(p['graphs']),'cells':len(p['unique_cells'])},indent=2));return
    print(json.dumps(run(a.workers) if a.command=='run' else analyze(),indent=2))
if __name__=='__main__':main()
