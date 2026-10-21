#!/usr/bin/env python3
"""Fit and freeze B5 from completed B4 evidence only.

This script is DEVELOPMENT ONLY. Confirmatory runners never call it.  It uses
historical B4 decisions plus the dense ten-graph ns-3 oracle to freeze a
parsimonious conflict-conditioned score, training-objective/global-feature
ablations, and the uncertainty-aware B1 tie-break margin.
"""
from __future__ import annotations
import ast, hashlib, itertools, json, sys
from pathlib import Path
import numpy as np
from scipy.optimize import minimize
from scipy.special import expit

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src')); sys.path.insert(0,str(ROOT/'deps'))
import run_stage_c as C
import b5_model as B

DEV=ROOT/'development_reference'; OUT=ROOT/'b5_lock'
METHOD_COL={
    'B0_AFFINITY_ADMISSION':'selected_B0','B1_MAPE_CAP_WS':'selected_B1',
    'B2_MAX_HEADROOM':'selected_B2','B3_U_ONLY':'selected_B3',
    'A1_U_NEFF':'selected_A1','B4_FULL_SHAPE':'selected_B4'
}
CV_SEED=20261009; HUBER_DELTA=0.01; SESOI=0.005
PRIMARY_FEATURES=('intercept','u_pair_interaction')
GLOBAL_ABLATION_FEATURES=('intercept','u_global_pair_interaction')


def sha(p:Path)->str:
    h=hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda:f.read(1<<20),b''): h.update(b)
    return h.hexdigest()

def dump(p:Path,o):
    p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(json.dumps(o,indent=2,sort_keys=True)+'\n',encoding='utf-8')

def vec(d,names): return np.asarray([float(d[k]) for k in names],dtype=float)

def _feature_dicts_from_contention(detail):
    groups=detail.get('groups',{}); total=float(detail.get('total_cross_bits',0.0))
    return B.conflict_feature_dict_from_groups(groups,total), B.global_feature_dict_from_groups(groups,total)


def historical_selected():
    import pandas as pd
    sc=pd.read_csv(DEV/'B4_RANDOM_GRAPH_SELECTIONS.csv')
    sd=pd.read_csv(DEV/'B4_STAGE_D_GRAPH_METHOD_STATE.csv')
    by={(r['size'],int(r['seed'])):r for _,r in sc.iterrows()}; uniq={}
    for _,r in sd.iterrows():
        sr=by[(r['size'],int(r['seed']))]
        sel=ast.literal_eval(sr[METHOD_COL[r['method']]])
        state=sel['contention'][r['state']]
        fc,fg=_feature_dicts_from_contention(state)
        k=(r['size'],int(r['seed']),r['state'],repr(sel['placement_key']))
        preds=state.get('predicted_loss_fraction',{})
        rec={
            'size':r['size'],'seed':int(r['seed']),'state':r['state'],
            'placement_key':repr(sel['placement_key']),
            'loss':1.0-float(r['delivered_fraction']),
            'features_conflict':fc,'features_global':fg,
            'b1_obj':float(sel.get('mape_objective',0.0)),
            'legacy_b3':float(preds.get('B3_U_ONLY',np.nan)),
            'legacy_b4':float(preds.get('B4_FULL_SHAPE',np.nan)),
            'source':'selected'
        }
        if k not in uniq: uniq[k]=rec
        elif abs(uniq[k]['loss']-rec['loss'])>1e-10:
            raise RuntimeError('historical duplicate loss mismatch')
    return list(uniq.values())


def dense_oracle():
    import pandas as pd
    od=pd.read_csv(DEV/'B4_ORACLE_CANDIDATES.csv'); out=[]
    for seed in sorted(int(x) for x in od.seed.unique()):
        p,_=C.build_scaled_problem('n8',seed)
        sc=next(s for s in p.scenarios if s.scenario_id=='conflict-dense')
        rows=od[od.seed==seed].sort_values('candidate_index').reset_index(drop=True); ci=0
        for pl,mv in C.candidates(p,p.max_relocations or 0):
            if not C.cluster_ok(p,pl): continue
            ev=C.evaluate_placement(p,pl,C.RISK)
            if not ev.feasible: continue
            rr=rows.iloc[ci]
            if int(rr['candidate_index'])!=ci: raise RuntimeError('oracle candidate order mismatch')
            groups,total=B.state_group_detail(p,pl,sc)
            fc=B.conflict_feature_dict_from_groups(groups,total)
            fg=B.global_feature_dict_from_groups(groups,total)
            out.append({
                'size':'n8','seed':seed,'state':'conflict-dense',
                'placement_key':repr(C.pkey(pl)),
                'loss':1.0-float(rr['observed_D']),
                'features_conflict':fc,'features_global':fg,
                'b1_obj':float(ev.total_objective),
                'legacy_b3':float(rr['B3']),'legacy_b4':float(rr['B4']),
                'source':'dense_oracle'
            })
            ci+=1
        if ci!=len(rows): raise RuntimeError(f'oracle reconstruction count mismatch {seed}: {ci}!={len(rows)}')
    return out


