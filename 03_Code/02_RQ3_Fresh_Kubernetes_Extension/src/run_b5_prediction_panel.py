#!/usr/bin/env python3
from __future__ import annotations
import argparse,csv,hashlib,json,math,random,sys
from dataclasses import replace
from pathlib import Path
import numpy as np
from scipy.stats import spearmanr,wilcoxon
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
import run_stage_a as A
import run_stage_c as C
import run_stage_d as D
import b5_model as B5
CFG=json.loads((ROOT/'config/b5_prediction_panel.json').read_text())
FULL=json.loads((ROOT/'config/full_campaign.json').read_text())
OUT=ROOT/'b5_prediction_panel_results'
METHODS=['B3_U_ONLY','A1_U_NEFF','B4_FULL_SHAPE','B5_CONFLICT_RANK','B5_MAE_ONLY','B5_GLOBAL_RANK']

def dump(p,o): p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(o,indent=2,sort_keys=True)+'\n',encoding='utf-8')
def hid(o): return hashlib.sha256(json.dumps(o,sort_keys=True,separators=(',',':')).encode()).hexdigest()[:20]

def _rescale_problem(p,target):
    cur=dict(p.current_placement)
    if not C.cluster_ok(p,cur): return None,{'invalid_reason':'current_cluster_infeasible'}
    ev=C.evaluate_placement(p,cur,C.RISK)
    if not ev.feasible:
        # Feasibility at unit load can fail only because the transformed demand is
        # already too high. Evaluate a tiny copy to isolate non-airtime defects.
        tiny=replace(p,flows=tuple(replace(f,bits_per_window=f.bits_per_window*C.TINY,requests_per_window=f.requests_per_window*C.TINY) for f in p.flows))
        et=C.evaluate_placement(tiny,cur,C.RISK)
        if not et.feasible:return None,{'invalid_reason':'current_non_airtime_or_availability_infeasible','reasons':et.reasons}
        u=C.worst_util(tiny,et)/C.TINY
    else:u=C.worst_util(p,ev)
    if not math.isfinite(u) or u<=0:return None,{'invalid_reason':'zero_or_invalid_current_utilization'}
    factor=float(target)/u
    flows=tuple(replace(f,bits_per_window=float(f.bits_per_window)*factor,requests_per_window=float(f.requests_per_window)*factor) for f in p.flows)
    return replace(p,flows=flows,metadata={**p.metadata,'b5_prediction_panel_scale':factor}),{'payload_scale':factor,'unit_current_utilization':u}

