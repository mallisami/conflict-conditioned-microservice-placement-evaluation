#!/usr/bin/env python3
from __future__ import annotations
import argparse,hashlib,json,math,sys,csv
from pathlib import Path
import numpy as np
from scipy.stats import spearmanr
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
import run_stage_a as A
import run_stage_c as C
import run_stage_d as D
import b5_model as B5
FULL=json.loads((ROOT/'config/full_campaign.json').read_text()); CFG=FULL['stage_d_oracle']; OUT=ROOT/'stage_d_oracle_results'

def dump(p,o):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(o,indent=2,sort_keys=True),encoding='utf-8')
def h(o):return hashlib.sha256(json.dumps(o,sort_keys=True,separators=(',',':')).encode()).hexdigest()
def build():
    coeffs,_=C.load_coeffs();good=D.solo_goodputs();graphs=[];unique={};b5_lock=B5.load_lock()
    for seed in CFG['seeds']:
        p,cal=C.build_scaled_problem(CFG['size'],int(seed))
        if p is None:graphs.append({'seed':seed,'valid':False,**cal});continue
        candidates=[]
        for pl,mv in C.candidates(p,p.max_relocations or 0):
            if not C.cluster_ok(p,pl):continue
            ev=C.evaluate_placement(p,pl,C.RISK)
            if not ev.feasible:continue
            key=C.pkey(pl);cs,detail=C.calibrated_scores(p,pl,coeffs);b5s,b5detail=B5.placement_scores(p,pl,b5_lock)
            cells,summary=D.make_group_cells(p,pl,CFG['state'],good);refs=[]
            for cell in cells:
                k={'seed':seed,'state':CFG['state'],'group':cell['group'],'duty_fraction':cell['duty_fraction'],'rates_mbps':[round(x,9) for x in cell['rates_mbps']]}
                cid='o-'+h(k)[:20]
                if cid not in unique:unique[cid]={'cell_id':cid,**k,**cell}
                refs.append(cid)
            candidates.append({'placement':pl,'placement_key':list(key),'moves':mv,'B1':float(ev.total_objective),'B2':C.worst_util(p,ev),'B0':C.cross_bits(p,pl),
                               'B3':cs['B3_U_ONLY'],'A1':cs['A1_U_NEFF'],'B4':cs['B4_FULL_SHAPE'],
                               'B5':b5s['B5_CONFLICT_RANK'],'B5_MAE':b5s['B5_MAE_ONLY'],'B5_GLOBAL':b5s['B5_GLOBAL_RANK'],
                               'cell_ids':refs,**summary})
        graphs.append({'seed':seed,'valid':True,'n_admissible':len(candidates),'candidates':candidates})
    plan={'state':CFG['state'],'rng_runs':CFG['rng_runs'],'graphs':graphs,'unique_cells':sorted(unique.values(),key=lambda x:x['cell_id'])}
    dump(OUT/'ORACLE_PLAN.json',plan);return plan
def run(workers=4):
    plan=json.loads((OUT/'ORACLE_PLAN.json').read_text()) if (OUT/'ORACLE_PLAN.json').exists() else build()
    root=OUT/'packet_run';root.mkdir(parents=True,exist_ok=True);todo=[]
    for c in plan['unique_cells']:
        for rng in plan['rng_runs']:todo.append((c,rng))
    from concurrent.futures import ThreadPoolExecutor
    def one(z):
        c,rng=z;cid=f"{c['cell_id']}-rng{rng}"
        return A.run_cell(root,'science',cid,c['rates_mbps'],int(rng),float(c['duty_fraction']),{'base_cell_id':c['cell_id'],'planner_group_u':c['planner_group_u'],'direction_bits':c['direction_bits']})
    with ThreadPoolExecutor(max_workers=int(workers)) as ex:list(ex.map(one,todo))
    return analyze()
def means(plan):
    out={}
    for c in plan['unique_cells']:
        rr=[json.loads((OUT/'packet_run/cells/science'/f"{c['cell_id']}-rng{rng}"/'accepted.json').read_text()) for rng in plan['rng_runs']]
        pd=[[] for _ in range(6)]
        for r in rr:
            for q in r['packets']:pd[int(q['sta_index'])].append(float(q['delivered_fraction']))
        out[c['cell_id']]={'D':[float(np.mean(v)) if v else 1. for v in pd],'bits':c['direction_bits']}
    return out
def cand_D(c,mm):
    total=float(c['total_cross_bits'])
    if total<=0:return 1.
    delivered=float(c.get('nonshared_cross_bits',0))
    for cid in c['cell_ids']:
        x=mm[cid];delivered+=sum(float(b)*float(d) for b,d in zip(x['bits'],x['D']))
    return delivered/total
def boot(vals,seed):
    x=np.asarray(vals,float)
    if len(x)==0:return None,[None,None]
    rng=np.random.default_rng(seed);B=int(FULL['bootstrap_resamples']);chunks=[];left=B
    while left:
        n=min(5000,left);idx=rng.integers(0,len(x),(n,len(x)));chunks.append(x[idx].mean(axis=1));left-=n
    b=np.concatenate(chunks);return float(x.mean()),[float(np.quantile(b,.025)),float(np.quantile(b,.975))]