def dataset():
    sel=historical_selected(); oracle=dense_oracle(); oseeds={x['seed'] for x in oracle}
    # Dense oracle rows replace the sparse selected-placement rows for the same
    # n8/conflict-dense development graph-state group.
    return list(oracle)+[x for x in sel if not (x['size']=='n8' and x['seed'] in oseeds and x['state']=='conflict-dense')]


def groups_and_pairs(rows):
    groups={}
    for i,r in enumerate(rows): groups.setdefault((r['size'],r['seed'],r['state']),[]).append(i)
    pairs=[]
    for idxs in groups.values():
        for a,b in itertools.combinations(idxs,2):
            dy=rows[a]['loss']-rows[b]['loss']
            if abs(dy)<=1e-12: continue
            pairs.append((a,b,1.0 if dy>0 else -1.0,min(abs(dy)/SESOI,1.0)))
    return groups,pairs


def matrix(rows,feature_set,names):
    key='features_conflict' if feature_set=='conflict' else 'features_global'
    return np.vstack([vec(r[key],names) for r in rows])


def fit(rows,train_idx,feature_set,names,pairs,lam,gamma,tau):
    X=matrix(rows,feature_set,names); y=np.asarray([r['loss'] for r in rows],float)
    mask=np.zeros(len(rows),bool); mask[train_idx]=True
    tp=[p for p in pairs if mask[p[0]] and mask[p[1]]]
    Xtr=X[train_idx]; ytr=y[train_idx]
    init=np.linalg.lstsq(Xtr,ytr,rcond=None)[0]
    ia=np.asarray([p[0] for p in tp],int); ib=np.asarray([p[1] for p in tp],int)
    ss=np.asarray([p[2] for p in tp],float); ww=np.asarray([p[3] for p in tp],float)
    xd=X[ia]-X[ib] if len(tp) else np.empty((0,X.shape[1]))
    def fg(beta):
        pred=Xtr@beta; resid=ytr-pred; ar=np.abs(resid)
        hl=np.where(ar<=HUBER_DELTA,.5*resid*resid,HUBER_DELTA*(ar-.5*HUBER_DELTA))
        lp=float(hl.mean()/(HUBER_DELTA*HUBER_DELTA))
        dldp=np.where(ar<=HUBER_DELTA,-resid,-HUBER_DELTA*np.sign(resid))/(HUBER_DELTA*HUBER_DELTA)
        gp=(Xtr.T@dldp)/len(ytr)
        if len(tp):
            z=-ss*(xd@beta)/tau
            lr=float(np.mean(ww*np.logaddexp(0,z)))
            fac=ww*expit(z)*(-ss/tau); gr=(xd.T@fac)/len(tp)
        else:
            lr=0.0; gr=np.zeros_like(beta)
        penalty=gamma*np.dot(beta[1:],beta[1:])
        grad_pen=np.r_[0.0,2*gamma*beta[1:]]
        return (1-lam)*lp+lam*lr+penalty,(1-lam)*gp+lam*gr+grad_pen
    # B5 is physically monotone in every non-intercept exposure feature.
    bounds=[(None,None)]+[(0.0,None)]*(len(names)-1)
    for j in range(1,len(init)): init[j]=max(0.0,float(init[j]))
    res=minimize(lambda b:fg(b),init,jac=True,method='L-BFGS-B',bounds=bounds,options={'maxiter':1000})
    if not res.success: raise RuntimeError('B5 optimizer failed: '+str(res.message))
    return res.x


def fold_map(rows):
    seeds=sorted({int(r['seed']) for r in rows}); rng=np.random.default_rng(CV_SEED)
    arr=np.asarray(seeds); rng.shuffle(arr); folds=np.array_split(arr,5)
    return {int(s):i for i,a in enumerate(folds) for s in a}