def ood_problem(family,seed):
    p=C.base_problem(8,1,2,int(seed)); flows=list(p.flows); n=len(flows); rng=np.random.default_rng(int(seed)*17+sum(ord(x) for x in family))
    if n<2: raise RuntimeError('OOD generator needs at least two flows')
    if family=='zipf':
        order=rng.permutation(n); ranks=np.arange(1,n+1,dtype=float); raw=1.0/(ranks**1.25); w=np.zeros(n);w[order]=raw
    elif family=='hotspot':
        order=rng.permutation(n); k=max(1,n//5);w=np.full(n,0.30/max(1,n-k));w[order[:k]]=0.70/k
    elif family=='bimodal':
        order=rng.permutation(n); k=max(1,min(2,n//3));w=np.full(n,0.35/max(1,n-k));w[order[:k]]=0.65/k
    elif family=='lognormal':
        w=rng.lognormal(mean=0.0,sigma=1.5,size=n)
    else: raise ValueError(family)
    w=np.asarray(w,float);w=w/w.sum();total=sum(float(f.bits_per_window) for f in flows)
    new=[]
    for i,f in enumerate(flows):
        old=max(float(f.bits_per_window),1e-12);bits=total*float(w[i]); ratio=bits/old
        new.append(replace(f,bits_per_window=bits,requests_per_window=max(1e-9,float(f.requests_per_window)*ratio)))
    p=replace(p,flows=tuple(new),metadata={**p.metadata,'b5_ood_family':family})
    return _rescale_problem(p,float(CFG['target_current_worst_utilization']))

def build_problem(split,family,seed):
    if split=='ID': return C.build_scaled_problem(CFG['size'],int(seed))
    return ood_problem(family,int(seed))

def schedule():
    out=[]
    for s in range(int(CFG['id_seed_start']),int(CFG['id_seed_end'])+1):out.append(('ID','id',s))
    for fam,(lo,hi) in CFG['ood_families'].items():
        for s in range(int(lo),int(hi)+1):out.append(('OOD',fam,s))
    return out

def admissible_panel(p,k):
    count=0; h=hashlib.sha256()
    for pl,mv in C.candidates(p,p.max_relocations or 0):
        if not C.cluster_ok(p,pl):continue
        ev=C.evaluate_placement(p,pl,C.RISK)
        if not ev.feasible:continue
        h.update((json.dumps(C.pkey(pl),separators=(',',':'))+'\n').encode());count+=1
    if count==0:return [],0,h.hexdigest()
    idxs=sorted(set(int(x) for x in np.linspace(0,count-1,min(int(k),count))))
    wanted=set(idxs);panel=[];i=0
    for pl,mv in C.candidates(p,p.max_relocations or 0):
        if not C.cluster_ok(p,pl):continue
        ev=C.evaluate_placement(p,pl,C.RISK)
        if not ev.feasible:continue
        if i in wanted:panel.append((i,dict(pl),int(mv),ev))
        i+=1
    if len(panel)!=len(idxs):raise RuntimeError('prediction-panel index reconstruction failed')
    return panel,count,h.hexdigest()

def build():
    coeffs,_=C.load_coeffs();good=D.solo_goodputs();b5=B5.load_lock();graphs=[];unique={}
    for split,fam,seed in schedule():
        p,cal=build_problem(split,fam,seed)
        if p is None:graphs.append({'split':split,'family':fam,'seed':seed,'valid':False,**cal});continue
        panel,nadm,xsha=admissible_panel(p,int(CFG['panel_candidates_per_graph']));sc=next(s for s in p.scenarios if s.scenario_id==CFG['execution_state']);cands=[]
        for idx,pl,mv,ev in panel:
            cs,cdetail=C.calibrated_scores(p,pl,coeffs);bs,bdetail=B5.placement_scores(p,pl,b5); legacy_state=cdetail[sc.scenario_id]['predicted_loss_fraction']; b5_state=bdetail['state_predictions'][sc.scenario_id]; cells,summ=D.make_group_cells(p,pl,sc.scenario_id,good);refs=[]
            for cell in cells:
                key={'split':split,'family':fam,'seed':seed,'candidate_index':idx,'group':cell['group'],'duty_fraction':cell['duty_fraction'],'rates_mbps':[round(x,9) for x in cell['rates_mbps']]}
                cid='p-'+hid(key)
                if cid not in unique:unique[cid]={'cell_id':cid,**key,**cell}
                refs.append(cid)
            cands.append({'candidate_index':idx,'placement':pl,'moves':mv,'B3_U_ONLY':legacy_state['B3_U_ONLY'],'A1_U_NEFF':legacy_state['A1_U_NEFF'],'B4_FULL_SHAPE':legacy_state['B4_FULL_SHAPE'],
                          'B5_CONFLICT_RANK':b5_state['B5_CONFLICT_RANK'],'B5_MAE_ONLY':b5_state['B5_MAE_ONLY'],'B5_GLOBAL_RANK':b5_state['B5_GLOBAL_RANK'],'cell_ids':refs,**summ})
        graphs.append({'split':split,'family':fam,'seed':seed,'valid':True,'n_admissible':nadm,'x_adm_sha256':xsha,'panel_count':len(cands),'candidates':cands,**cal})
    plan={'protocol_id':CFG['protocol_id'],'rng_runs':CFG['rng_runs'],'graphs':graphs,'unique_cells':sorted(unique.values(),key=lambda x:x['cell_id'])}
    dump(OUT/'PREDICTION_PANEL_PLAN.json',plan);return plan

def run(workers=3):
    plan=json.loads((OUT/'PREDICTION_PANEL_PLAN.json').read_text()) if (OUT/'PREDICTION_PANEL_PLAN.json').exists() else build();root=OUT/'packet_run'
    todo=[(c,r) for c in plan['unique_cells'] for r in plan['rng_runs']]
    from concurrent.futures import ThreadPoolExecutor
    def one(z):
        c,r=z;return A.run_cell(root,'science',f"{c['cell_id']}-rng{r}",c['rates_mbps'],int(r),float(c['duty_fraction']),{'prediction_panel':True,'split':c['split'],'family':c['family'],'seed':c['seed'],'direction_bits':c['direction_bits']})
    with ThreadPoolExecutor(max_workers=int(workers)) as ex:list(ex.map(one,todo))
    return analyze()

def _means(plan):
    out={}
    for c in plan['unique_cells']:
        rr=[json.loads((OUT/'packet_run/cells/science'/f"{c['cell_id']}-rng{r}"/'accepted.json').read_text()) for r in plan['rng_runs']];d=[[] for _ in range(6)]
        for x in rr:
            for q in x['packets']:d[int(q['sta_index'])].append(float(q['delivered_fraction']))
        out[c['cell_id']]=[float(np.mean(v)) if v else 1.0 for v in d]
    return out

def observed_D(c,means,lookup):
    total=float(c['total_cross_bits'])
    if total<=0:return 1.0
    delivered=float(c.get('nonshared_cross_bits',0.0))
    for cid in c['cell_ids']:
        cell=lookup[cid];delivered+=sum(float(b)*float(x) for b,x in zip(cell['direction_bits'],means[cid]))
    return delivered/total

def boot(vals,seed):
    x=np.asarray(vals,float)
    if len(x)==0:return None,[None,None]
    rng=np.random.default_rng(seed);B=int(CFG['bootstrap_resamples']);chunks=[];left=B
    while left:
        n=min(5000,left);idx=rng.integers(0,len(x),(n,len(x)));chunks.append(x[idx].mean(axis=1));left-=n
    z=np.concatenate(chunks);return float(x.mean()),[float(np.quantile(z,.025)),float(np.quantile(z,.975))]

def analyze():
    plan=json.loads((OUT/'PREDICTION_PANEL_PLAN.json').read_text());lookup={x['cell_id']:x for x in plan['unique_cells']};means=_means(plan);rows=[];graph_metrics=[]
    for g in plan['graphs']:
        if not g.get('valid') or not g.get('candidates'):continue
        cr=[]
        for c in g['candidates']:
            Dobs=observed_D(c,means,lookup);loss=1.0-Dobs;row={'split':g['split'],'family':g['family'],'seed':g['seed'],'candidate_index':c['candidate_index'],'observed_loss':loss}
            for m in METHODS:row[m]=float(c[m])
            cr.append(row);rows.append(row)
        gm={'split':g['split'],'family':g['family'],'seed':g['seed'],'n_candidates':len(cr)}
        for m in METHODS:
            gm['mae_'+m]=float(np.mean([abs(x[m]-x['observed_loss']) for x in cr]))
            gm['rho_'+m]=float(spearmanr([x[m] for x in cr],[x['observed_loss'] for x in cr]).statistic) if len(cr)>2 else None
        graph_metrics.append(gm)
    def report_split(split):
        gg=[x for x in graph_metrics if x['split']==split];out={'n_graphs':len(gg),'mean_mae':{m:float(np.mean([x['mae_'+m] for x in gg])) for m in METHODS},'contrasts':{}}
        for j,comp in enumerate(['B3_U_ONLY','B4_FULL_SHAPE','B5_MAE_ONLY','B5_GLOBAL_RANK']):
            d=[x['mae_B5_CONFLICT_RANK']-x['mae_'+comp] for x in gg];m,ci=boot(d,int(CFG['bootstrap_seed'])+(0 if split=='ID' else 100)+j)
            out['contrasts'][f'B5_CONFLICT_RANK-minus-{comp}']={'mean_delta_MAE':m,'ci95':ci,'supported_lower_MAE':bool(ci[1]<0),'practically_relevant':bool(m is not None and m<=-float(FULL['practical_significance']['RQ1_MAE_absolute_improvement_min']))}
        return out
    rep={'primary_RQ1_ID':report_split('ID'),'RQ1_OOD':report_split('OOD'),'OOD_by_family':{},'inferential_unit':CFG['inferential_unit']}
    for fam in CFG['ood_families']:
        gg=[x for x in graph_metrics if x['split']=='OOD' and x['family']==fam]
        d=[x['mae_B5_CONFLICT_RANK']-x['mae_B3_U_ONLY'] for x in gg];m,ci=boot(d,int(CFG['bootstrap_seed'])+500+sum(ord(c) for c in fam));rep['OOD_by_family'][fam]={'n_graphs':len(gg),'mean_delta_MAE_B5_minus_B3':m,'ci95':ci}
    OUT.mkdir(parents=True,exist_ok=True)
    if rows:
        with (OUT/'PREDICTION_PANEL_CANDIDATES.csv').open('w',newline='',encoding='utf-8') as f:w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    if graph_metrics:
        with (OUT/'PREDICTION_PANEL_GRAPH_METRICS.csv').open('w',newline='',encoding='utf-8') as f:w=csv.DictWriter(f,fieldnames=list(graph_metrics[0]));w.writeheader();w.writerows(graph_metrics)
    dump(OUT/'RQ1_B5_PREDICTION_SUMMARY.json',rep);return rep

def main():
    ap=argparse.ArgumentParser();ap.add_argument('command',choices=['build-plan','run','analyze']);ap.add_argument('--workers',type=int,default=3);a=ap.parse_args()
    if a.command=='build-plan':p=build();print(json.dumps({'graphs':len(p['graphs']),'unique_cells':len(p['unique_cells'])},indent=2));return
    print(json.dumps(run(a.workers) if a.command=='run' else analyze(),indent=2))
if __name__=='__main__':main()