def analyze():
    plan=json.loads((OUT/'ORACLE_PLAN.json').read_text()); mm=means(plan); rows=[]; graphs=[]
    strict_rankers={'B0':'B0','B1':'B1','B2':'B2','B3':'B3','A1':'A1','B4':'B4','B5_NOTIE':'B5'}
    near_rankers={'B5':'B5','B5_MAE':'B5_MAE','B5_GLOBAL':'B5_GLOBAL'}
    b5_delta=B5.near_margin(); tol=1e-12; near=float(CFG.get('near_best_regret_threshold',0.01))
    for g in plan['graphs']:
        if not g.get('valid') or not g['candidates']: continue
        cc=[]
        for i,c in enumerate(g['candidates']):
            Dobs=cand_D(c,mm); cc.append({**c,'candidate_index':i,'observed_D':Dobs,'observed_loss':1-Dobs})
        bestD=max(x['observed_D'] for x in cc)
        rec={'seed':g['seed'],'n_admissible':len(cc),'best_observed_D':bestD,'rankers':{}}
        for name,key in strict_rankers.items():
            sel=min(cc,key=lambda x:(x[key],x['moves'],tuple(tuple(y) for y in x['placement_key'])))
            regret=bestD-sel['observed_D']
            rec['rankers'][name]={'observed_D':sel['observed_D'],'regret':regret,'candidate_index':sel['candidate_index'],
                                  'observed_best_capture':bool(regret<=tol),'near_best_capture':bool(regret<=near)}
        # Primary B5 and the two feature/training ablations use the identical
        # frozen near-margin + B1 tie-break. B5_NOTIE above isolates that rule.
        for name,key in near_rankers.items():
            pmin=min(x[key] for x in cc); elig=[x for x in cc if x[key]<=pmin+b5_delta+1e-12]
            sel=min(elig,key=lambda x:(x['B1'],x['moves'],tuple(tuple(y) for y in x['placement_key'])))
            regret=bestD-sel['observed_D']
            rec['rankers'][name]={'observed_D':sel['observed_D'],'regret':regret,'candidate_index':sel['candidate_index'],
                'observed_best_capture':bool(regret<=tol),'near_best_capture':bool(regret<=near),'near_candidate_count':len(elig),'near_margin':b5_delta}
        for name,key in [('B3','B3'),('A1','A1'),('B4','B4'),('B5','B5'),('B5_MAE','B5_MAE'),('B5_GLOBAL','B5_GLOBAL')]:
            rho=float(spearmanr([x[key] for x in cc],[x['observed_loss'] for x in cc]).statistic) if len(cc)>2 else float('nan')
            rec['rankers'][name]['spearman_predicted_vs_observed_loss']=rho
        graphs.append(rec)
        for x in cc:
            rows.append({'seed':g['seed'],'candidate_index':x['candidate_index'],'observed_D':x['observed_D'],'B3':x['B3'],'A1':x['A1'],'B4':x['B4'],'B5':x['B5'],'B5_MAE':x['B5_MAE'],'B5_GLOBAL':x['B5_GLOBAL']})
    all_rankers=['B0','B1','B2','B3','A1','B4','B5','B5_MAE','B5_GLOBAL','B5_NOTIE']
    summary={'n_graphs':len(graphs),'regret':{},'observed_best_capture':{},'near_best_capture':{},'paired_regret_contrasts':{}}
    for j,r in enumerate(all_rankers):
        vals=[g['rankers'][r]['regret'] for g in graphs];m,ci=boot(vals,int(FULL['bootstrap_seed'])+100+j)
        summary['regret'][r]={'mean':m,'median':float(np.median(vals)) if vals else None,'ci95_mean':ci}
        caps=[g['rankers'][r]['observed_best_capture'] for g in graphs];nc=[g['rankers'][r]['near_best_capture'] for g in graphs]
        summary['observed_best_capture'][r]={'count':int(sum(caps)),'n':len(caps),'rate':float(np.mean(caps)) if caps else None}
        summary['near_best_capture'][r]={'threshold_regret':near,'count':int(sum(nc)),'n':len(nc),'rate':float(np.mean(nc)) if nc else None}
    for j,comp in enumerate(['B3','A1','B4','B1','B5_MAE','B5_GLOBAL','B5_NOTIE']):
        vals=[g['rankers']['B5']['regret']-g['rankers'][comp]['regret'] for g in graphs];m,ci=boot(vals,int(FULL['bootstrap_seed'])+120+j)
        summary['paired_regret_contrasts'][f'B5-minus-{comp}']={'mean_regret_difference':m,'ci95':ci,'beneficial_if_negative':True}
    summary['mean_spearman']={r:float(np.nanmean([g['rankers'][r].get('spearman_predicted_vs_observed_loss',np.nan) for g in graphs])) for r in ['B3','A1','B4','B5','B5_MAE','B5_GLOBAL']} if graphs else {}
    dump(OUT/'ORACLE_SUMMARY.json',{'graphs':graphs,'summary':summary,'oracle_label':'ns-3 execution oracle; not physical ground truth'})
    if rows:
        with (OUT/'ORACLE_CANDIDATES.csv').open('w',newline='',encoding='utf-8') as f:
            w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    return summary

def main():
    ap=argparse.ArgumentParser();ap.add_argument('command',choices=['build-plan','run','analyze']);ap.add_argument('--workers',type=int,default=4);a=ap.parse_args()
    if a.command=='build-plan':p=build();print(json.dumps({'graphs':len(p['graphs']),'unique_cells':len(p['unique_cells'])},indent=2));return
    print(json.dumps(run(a.workers) if a.command=='run' else analyze(),indent=2))
if __name__=='__main__':main()
