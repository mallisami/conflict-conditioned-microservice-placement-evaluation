#!/usr/bin/env python3
from __future__ import annotations
import argparse,csv,json,math,random,sys,time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
import run_stage_a as A
CFG=json.loads((ROOT/'config/stage_a.json').read_text())
INTENTS=json.loads((ROOT/'config/stage_a_ood_intents.json').read_text())['intents']

def dump(p,o):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(o,indent=2,sort_keys=True),encoding='utf-8')
def root():
    p=ROOT/'stage_a_results/CURRENT_RUN.txt'
    if not p.exists():raise RuntimeError('Stage-A CURRENT_RUN missing')
    return Path(p.read_text().strip())
def cells(r):
    if not A.coefficient_freeze_valid(r):raise RuntimeError('OOD execution locked until coefficient freeze is valid')
    good=A.load_goodputs(r);rows=[]
    for c in INTENTS:
        s=float(c['resource_share']);U=float(c['U'])
        rates=[float(w)*U*s*float(g) for w,g in zip(c['weights'],good)]
        implied=sum(r/g for r,g in zip(rates,good) if r>0)/s
        if not math.isclose(implied,U,rel_tol=1e-10,abs_tol=1e-10):raise RuntimeError('OOD rate construction mismatch')
        rows.append({**c,'rates_mbps':rates})
    random.Random(int(CFG['run_order_seed'])+99).shuffle(rows)
    return rows
def run(workers=4):
    r=root();cc=cells(r);done=[0];t0=time.time()
    def one(c):
        extra={k:c[k] for k in ['shape_id','family','resource_share','U','m','n_eff','weights','parameter']}
        rec=A.run_cell(r,'ood',c['cell_id'],c['rates_mbps'],int(c['rng_run']),float(c['resource_share']),extra)
        done[0]+=1
        if done[0]%50==0 or done[0]==len(cc):print(f"[OOD {done[0]}/{len(cc)}] {(time.time()-t0)/60:.1f} min",flush=True)
        return rec
    with ThreadPoolExecutor(max_workers=int(workers)) as ex:list(ex.map(one,cc))
    return analyze()
def aggregate(r):
    recs=[json.loads(p.read_text()) for p in sorted((r/'cells/ood').glob('*/accepted.json'))]
    if len(recs)!=1350:raise RuntimeError(f'OOD incomplete: {len(recs)}/1350 accepted RNG cells')
    grp={}
    for x in recs:grp.setdefault((x['shape_id'],x['family'],float(x['resource_share']),float(x['U'])),[]).append(x)
    rows=[]
    for (sid,fam,s,U),rr in sorted(grp.items()):
        if len(rr)!=3:raise RuntimeError(f'OOD missing nested RNGs {sid}/{s}/{U}')
        D=float(np.mean([x['aggregate_delivered_fraction'] for x in rr]))
        rows.append({'shape_id':sid,'family':fam,'resource_share':s,'U':U,'m':rr[0]['m'],'n_eff':rr[0]['n_eff'],'loss':1-D})
    return rows
def pred(coef,x):return min(1.,max(0.,sum(float(a)*float(b) for a,b in zip(coef,x))))
def analyze():
    r=root()
    if not A.coefficient_freeze_valid(r):raise RuntimeError('coefficient freeze invalid')
    rows=aggregate(r);co=json.loads((r/'frozen_coefficients.json').read_text());per={};detail=[]
    for x in rows:
        fit=co['fits'][str(float(x['resource_share']))]
        p3=pred(fit['B3_U_only'],A.design_u(x['U']))
        p4=pred(fit['B4_full_shape'],A.design_full(x['U'],x['n_eff'],x['m']))
        z={**x,'pred_B3':p3,'pred_B4':p4,'ae_B3':abs(p3-x['loss']),'ae_B4':abs(p4-x['loss'])}
        detail.append(z);per.setdefault(x['shape_id'],[]).append(z)
    sr=[]
    for sid,rr in sorted(per.items()):
        a3=float(np.mean([q['ae_B3'] for q in rr]));a4=float(np.mean([q['ae_B4'] for q in rr]))
        sr.append({'shape_id':sid,'family':rr[0]['family'],'mae_B3':a3,'mae_B4':a4,'delta_B4_minus_B3':a4-a3})
    d=np.array([x['delta_B4_minus_B3'] for x in sr]);rng=np.random.default_rng(int(CFG['bootstrap_seed'])+91);B=int(CFG['bootstrap_resamples'])
    idx=rng.integers(0,len(d),(B,len(d)));bm=d[idx].mean(axis=1)
    rep={'n_ood_shapes':len(sr),'mean_delta_MAE_B4_minus_B3':float(d.mean()),'ci95':[float(np.quantile(bm,.025)),float(np.quantile(bm,.975))],
         'ood_supported':bool(np.quantile(bm,.975)<0),'note':'No refitting on OOD outcomes.'}
    dump(r/'RQ1_OOD_SUMMARY.json',rep)
    with (r/'ood_shape_errors.csv').open('w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=list(sr[0]));w.writeheader();w.writerows(sr)
    return rep
def main():
    ap=argparse.ArgumentParser();ap.add_argument('command',choices=['run','analyze']);ap.add_argument('--workers',type=int,default=4);a=ap.parse_args()
    print(json.dumps(run(a.workers) if a.command=='run' else analyze(),indent=2))
if __name__=='__main__':main()
