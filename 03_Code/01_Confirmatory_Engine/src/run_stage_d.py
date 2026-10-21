#!/usr/bin/env python3
from __future__ import annotations
import argparse,csv,hashlib,json,math,random,sys,time
from pathlib import Path
from typing import Any
import numpy as np
from scipy.stats import wilcoxon

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
import run_stage_a as A
import run_stage_c as C
FULL=json.loads((ROOT/'config/full_campaign.json').read_text())
D_CFG=FULL['stage_d']; OUT=ROOT/'stage_d_results'; PAIRS=C.PAIR_ORDER
METHODS=list(FULL.get('confirmatory_methods',['B1_MAPE_CAP_WS','B3_U_ONLY','A1_U_NEFF','B4_FULL_SHAPE','B5_CONFLICT_RANK']))


def dump(p:Path,o:Any): p.parent.mkdir(parents=True,exist_ok=True); p.write_text(json.dumps(o,indent=2,sort_keys=True),encoding='utf-8')
def sha_obj(o): return hashlib.sha256(json.dumps(o,sort_keys=True,separators=(',',':')).encode()).hexdigest()
def stage_a_root():
    p=ROOT/'stage_a_results/CURRENT_RUN.txt'
    if not p.exists(): raise RuntimeError('Stage-A run pointer missing')
    return Path(p.read_text().strip())
def solo_goodputs(): return A.load_goodputs(stage_a_root())
def state_of(p,sid): return next(s for s in p.scenarios if s.scenario_id==sid)
def pair_bits(p,pl):
    nodes=p.node_by_id; bits={k:0.0 for k in PAIRS}
    for f in p.flows:
        a=nodes[pl[f.source_replica]].rack_id; b=nodes[pl[f.destination_replica]].rack_id
        if a!=b: bits[f'{a}>{b}']+=float(f.bits_per_window)
    return bits

def make_group_cells(p,pl,sid,good):
    sc=state_of(p,sid); bits=pair_bits(p,pl); by={}
    for i,pair in enumerate(PAIRS):
        a,b=pair.split('>'); link=sc.links[(a,b)]
        if bits[pair]<=0 or not link.available or not link.conflict_group: continue
        g=link.conflict_group; air=bits[pair]/float(link.goodput_bps)/float(p.decision_window_seconds)
        rec=by.setdefault(g,{'airfrac':[0.0]*6,'bits':[0.0]*6})
        rec['airfrac'][i]=air; rec['bits'][i]=bits[pair]
    cells=[]
    for g,rec in sorted(by.items()):
        budget=float(sc.conflict_budgets_seconds[g]); duty=budget/float(p.decision_window_seconds)
        rates=[rec['airfrac'][i]*float(good[i]) for i in range(6)]
        U=sum(rec['airfrac'])/duty if duty>0 else 0.0
        cells.append({'group':g,'duty_fraction':duty,'rates_mbps':rates,'direction_bits':rec['bits'],'planner_group_u':U})
    # cross-rack bits not carried by a shared group are treated as loss-free for this shared-medium endpoint.
    grouped=sum(sum(c['direction_bits']) for c in cells); total=sum(bits.values())
    return cells,{'all_direction_bits':[bits[pair] for pair in PAIRS],'total_cross_bits':total,'shared_group_bits':grouped,'nonshared_cross_bits':total-grouped}

def build_plan():
    good=solo_goodputs(); graphs=[]; unique={}
    for gp in sorted((ROOT/'stage_c_results/graphs').glob('*.json')):
        r=json.loads(gp.read_text())
        if not r.get('valid') or r.get('no_admissible_placement'): continue
        p,cal=C.build_scaled_problem(r['size'],int(r['seed']))
        if p is None: raise RuntimeError(f"Stage-C reconstruct failed {r['size']}/{r['seed']}")
        grow={'size':r['size'],'seed':int(r['seed']),'x_adm_sha256':r['x_adm_sha256'],'state_weights':{s.scenario_id:float(s.weight) for s in p.scenarios},'methods':{}}
        for method in METHODS:
            sel=r['selections'][method]; pl=sel['placement']; mrec={'placement':pl,'states':{}}
            for sid in D_CFG['states']:
                cells,summary=make_group_cells(p,pl,sid,good); refs=[]
                for cell in cells:
                    key={'size':r['size'],'seed':int(r['seed']),'state':sid,'group':cell['group'],'duty_fraction':cell['duty_fraction'],'rates_mbps':[round(x,9) for x in cell['rates_mbps']]}
                    cid='d-'+sha_obj(key)[:20]
                    if cid not in unique: unique[cid]={'cell_id':cid,**key,**cell}
                    refs.append(cid)
                mrec['states'][sid]={'cell_ids':refs,**summary}
            grow['methods'][method]=mrec
        graphs.append(grow)
    cells=sorted(unique.values(),key=lambda x:x['cell_id'])
    plan={'protocol':'paper2-b5-confirmatory-stage-d-v1.0','stage_a_solo_goodputs_mbps':good,'rng_runs':D_CFG['rng_runs'],'states':D_CFG['states'],'graphs':graphs,'unique_cells':cells}
    OUT.mkdir(parents=True,exist_ok=True); dump(OUT/'STAGE_D_PLAN.json',plan); (OUT/'STAGE_D_PLAN.sha256').write_text(sha_obj(plan)+'  STAGE_D_PLAN.json\n')
    return plan

