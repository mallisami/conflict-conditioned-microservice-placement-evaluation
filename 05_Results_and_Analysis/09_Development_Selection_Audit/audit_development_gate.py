#!/usr/bin/env python3
"""Reconstruct B3/B4 state-specific development baselines and matched regret.

Read-only audit. Does not fit a model or run ns-3/Kubernetes trials.
"""
from pathlib import Path
import argparse, ast, hashlib, json, sys, tempfile, zipfile
import numpy as np
import pandas as pd

EXPECTED_COEF='dff395f493c66880612e63b5cdc7bf970c17d29f1f65a73e4ea4f40a36d53e2c'
EXPECTED_NESTED_ZIP='9370074d3baf94451e76b11f7792d43ad2ad2bffd125fd033aae147929071107'
EXPECTED_DEV={
'B4_ORACLE_CANDIDATES.csv':'2689e7271a6a0ad26edc69d0519d52e43358ef97992f8a1cb6bd475cca1d1810',
'B4_RANDOM_GRAPH_SELECTIONS.csv':'259334d23415bd45d59f1a344a12e458627494393f74b8c9764ac5ee4390f7b9',
'B4_STAGE_D_GRAPH_METHOD_STATE.csv':'03784c84d3230d1a55b3531e6fe4169c6d89def3704105ec5ac41cec7a6999ce',
'B4_STRUCTURED_GRAPH_METHOD.csv':'b80de334c3ce2793ae20e5828727de9f195043bac3f68b84f83f0061887319ed'}
METHOD_COL={'B0_AFFINITY_ADMISSION':'selected_B0','B1_MAPE_CAP_WS':'selected_B1','B2_MAX_HEADROOM':'selected_B2','B3_U_ONLY':'selected_B3','A1_U_NEFF':'selected_A1','B4_FULL_SHAPE':'selected_B4'}
def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def safe_extract(zpath,dest):
    with zipfile.ZipFile(zpath) as z:
        for m in z.infolist():
            target=(dest/m.filename).resolve()
            if not str(target).startswith(str(dest.resolve())+'/'): raise RuntimeError('Unsafe ZIP path '+m.filename)
        z.extractall(dest)