def evaluate_oof(rows,feature_set,names,lam,gamma,tau):
    groups,pairs=groups_and_pairs(rows); sf=fold_map(rows)
    X=matrix(rows,feature_set,names); y=np.asarray([r['loss'] for r in rows],float); pred=np.empty(len(rows))
    for fi in range(5):
        tr=np.asarray([i for i,r in enumerate(rows) if sf[int(r['seed'])]!=fi])
        va=np.asarray([i for i,r in enumerate(rows) if sf[int(r['seed'])]==fi])
        beta=fit(rows,tr,feature_set,names,pairs,lam,gamma,tau)
        pred[va]=np.clip(X[va]@beta,0,1)
    absres=np.abs(pred-y)
    strict=[]
    for idxs in groups.values():
        ch=min(idxs,key=lambda i:(pred[i],rows[i]['placement_key']))
        strict.append(y[ch]-min(y[i] for i in idxs))
    near_grid=[]
    for q in [0.0,0.10,0.25,0.50,0.75]:
        delta=0.0 if q==0 else min(SESOI,float(np.quantile(absres,q)))
        regs=[]
        for idxs in groups.values():
            pmin=min(pred[i] for i in idxs)
            eligible=[i for i in idxs if pred[i]<=pmin+delta+1e-15]
            ch=min(eligible,key=lambda i:(rows[i]['b1_obj'],rows[i]['placement_key']))
            regs.append(y[ch]-min(y[i] for i in idxs))
        near_grid.append({'quantile':q,'near_margin':delta,'oof_mean_selection_regret':float(np.mean(regs))})
    near=min(near_grid,key=lambda x:(x['oof_mean_selection_regret'],x['near_margin']))
    return {
        'lambda':lam,'gamma':gamma,'tau':tau,
        'cv_mae':float(np.mean(absres)),
        'cv_strict_selection_regret':float(np.mean(strict)),
        'near_margin':near,
        'near_margin_grid':near_grid,
        'oof_abs_residual_quantiles':{
            'median':float(np.quantile(absres,.5)),
            'q75':float(np.quantile(absres,.75)),
            'q90':float(np.quantile(absres,.9))
        }
    }


def legacy_baselines(rows):
    groups,_=groups_and_pairs(rows); y=np.asarray([r['loss'] for r in rows],float)
    out={}
    for label,key in [('B3','legacy_b3'),('B4','legacy_b4')]:
        ae=[abs(float(r[key])-r['loss']) for r in rows if np.isfinite(float(r[key]))]
        regs=[]
        for idxs in groups.values():
            ch=min(idxs,key=lambda i:(float(rows[i][key]),rows[i]['placement_key']))
            regs.append(y[ch]-min(y[i] for i in idxs))
        out[label]={'mae':float(np.mean(ae)),'strict_selection_regret':float(np.mean(regs))}
    # Existing B1 selection is included as a context baseline only.
    regs=[]
    for idxs in groups.values():
        ch=min(idxs,key=lambda i:(rows[i]['b1_obj'],rows[i]['placement_key']))
        regs.append(y[ch]-min(y[i] for i in idxs))
    out['B1']={'strict_selection_regret':float(np.mean(regs))}
    return out


def choose_primary(rows,baselines):
    grid=[]
    for lam in [0.10,0.25,0.50]:
        for gamma in [1e-6,1e-4]:
            for tau in [0.01,0.02]:
                grid.append(evaluate_oof(rows,'conflict',PRIMARY_FEATURES,lam,gamma,tau))
    eligible=[x for x in grid if x['cv_mae']<=baselines['B4']['mae']+1e-12 and x['near_margin']['oof_mean_selection_regret']<=baselines['B4']['strict_selection_regret']+1e-12]
    if not eligible:
        raise RuntimeError('No primary B5 setting passed both the B4 predictive and decision-quality development guards')
    chosen=min(eligible,key=lambda x:(x['near_margin']['oof_mean_selection_regret'],x['cv_mae'],x['lambda'],x['gamma'],x['tau']))
    return chosen,grid


def choose_ablation(rows,feature_set,names,lambdas):
    grid=[]
    for lam in lambdas:
        for gamma in [1e-6,1e-4]:
            for tau in [0.01,0.02]:
                grid.append(evaluate_oof(rows,feature_set,names,lam,gamma,tau))
    return min(grid,key=lambda x:(x['near_margin']['oof_mean_selection_regret'],x['cv_mae'],x['gamma'],x['tau'])),grid