def run(workers=None):
    plan=json.loads((OUT/'STAGE_D_PLAN.json').read_text()) if (OUT/'STAGE_D_PLAN.json').exists() else build_plan()
    root=OUT/'packet_run'; root.mkdir(parents=True,exist_ok=True)
    todo=[]
    for c in plan['unique_cells']:
        for rng in plan['rng_runs']:
            cid=f"{c['cell_id']}-rng{rng}"
            todo.append((cid,c,rng))
    rnd=random.Random(20261009); rnd.shuffle(todo); done=[0]; t0=time.time()
    def one(item):
        cid,c,rng=item
        extra={'base_cell_id':c['cell_id'],'state':c['state'],'group':c['group'],'planner_group_u':c['planner_group_u'],'direction_bits':c['direction_bits']}
        rec=A.run_cell(root,'science',cid,c['rates_mbps'],int(rng),float(c['duty_fraction']),extra)
        done[0]+=1
        if done[0]%50==0 or done[0]==len(todo): print(f"[Stage-D {done[0]}/{len(todo)}] {((time.time()-t0)/60):.1f} min",flush=True)
        return rec
    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=int(workers or FULL['stage_d_workers'])) as ex:list(ex.map(one,todo))
    return analyze()

def cell_means(plan):
    root=OUT/'packet_run/cells/science'; out={}
    for c in plan['unique_cells']:
        rows=[]
        for rng in plan['rng_runs']:
            p=root/f"{c['cell_id']}-rng{rng}"/'accepted.json'
            if not p.exists(): raise RuntimeError(f'missing Stage-D cell {p}')
            rows.append(json.loads(p.read_text()))
        per=[[] for _ in range(6)]
        for r in rows:
            for x in r['packets']: per[int(x['sta_index'])].append(float(x['delivered_fraction']))
        out[c['cell_id']]={'direction_D':[float(np.mean(v)) if v else 1.0 for v in per],'planner_group_u':c['planner_group_u'],'state':c['state'],'group':c['group']}
    return out

def placement_D(mstate,means):
    total=float(mstate['total_cross_bits'])
    if total<=0:return 1.0
    delivered=float(mstate.get('nonshared_cross_bits',0.0))
    for cid in mstate['cell_ids']:
        cm=means[cid]
        # direction bits are in the plan cell
        c=next(x for x in PLAN_CACHE['unique_cells'] if x['cell_id']==cid)
        delivered+=sum(float(b)*float(d) for b,d in zip(c['direction_bits'],cm['direction_D']))
    return delivered/total

def boot(diff,seed):
    x=np.asarray(diff,float); rng=np.random.default_rng(seed); B=int(FULL['bootstrap_resamples']); chunks=[]; left=B
    while left:
        n=min(5000,left); idx=rng.integers(0,len(x),(n,len(x))); chunks.append(x[idx].mean(axis=1)); left-=n
    v=np.concatenate(chunks); return float(x.mean()),[float(np.quantile(v,.025)),float(np.quantile(v,.975))]
def wp(diff):
    x=np.asarray(diff,float); x=x[np.abs(x)>1e-12]
    if len(x)==0:return 1.0
    return float(wilcoxon(x,alternative='two-sided').pvalue)
def holm(ps):
    order=sorted(range(len(ps)),key=lambda i:ps[i]); out=[1.0]*len(ps); running=0
    for j,i in enumerate(order): running=max(running,min(1.0,ps[i]*(len(ps)-j))); out[i]=running
    return out