def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--inputs-dir',type=Path,default=Path(__file__).resolve().parent/'inputs')
    ap.add_argument('--out-dir',type=Path,default=Path(__file__).resolve().parent/'outputs')
    a=ap.parse_args(); inp=a.inputs_dir; out=a.out_dir; out.mkdir(parents=True,exist_ok=True)
    science=inp/'PAPER2_COMPLETE_POSTCONFIRMATORY_EXPERIMENT_HYBRID_1152_20261016.zip'
    for fn,expected in EXPECTED_DEV.items():
        got=sha(inp/fn)
        if got!=expected: raise RuntimeError(f'Development CSV hash mismatch {fn}: {got}')
    science_hash=sha(science)
    if science_hash!=EXPECTED_NESTED_ZIP: raise RuntimeError(f'Nested science ZIP hash mismatch: {science_hash}')
    with tempfile.TemporaryDirectory(prefix='mape_b5_gate_v13_') as td:
        tmp=Path(td); safe_extract(science,tmp)
        roots=list(tmp.glob('*/RQ3_EXPERIMENT'))
        if len(roots)!=1: raise RuntimeError(f'Expected one RQ3_EXPERIMENT root, found {len(roots)}')
        root=roots[0]; coeff=root/'b3_lock/frozen_coefficients.json'; lock_path=root/'b5_lock/B5_MODEL_LOCK.json'; cv_path=root/'b5_lock/B5_DEVELOPMENT_CV_AUDIT.json'
        if sha(coeff)!=EXPECTED_COEF: raise RuntimeError('Frozen coefficient SHA-256 mismatch')
        lock=json.loads(lock_path.read_text()); cv=json.loads(cv_path.read_text()); coeff_sha=sha(coeff); lock_sha=sha(lock_path)
        for fn,expected in EXPECTED_DEV.items():
            if lock['development_sources'].get(fn)!=expected: raise RuntimeError('B5 model-lock source hash mismatch '+fn)
        sys.path.insert(0,str(root/'src')); sys.path.insert(0,str(root/'deps'))
        import run_stage_c as C
        coeffs=json.loads(coeff.read_text())
        od=pd.read_csv(inp/'B4_ORACLE_CANDIDATES.csv'); dense=[]; checks=0
        for seed in sorted(int(x) for x in od.seed.unique()):
            p,cal=C.build_scaled_problem('n8',seed)
            if p is None: raise RuntimeError(f'Could not reconstruct seed {seed}: {cal}')
            rows=od[od.seed==seed].sort_values('candidate_index').reset_index(drop=True); ci=0
            for pl,mv in C.candidates(p,p.max_relocations or 0):
                if not C.cluster_ok(p,pl): continue
                ev=C.evaluate_placement(p,pl,C.RISK)
                if not ev.feasible: continue
                rr=rows.iloc[ci]
                if int(rr['candidate_index'])!=ci: raise RuntimeError(f'Candidate order mismatch seed={seed}, i={ci}')
                cs,detail=C.calibrated_scores(p,pl,coeffs)
                for col,key in [('B3','B3_U_ONLY'),('B4','B4_FULL_SHAPE')]:
                    if abs(float(rr[col])-float(cs[key]))>=1e-10: raise RuntimeError(f'{col} composite mismatch seed={seed}, i={ci}')
                    checks+=1
                st=detail['conflict-dense']['predicted_loss_fraction']
                dense.append({'size':'n8','seed':seed,'state':'conflict-dense','candidate_index':ci,
                    'placement_key':repr(C.pkey(pl)),'loss':1-float(rr['observed_D']),
                    'B3_composite':float(cs['B3_U_ONLY']),'B4_composite':float(cs['B4_FULL_SHAPE']),
                    'B3':float(st['B3_U_ONLY']),'B4':float(st['B4_FULL_SHAPE']),
                    'b1_obj':float(ev.total_objective),'moves':int(mv),'source':'dense_oracle'})
                ci+=1
            if ci!=len(rows): raise RuntimeError(f'Candidate count mismatch seed={seed}: {ci}!={len(rows)}')
        dense=pd.DataFrame(dense)
    if len(dense)!=1038 or checks!=2076: raise RuntimeError(f'Unexpected dense count/checks {len(dense)}/{checks}')
    sc=pd.read_csv(inp/'B4_RANDOM_GRAPH_SELECTIONS.csv'); sd=pd.read_csv(inp/'B4_STAGE_D_GRAPH_METHOD_STATE.csv')
    by={(r['size'],int(r['seed'])):r for _,r in sc.iterrows()}; oracle_seeds=set(od.seed.astype(int)); uniq={}
    for _,r in sd.iterrows():
        size=r['size']; seed=int(r['seed']); state=r['state']
        if size=='n8' and seed in oracle_seeds and state=='conflict-dense': continue
        sr=by[(size,seed)]; sel=ast.literal_eval(sr[METHOD_COL[r['method']]])
        preds=sel['contention'][state].get('predicted_loss_fraction',{})
        key=(size,seed,state,repr(sel['placement_key']))
        item={'size':size,'seed':seed,'state':state,'placement_key':repr(sel['placement_key']),
            'loss':1-float(r['delivered_fraction']),'B3':float(preds.get('B3_U_ONLY',np.nan)),
            'B4':float(preds.get('B4_FULL_SHAPE',np.nan)),'b1_obj':float(sel.get('mape_objective',0.0)),
            'moves':int(sel.get('moves',0)),'source':'selected'}
        if key not in uniq: uniq[key]=item
        elif abs(uniq[key]['loss']-item['loss'])>1e-10: raise RuntimeError('Duplicate selected outcome mismatch')
    selected=pd.DataFrame(list(uniq.values()))
    if len(selected)!=1090: raise RuntimeError(f'Unexpected selected rows {len(selected)}')
    dense['source']='dense_oracle'; allrows=pd.concat([dense,selected],ignore_index=True)
    if len(allrows)!=2128 or allrows.groupby(['size','seed','state']).ngroups!=360: raise RuntimeError('Full development support mismatch')
    b5=cv['chosen_primary']; b5_mae=float(b5['cv_mae']); b5_strict=float(b5['cv_strict_selection_regret'])
    delta=float(b5['near_margin']['near_margin']); b5_near=float(b5['near_margin']['oof_mean_selection_regret'])
    # MAE rows: preserve both historical mixed calculation and corrected state-specific comparison.
    metrics=[]
    def add(name,df,b3,b4,b5v,note):
        metrics.append({'subset':name,'rows':len(df),'graph_state_groups':df.groupby(['size','seed','state']).ngroups,
            'B3_MAE':b3,'B4_MAE':b4,'B5_OOF_MAE':b5v,'interpretation':note})
    add('dense_oracle_composite_vs_state_loss',dense,np.mean(abs(dense.B3_composite-dense.loss)),np.mean(abs(dense.B4_composite-dense.loss)),np.nan,'Invalid semantics: composite score vs conflict-dense loss')
    add('dense_oracle_state_specific',dense,np.mean(abs(dense.B3-dense.loss)),np.mean(abs(dense.B4-dense.loss)),np.nan,'Aligned state-specific predictions and conflict-dense target')
    add('selected_state_specific',selected,np.mean(abs(selected.B3-selected.loss)),np.mean(abs(selected.B4-selected.loss)),np.nan,'Aligned state-specific selected-placement predictions')
    old_b3=np.mean(abs(np.concatenate([dense.B3_composite.to_numpy()-dense.loss.to_numpy(),selected.B3.to_numpy()-selected.loss.to_numpy()])))
    old_b4=np.mean(abs(np.concatenate([dense.B4_composite.to_numpy()-dense.loss.to_numpy(),selected.B4.to_numpy()-selected.loss.to_numpy()])))
    cor_b3=np.mean(abs(allrows.B3-allrows.loss)); cor_b4=np.mean(abs(allrows.B4-allrows.loss))
    add('pooled_historical_lock_mixed_semantics',allrows,old_b3,old_b4,np.nan,'Reproduces lock values; mixes composite and state-specific predictions')
    add('pooled_corrected_state_specific',allrows,cor_b3,cor_b4,np.nan,'Corrected state-specific baselines on same 2,128 rows')
    metrics.append({'subset':'B5_selected_primary_OOF_CV','rows':2128,'graph_state_groups':360,'B3_MAE':np.nan,'B4_MAE':np.nan,'B5_OOF_MAE':b5_mae,'interpretation':'Archived OOF metric selected through the same CV search; post-selection, not nested independent validation'})
    pd.DataFrame(metrics).to_csv(out/'development_gate_metrics.csv',index=False)
    dense.to_csv(out/'dense_oracle_state_specific_predictions.csv',index=False)
    selected.to_csv(out/'selected_state_specific_rows.csv',index=False)
    # Matched-policy baseline regret using the same fixed B5 near-margin delta and B1 tie-break.
    comp=[]
    for model in ['B3','B4']:
        strict=[]; near=[]
        for _,g in allrows.groupby(['size','seed','state'],sort=False):
            strict_ch=g.sort_values([model,'placement_key'],kind='mergesort').iloc[0]
            strict.append(float(strict_ch.loss-g.loss.min()))
            pmin=float(g[model].min()); eligible=g[g[model] <= pmin+delta+1e-15]
            near_ch=eligible.sort_values(['b1_obj','placement_key'],kind='mergesort').iloc[0]
            near.append(float(near_ch.loss-g.loss.min()))
        comp.append({'method':model,'state_specific_MAE':cor_b3 if model=='B3' else cor_b4,
            'strict_selection_regret':float(np.mean(strict)),'near_margin_regret_at_B5_delta':float(np.mean(near)),
            'near_margin_delta':delta,'candidate_support':'10 exhaustive dense N=8 groups; 350 selected-only groups','source':'reconstructed frozen predictions'})
    comp.append({'method':'B5','state_specific_MAE':b5_mae,'strict_selection_regret':b5_strict,
        'near_margin_regret_at_B5_delta':b5_near,'near_margin_delta':delta,
        'candidate_support':'Archived OOF; same heterogeneous 360-group support','source':'frozen B5_DEVELOPMENT_CV_AUDIT.json; not refitted'})
    compdf=pd.DataFrame(comp); compdf.to_csv(out/'matched_decision_gate_comparison.csv',index=False)
    g_dense=dense.groupby(['size','seed','state']).size(); g_sel=selected.groupby(['size','seed','state']).size(); counts=g_sel.value_counts().sort_index()
    support=[{'candidate_support':'Exhaustive dense-oracle candidate sets','group_count':len(g_dense),'rows':len(dense),'meaning':f'{int(g_dense.min())} to {int(g_dense.max())} candidates per group'}]
    for n,num in counts.items(): support.append({'candidate_support':f'Selected-only groups with {n} candidate(s)','group_count':int(num),'rows':int(n*num),'meaning':'Regret zero by construction' if n==1 else f'Best of {n} previously selected placements only'})
    pd.DataFrame(support).to_csv(out/'decision_support_groups.csv',index=False)
    report={'source_nested_zip_sha256':science_hash,'frozen_coefficients_sha256':coeff_sha,'b5_model_lock_sha256':lock_sha,
        'development_csv_hashes':{fn:sha(inp/fn) for fn in EXPECTED_DEV},'development_csv_hashes_match_model_lock':True,
        'dense_oracle_rows':len(dense),'dense_graphs':len(g_dense),'composite_score_checks':checks,'composite_score_tolerance':1e-10,
        'selected_rows':len(selected),'selected_only_groups':len(g_sel),'total_rows':len(allrows),'total_groups':allrows.groupby(['size','seed','state']).ngroups,
        'single_candidate_groups':int((g_sel==1).sum()),'B3_corrected_state_specific_MAE':float(cor_b3),'B4_corrected_state_specific_MAE':float(cor_b4),
        'B5_archived_OOF_MAE':b5_mae,'B5_minus_B3_MAE':b5_mae-float(cor_b3),'B5_minus_B4_MAE':b5_mae-float(cor_b4),
        'B3_strict_regret':float(compdf.loc[compdf.method=='B3','strict_selection_regret'].iloc[0]),
        'B4_strict_regret':float(compdf.loc[compdf.method=='B4','strict_selection_regret'].iloc[0]),
        'B5_strict_regret_archived':b5_strict,'B3_near_regret_at_B5_delta':float(compdf.loc[compdf.method=='B3','near_margin_regret_at_B5_delta'].iloc[0]),
        'B4_near_regret_at_B5_delta':float(compdf.loc[compdf.method=='B4','near_margin_regret_at_B5_delta'].iloc[0]),
        'B5_near_regret_archived':b5_near,'B5_near_margin_delta':delta,
        'model_fit_performed':False,'ns3_or_kubernetes_trials_performed':False,
        'interpretation':'Corrected development metrics remain numerically favorable to B5 on this development pool, but are post-selection OOF/heterogeneous-support evidence and do not override held-out RQ1 or confirmatory RQ2/RQ3.'}
    (out/'reconstruction_verification.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))
if __name__=='__main__': main()