def main():
    OUT.mkdir(parents=True,exist_ok=True)
    rows=dataset(); groups,pairs=groups_and_pairs(rows); baselines=legacy_baselines(rows)
    primary,primary_grid=choose_primary(rows,baselines)
    mae_only,mae_grid=choose_ablation(rows,'conflict',PRIMARY_FEATURES,[0.0])
    global_rank,global_grid=choose_ablation(rows,'global',GLOBAL_ABLATION_FEATURES,[0.10,0.25,0.50])
    allidx=np.arange(len(rows))
    b5=fit(rows,allidx,'conflict',PRIMARY_FEATURES,pairs,primary['lambda'],primary['gamma'],primary['tau'])
    b5_mae=fit(rows,allidx,'conflict',PRIMARY_FEATURES,pairs,0.0,mae_only['gamma'],mae_only['tau'])
    b5_global=fit(rows,allidx,'global',GLOBAL_ABLATION_FEATURES,pairs,global_rank['lambda'],global_rank['gamma'],global_rank['tau'])
    near=primary['near_margin']
    lock={
        'status':'FROZEN_PRE_CONFIRMATION',
        'model_id':'B5_conflict_conditioned_decision_aware_v1.0',
        'development_only':True,
        'development_sources':{p.name:sha(p) for p in sorted(DEV.glob('*.csv'))},
        'development_rows':len(rows),'development_graph_state_groups':len(groups),'dense_oracle_graphs':10,
        'cv_seed':CV_SEED,'pointwise_huber_delta':HUBER_DELTA,'pair_weight_scale':SESOI,
        'development_baselines':baselines,
        'development_gate':{
            'required_primary_cv_mae_le_B4':baselines['B4']['mae'],
            'required_primary_oof_near_regret_le_B4_strict':baselines['B4']['strict_selection_regret'],
            'passed':True
        },
        'hyperparameter_selection':{k:primary[k] for k in ['lambda','gamma','tau','cv_mae','cv_strict_selection_regret']},
        'selection':{
            'near_margin':near['near_margin'],'near_margin_quantile':near['quantile'],
            'oof_selection_regret':near['oof_mean_selection_regret'],
            'candidate_grid':primary['near_margin_grid'],
            'tie_break':'B1_MAPE_CAP_WS objective, then moves, then placement key; only inside frozen B5 near-margin',
            'same_margin_applied_to_feature/training ablations':True
        },
        'models':{
            'B5_CONFLICT_RANK':{
                'feature_set':'conflict','feature_names':list(PRIMARY_FEATURES),
                'coefficients':[float(x) for x in b5],
                'coefficient_constraints':'intercept free; every exposure coefficient non-negative',
                'lambda':primary['lambda'],'gamma':primary['gamma'],'tau':primary['tau']
            },
            'B5_MAE_ONLY':{
                'feature_set':'conflict','feature_names':list(PRIMARY_FEATURES),
                'coefficients':[float(x) for x in b5_mae],
                'coefficient_constraints':'intercept free; every exposure coefficient non-negative',
                'lambda':0.0,'gamma':mae_only['gamma'],'tau':mae_only['tau']
            },
            'B5_GLOBAL_RANK':{
                'feature_set':'global','feature_names':list(GLOBAL_ABLATION_FEATURES),
                'coefficients':[float(x) for x in b5_global],
                'coefficient_constraints':'intercept free; every exposure coefficient non-negative',
                'lambda':global_rank['lambda'],'gamma':global_rank['gamma'],'tau':global_rank['tau']
            }
        },
        'development_only_note':'All historical B4 outcomes are development evidence. No development graph/shape/seed may be counted as B5 confirmatory evidence.'
    }
    p=OUT/'B5_MODEL_LOCK.json'; dump(p,lock)
    (OUT/'B5_MODEL_LOCK.sha256').write_text(sha(p)+'  B5_MODEL_LOCK.json\n',encoding='utf-8')
    audit={
        'primary_feature_definition':list(PRIMARY_FEATURES),
        'global_ablation_feature_definition':list(GLOBAL_ABLATION_FEATURES),
        'primary_grid':primary_grid,'chosen_primary':primary,
        'mae_only_grid':mae_grid,'chosen_mae_only':mae_only,
        'global_grid':global_grid,'chosen_global':global_rank,
        'legacy_development_baselines':baselines,
        'development_gate':lock['development_gate']
    }
    dump(OUT/'B5_DEVELOPMENT_CV_AUDIT.json',audit)
    print(json.dumps({'lock':str(p),'sha256':sha(p),'chosen':primary,'baselines':baselines,'rows':len(rows),'groups':len(groups)},indent=2))

if __name__=='__main__': main()