def analyze():
    global PLAN_CACHE
    PLAN_CACHE=json.loads((OUT/'STAGE_D_PLAN.json').read_text()); means=cell_means(PLAN_CACHE); rows=[]
    for g in PLAN_CACHE['graphs']:
        for m,mr in g['methods'].items():
            for sid,sr in mr['states'].items():
                rows.append({'size':g['size'],'seed':g['seed'],'method':m,'state':sid,'delivered_fraction':placement_D(sr,means),'total_cross_bits':sr['total_cross_bits']})
    with (OUT/'STAGE_D_GRAPH_METHOD_STATE.csv').open('w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    by={(r['size'],r['seed'],r['state'],r['method']):r for r in rows}
    primary=[]
    for g in PLAN_CACHE['graphs']:
        k=(g['size'],g['seed'],'conflict-dense')
        if (*k,'B5_CONFLICT_RANK') in by and (*k,'B3_U_ONLY') in by: primary.append(by[(*k,'B5_CONFLICT_RANK')]['delivered_fraction']-by[(*k,'B3_U_ONLY')]['delivered_fraction'])
    mean,ci=boot(primary,int(FULL['bootstrap_seed'])+20)
    sesoi=float(FULL.get('practical_significance',{}).get('RQ2_delivered_fraction_improvement_min',0.005)); report={'primary_RQ2':{'contrast':'B5_CONFLICT_RANK-minus-B3_U_ONLY','state':'conflict-dense','n_graphs':len(primary),'mean_difference':mean,'ci95':ci,'supported':bool(ci[0]>0),'sesoi':sesoi,'practically_relevant':bool(mean>=sesoi),'strong_operational_support':bool(ci[0]>0 and mean>=sesoi)}}
    second=[]
    for comp in ['B1_MAPE_CAP_WS','A1_U_NEFF','B4_FULL_SHAPE','B5_MAE_ONLY','B5_GLOBAL_RANK','B5_NOTIE']:
        d=[]
        for g in PLAN_CACHE['graphs']:
            k=(g['size'],g['seed'],'conflict-dense')
            if (*k,'B5_CONFLICT_RANK') in by and (*k,comp) in by:d.append(by[(*k,'B5_CONFLICT_RANK')]['delivered_fraction']-by[(*k,comp)]['delivered_fraction'])
        m,ci2=boot(d,int(FULL['bootstrap_seed'])+30+len(second)); second.append({'contrast':f'B5_CONFLICT_RANK-minus-{comp}','n_graphs':len(d),'mean_difference':m,'ci95':ci2,'wilcoxon_p':wp(d)})
    hp=holm([x['wilcoxon_p'] for x in second])
    for x,p in zip(second,hp):x['holm_p']=p
    report['secondary_conflict_dense']=second
    transfers={}
    for sid in ['persistent-degradation','partial-blockage']:
        d=[]
        for g in PLAN_CACHE['graphs']:
            k=(g['size'],g['seed'],sid)
            if (*k,'B5_CONFLICT_RANK') in by and (*k,'B3_U_ONLY') in by:d.append(by[(*k,'B5_CONFLICT_RANK')]['delivered_fraction']-by[(*k,'B3_U_ONLY')]['delivered_fraction'])
        m,ci2=boot(d,int(FULL['bootstrap_seed'])+50+len(transfers));transfers[sid]={'n_graphs':len(d),'mean_B5_minus_B3':m,'ci95':ci2}
    report['secondary_state_transfer']=transfers
    # Objective-aligned three-state composite. State weights are frozen in the placement model;
    # graph identity remains the inferential unit.
    wd=[]
    for g in PLAN_CACHE['graphs']:
        weights=g.get('state_weights',{})
        denom=sum(float(weights.get(s,0.0)) for s in D_CFG['states'])
        if denom<=0: continue
        b5=b3=0.0; ok=True
        for sid in D_CFG['states']:
            k=(g['size'],g['seed'],sid)
            if (*k,'B5_CONFLICT_RANK') not in by or (*k,'B3_U_ONLY') not in by: ok=False; break
            w=float(weights.get(sid,0.0))/denom
            b5 += w*by[(*k,'B5_CONFLICT_RANK')]['delivered_fraction']
            b3 += w*by[(*k,'B3_U_ONLY')]['delivered_fraction']
        if ok: wd.append(b5-b3)
    wm,wci=boot(wd,int(FULL['bootstrap_seed'])+60)
    report['objective_aligned_weighted_state_composite']={'contrast':'B5_CONFLICT_RANK-minus-B3_U_ONLY','n_graphs':len(wd),'mean_difference':wm,'ci95':wci,'supported':bool(wci[0]>0),'weights_source':'frozen scenario weights used by the placement objective'}
    dump(OUT/'RQ2_PACKET_SUMMARY.json',report); return report

def main():
    ap=argparse.ArgumentParser();ap.add_argument('command',choices=['build-plan','run','analyze']);ap.add_argument('--workers',type=int);a=ap.parse_args()
    if a.command=='build-plan':p=build_plan();print(json.dumps({'graphs':len(p['graphs']),'unique_cells':len(p['unique_cells'])},indent=2));return
    if a.command=='run':print(json.dumps(run(a.workers),indent=2));return
    print(json.dumps(analyze(),indent=2))
if __name__=='__main__':main()
