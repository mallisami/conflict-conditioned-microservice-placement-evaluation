#!/usr/bin/env python3
from __future__ import annotations
import argparse,csv,hashlib,json,math,os,random,shutil,statistics,sys,time,zipfile
from concurrent.futures import ProcessPoolExecutor,as_completed
from dataclasses import replace
from pathlib import Path
from typing import Any
import numpy as np
from scipy.stats import wilcoxon

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'));sys.path.insert(0,str(ROOT/'stage_e_support'));sys.path.insert(0,str(ROOT/'deps'))
import run_stage_e as E
import rq3_selector as S
import live_confirmatory as lc
from mape_cap_bplus.models import NodeSpec

CFG=json.loads((ROOT/'config/rq3_extension.json').read_text())
OUT=ROOT/'rq3_results'; PRE=ROOT/'PRE_RUN_FREEZE'; SEL=PRE/'selection_graphs'; SCI=OUT/'science'; TIMEOUT_MS=3000.0
METHOD_INTERNAL={'B3_STRICT':'B3_STRICT','B3_STABILIZED':'B3_STABILIZED','B5_NOTIE':'B5_NOTIE','B5_COMPLETE':'B5_COMPLETE'}

def dump(p:Path,o:Any):
    p.parent.mkdir(parents=True,exist_ok=True);tmp=p.with_suffix(p.suffix+'.tmp');tmp.write_text(json.dumps(o,indent=2,sort_keys=True,default=str),encoding='utf-8');os.replace(tmp,p)
def sha(p:Path)->str:return hashlib.sha256(p.read_bytes()).hexdigest()
def panel(seed:int)->str:return 'A' if int(CFG['panel_a']['seed_start'])<=seed<=int(CFG['panel_a']['seed_end']) else 'B'
def methods_for(seed:int)->list[str]:return list(CFG['panel_a']['methods'] if panel(seed)=='A' else CFG['panel_b']['methods'])
def all_seeds()->list[int]:return list(range(int(CFG['panel_a']['seed_start']),int(CFG['panel_b']['seed_end'])+1))

def verify_payload_locks():
    b3=json.loads((ROOT/'b3_lock/frozen_coefficients.json').read_text()); b5=json.loads((ROOT/'b5_lock/B5_MODEL_LOCK.json').read_text()); load=json.loads((ROOT/'b5_lock/STAGE_E_LOAD_LOCK.json').read_text()); lock=json.loads((ROOT/'SCIENTIFIC_PAYLOAD_LOCK.json').read_text())
    got={k:v['B3_U_only'] for k,v in b3['fits'].items()}
    if got!=lock['b3_scientific_payload']:raise RuntimeError('B3 scientific coefficient payload mismatch')
    if b5['models']['B5_CONFLICT_RANK']['coefficients']!=lock['b5_primary_coefficients']:raise RuntimeError('B5 coefficient payload mismatch')
    if float(b5['selection']['near_margin'])!=float(lock['near_margin']):raise RuntimeError('B5 near margin mismatch')
    if load.get('status')!='FROZEN_PRE_RQ3' or bool(load.get('B5_evaluated')):raise RuntimeError('Stage-E load lock provenance invalid')
    if float(load['multipliers']['high'])!=float(CFG['load_multiplier']):raise RuntimeError('high-load multiplier mismatch')
    # cryptographic locks where exact bytes were frozen
    for fname in ['B5_MODEL_LOCK','STAGE_E_LOAD_LOCK.json']:
        if fname=='B5_MODEL_LOCK': p=ROOT/'b5_lock/B5_MODEL_LOCK.json'; hp=ROOT/'b5_lock/B5_MODEL_LOCK.sha256'
        else: p=ROOT/'b5_lock/STAGE_E_LOAD_LOCK.json'; hp=ROOT/'b5_lock/STAGE_E_LOAD_LOCK.json.sha256'
        token=hp.read_text().strip().split()[0]
        if sha(p)!=token:raise RuntimeError(f'{p.name} hash mismatch')
    return {'b3_file_sha256':sha(ROOT/'b3_lock/frozen_coefficients.json'),'b5_lock_sha256':sha(ROOT/'b5_lock/B5_MODEL_LOCK.json'),'stage_e_load_lock_sha256':sha(ROOT/'b5_lock/STAGE_E_LOAD_LOCK.json'),'scientific_payload_lock_sha256':sha(ROOT/'SCIENTIFIC_PAYLOAD_LOCK.json')}

def selector_reproduction_gate():
    refs=json.loads((ROOT/'PROVENANCE/reference_stage_e_selections_98001_98040.json').read_text()); mism=[]
    for s in CFG['historical_reproduction_seeds']:
        got=S.solve_seed(int(s));exp=refs[str(s)]
        if got.get('x_adm_sha256')!=exp['x_adm_sha256'] or int(got.get('n_admissible',-1))!=int(exp['n_admissible']):mism.append({'seed':s,'field':'admissible_set'})
        for m in ['B3_STRICT','B5_NOTIE','B5_COMPLETE']:
            if got['selections'][m]['placement']!=exp[m]:mism.append({'seed':s,'method':m,'got':got['selections'][m]['placement'],'expected':exp[m]})
    if mism:raise RuntimeError(f'historical selector reproduction failed: {mism[:3]}')
    rec={'passed':True,'seeds':len(CFG['historical_reproduction_seeds']),'methods_reproduced':['B3_STRICT','B5_NOTIE','B5_COMPLETE'],'mismatches':0}
    dump(OUT/'HISTORICAL_SELECTOR_REPRODUCTION_GATE.json',rec);return rec

def build_selections(workers:int|None=None):
    # Selections are already frozen in the distributed package. This command validates, never regenerates them.
    expected=all_seeds();missing=[s for s in expected if not (SEL/f'n8-{s}.json').exists()]
    if missing:raise RuntimeError(f'frozen selection file(s) missing: {missing[:10]}')
    # Verify per-file frozen hashes.
    manifest={}
    for line in (PRE/'SELECTION_SHA256SUMS.txt').read_text().splitlines():
        if line.strip():
            h,rel=line.split('  ',1);manifest[rel]=h
    for seed in expected:
        q=SEL/f'n8-{seed}.json';rel=f'selection_graphs/{q.name}'
        if rel not in manifest or sha(q)!=manifest[rel]:raise RuntimeError(f'frozen selection hash mismatch: {q.name}')
    rows=[json.loads((SEL/f'n8-{s}.json').read_text()) for s in expected]
    bad=[r for r in rows if not r.get('valid') or r.get('no_admissible_placement')]
    if bad:raise RuntimeError(f'fresh panel structural eligibility failed: {[x.get("seed") for x in bad[:10]]}')
    counts=[int(r['n_admissible']) for r in rows]
    rec={'passed':True,'frozen_package_selections':True,'n':len(rows),'seed_min':min(expected),'seed_max':max(expected),'admissible_set_min':min(counts),'admissible_set_max':max(counts),'admissible_set_mean':float(np.mean(counts)),'bad':[]}
    frozen=json.loads((PRE/'FRESH_SELECTION_PREFLIGHT.json').read_text())
    for k in ['n','seed_min','seed_max','admissible_set_min','admissible_set_max']:
        if rec[k]!=frozen[k]:raise RuntimeError(f'frozen selection preflight mismatch on {k}: {rec[k]} != {frozen[k]}')
    dump(OUT/'FRESH_SELECTION_VALIDATION.json',rec);return rec

def generate_run_plan():
    p=PRE/'RUN_PLAN.json'
    if not p.exists():raise RuntimeError('frozen RUN_PLAN.json missing')
    obj=json.loads(p.read_text())
    expected=int(CFG['expected_science_cells'])
    if int(obj.get('n_cells',-1))!=expected or len(obj.get('cells',[]))!=expected:raise RuntimeError(f'frozen run plan does not contain {expected} cells')
    ids={(int(c['seed']),int(c['replicate']),str(c['method'])) for c in obj['cells']}
    if len(ids)!=expected:raise RuntimeError('duplicate cell identities in frozen run plan')
    rep1=sum(1 for c in obj['cells'] if int(c['replicate'])==1)
    extra=sum(1 for c in obj['cells'] if int(c['replicate']) in (2,3))
    if rep1!=768 or extra!=384:raise RuntimeError(f'hybrid run-plan accounting mismatch: rep1={rep1}, extra={extra}')
    return obj

def configure_upstream_stage_e():
    # Preserve original Stage-E implementation while replacing only extension-specific control values.
    E.CFG={**E.CFG,'namespace':CFG['namespace'],'benchmark_image':CFG['benchmark_image'],'expected_kubelet_version':CFG['expected_kubelet_version'],'expected_architecture':CFG['expected_architecture'],'expected_os':CFG['expected_os'],'execution_cpu_request':CFG['execution_cpu_request'],'execution_memory_request_mb':CFG['execution_memory_request_mb'],'settle_seconds':CFG['settle_seconds'],'measurement_seconds':CFG['measurement_seconds'],'max_cell_attempts':CFG['max_cell_attempts']}
    E.OUT=OUT

def cluster_preflight():
    configure_upstream_stage_e();E.setup_lc();info=E.cluster_info();E.image_probe(info);fps=E.fingerprint_probe(info);medium=lc.ensure_wireless_medium(info)
    rec={'passed':True,'context':lc.CONTEXT,'cluster':info,'host_machine_id_sha256':fps,'medium':medium,'benchmark_image':lc.IMAGE,'load_multiplier':CFG['load_multiplier'],'science_endpoints_collected':0}
    dump(OUT/'CLUSTER_PREFLIGHT.json',rec);return rec

def execution_problem(seed:int,info:dict[str,Any]):
    # Exact frozen Stage-E problem construction, high-load multiplier only.
    p,cal=E.C.build_scaled_problem('n8',int(seed))
    if p is None:raise RuntimeError(f'cannot reconstruct n8/{seed}: {cal}')
    p=replace(p,flows=tuple(replace(f,requests_per_window=float(f.requests_per_window)*float(CFG['load_multiplier']),bits_per_window=float(f.bits_per_window)*float(CFG['load_multiplier'])) for f in p.flows),metadata={**p.metadata,'stage_e_load_multiplier':float(CFG['load_multiplier']),'rq3_extension':True})
    syn_by_rack={n.rack_id:n.node_id for n in p.nodes};node_map={syn_by_rack[rack]:node for rack,node in info['rack_to_node'].items()}
    nodes=tuple(NodeSpec(node_map[n.node_id],n.rack_id,100.0,100000.0) for n in p.nodes);allowed=tuple(n.node_id for n in nodes)
    reps=tuple(replace(r,allowed_nodes=allowed,cpu_request=float(CFG['execution_cpu_request']),memory_request_mb=float(CFG['execution_memory_request_mb'])) for r in p.replicas)
    current={rid:node_map[nid] for rid,nid in p.current_placement.items()}
    return replace(p,nodes=nodes,replicas=reps,current_placement=current,metadata={**p.metadata,'execution_only_reservations':True}),node_map

def selected_plan(seed:int,method:str,node_map:dict[str,str]):
    g=json.loads((SEL/f'n8-{seed}.json').read_text());pl=g['selections'][method]['placement'];return {rid:node_map[nid] for rid,nid in pl.items()}

def timeout_augmented_p95(traffic,metrics):
    vals=[]
    for pm in traffic.get('pod_metrics',{}).values():
        for row in pm.get('flows',{}).values():vals.extend(float(x) for x in row.get('latencies_ms',[]))
    missing=max(0,int(metrics['expected_scheduled_requests'])-len(vals));vals.extend([TIMEOUT_MS]*missing)
    return lc.nearest_rank(vals,.95) if vals else None

def cell_root(c):return SCI/f"panel-{c['panel']}"/f"seed-{c['seed']}"/c['method']/f"rep-{c['replicate']}"
def run_cell(c,info):
    root=cell_root(c);accepted=root/'accepted.json'
    if accepted.exists():
        d=json.loads(accepted.read_text())
        for k in ['panel','seed','replicate','method','load_regime']:
            if d.get(k)!=c.get(k):raise RuntimeError(f'accepted-cell identity mismatch {accepted}: field={k}')
        if not math.isclose(float(d.get('load_multiplier')),float(c.get('load_multiplier')),rel_tol=0,abs_tol=1e-12):
            raise RuntimeError(f'accepted-cell load mismatch {accepted}')
        return d
    # Retry budget is cumulative across relaunches. Existing failure.json files count as consumed
    # infrastructure attempts; this prevents a restarted launcher from silently exceeding the frozen budget.
    failed_attempts=[]
    if root.exists():
        for q in root.glob('attempt-*/failure.json'):
            try: failed_attempts.append(int(q.parent.name.split('-',1)[1]))
            except Exception: pass
    start_attempt=max(failed_attempts,default=0)+1
    max_attempts=int(CFG['max_cell_attempts'])
    if start_attempt>max_attempts:
        raise RuntimeError(f"RQ3 cell exhausted cumulative retry budget ({max_attempts}): {c}")
    problem,node_map=execution_problem(c['seed'],info);pl=selected_plan(c['seed'],c['method'],node_map);sc=next(s for s in problem.scenarios if s.scenario_id=='conflict-dense')
    for attempt in range(start_attempt,max_attempts+1):
        ad=root/f'attempt-{attempt}';ad.mkdir(parents=True,exist_ok=True)
        try:
            run_id=f"p2rq3:{c['panel']}:{c['seed']}:{c['method']}:{c['replicate']}:a{attempt}"
            rollout=lc.apply_placement(problem,pl,run_id);actual=lc.current_live_placement(problem)
            if actual!=pl:raise RuntimeError(f'actual pod placement mismatch: {actual} != {pl}')
            time.sleep(float(CFG['settle_seconds']))
            traffic=lc.configure_and_run_for_scenario(problem,pl,run_id,int(CFG['measurement_seconds']),sc)
            m=lc.aggregate_metrics(problem,pl,traffic);medium=traffic.get('wireless_medium_metrics',{}).get('metrics',{})
            if int(m['attempted_requests'])<=0:raise RuntimeError('zero attempted requests')
            if float(m['cross_rack_attempted_bytes'])>0 and int(medium.get('requests',0))<=0:raise RuntimeError('shared medium observed zero requests')
            health=lc.deployment_health(problem)
            if not health['healthy']:raise RuntimeError('deployment unhealthy after execution')
            rec={**c,'attempt':attempt,'accepted_infrastructure':True,'rollout':rollout,'metrics':m,'timeout_augmented_p95_ms':timeout_augmented_p95(traffic,m),'wireless_medium_metrics':medium,'placement':pl,'host_racks':info['rack_to_node']}
            dump(accepted,rec);return rec
        except Exception as e:
            dump(ad/'failure.json',{'error':f'{type(e).__name__}: {e}','accepted_infrastructure':False,'cell':c,'attempt':attempt});time.sleep(2)
    raise RuntimeError(f"RQ3 cell exhausted cumulative retry budget: {c}")

def accepted_count():return sum(1 for _ in SCI.glob('panel-*/seed-*/*/rep-*/accepted.json')) if SCI.exists() else 0

def run_science():
    plan=generate_run_plan();pre=json.loads((OUT/'CLUSTER_PREFLIGHT.json').read_text());info=pre['cluster']
    go={'science_run_authorized':True,'authorized_utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),'package_inputs':verify_payload_locks(),'historical_selector_gate':json.loads((OUT/'HISTORICAL_SELECTOR_REPRODUCTION_GATE.json').read_text()),'fresh_selection_preflight':json.loads((OUT/'FRESH_SELECTION_VALIDATION.json').read_text()),'cluster_preflight_sha256':sha(OUT/'CLUSTER_PREFLIGHT.json'),'run_plan_sha256':sha(PRE/'RUN_PLAN.json'),'expected_cells':plan['n_cells']}
    dump(OUT/'SCIENCE_GO_LOCK.json',go)
    for c in plan['cells']:
        run_cell(c,info)
        # Progress is deliberately endpoint-free.
        n=accepted_count();dump(OUT/'PROGRESS.json',{'accepted_cells':n,'expected_cells':plan['n_cells'],'complete':n==plan['n_cells']})
    if accepted_count()!=plan['n_cells']:raise RuntimeError('science execution ended without all frozen cells')

def boot(vals,seed):
    x=np.asarray(vals,float);rng=np.random.default_rng(seed);B=int(CFG['bootstrap_resamples']);chunks=[];left=B
    while left:
        n=min(5000,left);idx=rng.integers(0,len(x),(n,len(x)));chunks.append(x[idx].mean(axis=1));left-=n
    v=np.concatenate(chunks);return float(x.mean()),[float(np.quantile(v,.025)),float(np.quantile(v,.975))]
def wp(vals):
    a=np.asarray(vals,float);a=a[np.abs(a)>1e-12]
    return 1.0 if len(a)==0 else float(wilcoxon(a,alternative='two-sided').pvalue)
def wins(vals):
    a=np.asarray(vals,float);return {'wins':int((a>1e-12).sum()),'losses':int((a< -1e-12).sum()),'ties':int((np.abs(a)<=1e-12).sum())}
def holm(ps):
    order=sorted(range(len(ps)),key=lambda i:ps[i]);out=[1.0]*len(ps);running=0.0
    for j,i in enumerate(order):running=max(running,min(1.0,ps[i]*(len(ps)-j)));out[i]=running
    return out

def collect_rows():
    rows=[]
    for p in sorted(SCI.glob('panel-*/seed-*/*/rep-*/accepted.json')):
        d=json.loads(p.read_text());m=d['metrics'];dur=float(CFG['measurement_seconds']);q=d['wireless_medium_metrics'].get('queue_wait_ms',[])
        rows.append({'panel':d['panel'],'seed':int(d['seed']),'method':d['method'],'replicate':int(d['replicate']),'completion':float(m['scheduled_completion_fraction']),'ta_p95_ms':float(d['timeout_augmented_p95_ms']),'attempted_p95_ms':float(m['p95_ms']),'throughput_success_rps':float(m['successful_requests'])/dur,'errors':float(m['errors']),'medium_queue_wait_mean_ms':float(statistics.fmean(q)) if q else 0.0})
    return rows

def analyze():
    plan=generate_run_plan();rows=collect_rows()
    if len(rows)!=plan['n_cells']:raise RuntimeError(f'analysis blocked: {len(rows)} accepted cells != {plan["n_cells"]}')
    expected={(c['panel'],int(c['seed']),c['method'],int(c['replicate'])) for c in plan['cells']}
    observed={(r['panel'],int(r['seed']),r['method'],int(r['replicate'])) for r in rows}
    if observed!=expected:
        missing=sorted(expected-observed)[:10];extra=sorted(observed-expected)[:10]
        raise RuntimeError(f'analysis blocked: accepted-cell identity set mismatch; missing={missing}, extra={extra}')
    fields=list(rows[0])
    with (OUT/'RQ3_ALL_CELLS.csv').open('w',newline='',encoding='utf-8') as f:w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rows)

    # Primary/secondary inferential dataset is replicate 1 only, uniformly for every graph-method condition.
    main=[r for r in rows if int(r['replicate'])==int(CFG['primary_analysis_replicate'])]
    if len(main)!=768:raise RuntimeError(f'expected 768 main-inference replicate-1 cells, found {len(main)}')
    with (OUT/'RQ3_MAIN_INFERENCE_CELLS.csv').open('w',newline='',encoding='utf-8') as f:w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(main)
    by={(r['panel'],r['seed'],r['method']):r for r in main}
    if len(by)!=768:raise RuntimeError('main-inference graph-method identities are not unique')
    A=list(range(CFG['panel_a']['seed_start'],CFG['panel_a']['seed_end']+1));ALL=all_seeds();sesoi=float(CFG['practical_completion_threshold']);base=int(CFG['bootstrap_seed'])
    def contrast(name,seeds,a,b,field='completion',seedoff=0):
        vals=[by[(panel(s),s,a)][field]-by[(panel(s),s,b)][field] for s in seeds];mean,ci=boot(vals,base+seedoff);return {'contrast':name,'endpoint':field,'n_graphs':len(seeds),'main_inference_replicate':int(CFG['primary_analysis_replicate']),'mean_difference':mean,'ci95':ci,**wins(vals),'wilcoxon_p':wp(vals),'values':vals}
    primary=contrast('B5_COMPLETE-minus-B3_STABILIZED',A,'B5_COMPLETE','B3_STABILIZED',seedoff=100)
    primary.update({'role':'mechanism_primary','sesoi':sesoi,'statistically_positive':primary['ci95'][0]>0,'practically_relevant_point_estimate':primary['mean_difference']>=sesoi})
    second=[contrast('B3_STABILIZED-minus-B3_STRICT',A,'B3_STABILIZED','B3_STRICT',seedoff=101),contrast('B5_COMPLETE-minus-B5_NOTIE',A,'B5_COMPLETE','B5_NOTIE',seedoff=102)]
    inter_vals=[]
    for seed in A:
        inter_vals.append((by[('A',seed,'B5_COMPLETE')]['completion']-by[('A',seed,'B5_NOTIE')]['completion'])-(by[('A',seed,'B3_STABILIZED')]['completion']-by[('A',seed,'B3_STRICT')]['completion']))
    im,ic=boot(inter_vals,base+103);inter={'contrast':'stabilizer_interaction','endpoint':'completion','n_graphs':len(A),'main_inference_replicate':1,'mean_difference':im,'ci95':ic,**wins(inter_vals),'wilcoxon_p':wp(inter_vals),'values':inter_vals}
    second.append(inter);adj=holm([x['wilcoxon_p'] for x in second])
    for x,padj in zip(second,adj):x['holm_p']=padj;x['role']='mechanism_secondary'
    repl=contrast('B5_COMPLETE-minus-B3_STRICT',ALL,'B5_COMPLETE','B3_STRICT',seedoff=110);repl.update({'role':'fresh_precision_replication','sesoi':sesoi,'statistically_positive':repl['ci95'][0]>0,'practically_relevant_point_estimate':repl['mean_difference']>=sesoi})
    metrics=[]
    for j,(field,benefit) in enumerate([('ta_p95_ms','lower'),('throughput_success_rps','higher'),('medium_queue_wait_mean_ms','lower')]):
        x=contrast('B5_COMPLETE-minus-B3_STABILIZED',A,'B5_COMPLETE','B3_STABILIZED',field,120+j);x['beneficial_direction']=benefit;x['role']='mechanism_secondary_metric';metrics.append(x)
        y=contrast('B5_COMPLETE-minus-B3_STRICT',ALL,'B5_COMPLETE','B3_STRICT',field,130+j);y['beneficial_direction']=benefit;y['role']='replication_secondary_metric';metrics.append(y)

    # Prespecified repeatability audit: 64 graph identities x their panel methods x 3 executions.
    rlock=json.loads((PRE/'REPEATABILITY_SUBSET_LOCK.json').read_text())
    repseeds=set(map(int,rlock['panel_a']['seeds']+rlock['panel_b']['seeds']))
    rr=[r for r in rows if int(r['seed']) in repseeds]
    groups={}
    for r in rr:groups.setdefault((r['panel'],r['seed'],r['method']),[]).append(r)
    expected_groups=32*4+32*2
    if len(groups)!=expected_groups:raise RuntimeError(f'repeatability group count mismatch: {len(groups)} != {expected_groups}')
    repeat_rows=[]
    metric_fields=['completion','ta_p95_ms','throughput_success_rps','medium_queue_wait_mean_ms']
    for (pa,se,me),vals in sorted(groups.items()):
        vals=sorted(vals,key=lambda x:x['replicate'])
        if [x['replicate'] for x in vals]!=[1,2,3]:raise RuntimeError(f'repeatability replicates incomplete for {(pa,se,me)}')
        row={'panel':pa,'seed':se,'method':me,'n_repeats':3}
        for field in metric_fields:
            xs=[float(x[field]) for x in vals]
            row[field+'_mean']=float(np.mean(xs));row[field+'_sd']=float(np.std(xs,ddof=1));row[field+'_range']=float(max(xs)-min(xs))
        repeat_rows.append(row)
    with (OUT/'RQ3_REPEATABILITY_GROUPS.csv').open('w',newline='',encoding='utf-8') as f:w=csv.DictWriter(f,fieldnames=list(repeat_rows[0]));w.writeheader();w.writerows(repeat_rows)
    repeat_summary={'status':'DESCRIPTIVE_DIAGNOSTIC_ONLY','selection_lock_sha256':sha(PRE/'REPEATABILITY_SUBSET_LOCK.json'),'n_graphs':64,'panel_A_graphs':32,'panel_B_graphs':32,'graph_method_groups':len(repeat_rows),'repeats_per_selected_graph_method':3,'additional_repeats_used_in_primary_inference':False,'metrics':{}}
    for field in metric_fields:
        sds=np.array([r[field+'_sd'] for r in repeat_rows],float);ranges=np.array([r[field+'_range'] for r in repeat_rows],float)
        repeat_summary['metrics'][field]={'mean_within_group_sd':float(sds.mean()),'median_within_group_sd':float(np.median(sds)),'p95_within_group_sd':float(np.quantile(sds,.95)),'max_within_group_sd':float(sds.max()),'mean_within_group_range':float(ranges.mean()),'max_within_group_range':float(ranges.max())}
    dump(OUT/'RQ3_REPEATABILITY_AUDIT.json',repeat_summary)

    raw={'mechanism_primary':primary.pop('values'),'mechanism_secondary':{x['contrast']:x.pop('values') for x in second},'precision_replication':repl.pop('values'),'secondary_metrics':{f"{x['contrast']}::{x['endpoint']}":x.pop('values') for x in metrics}}
    dump(OUT/'RQ3_PAIRED_DIFFERENCES.json',raw)
    report={'experiment_id':CFG['experiment_id'],'post_confirmatory':True,'original_RQ3_unchanged':True,'analysis_design':'replicate 1 only for all treatment-effect estimates; repeats 2-3 on frozen 64-graph subset are descriptive repeatability diagnostics only','mechanism_primary':primary,'mechanism_secondary':second,'fresh_precision_replication':repl,'secondary_application_metrics':metrics,'repeatability_diagnostic':repeat_summary,'execution_accounting':{'expected_cells':plan['n_cells'],'accepted_cells':len(rows),'main_inference_cells':len(main),'repeatability_extra_cells':len(rows)-len(main),'panel_A_graphs':128,'panel_B_graphs':128,'fresh_original_pair_graphs':256,'repeatability_graphs':64},'interpretation_rule':'Report all directions and intervals. Do not call lack of significance equivalence without a separately frozen equivalence test.'}
    dump(OUT/'RQ3_FINAL_SUMMARY.json',report);return report

def package_results():
    p=OUT/'PAPER2_RQ3_HYBRID_RESULTS_COMPLETE.zip';tmp=p.with_suffix('.zip.tmp')
    with zipfile.ZipFile(tmp,'w',zipfile.ZIP_DEFLATED) as z:
        for q in sorted(OUT.rglob('*')):
            if not q.is_file() or q in (p,tmp):continue
            z.write(q,q.relative_to(OUT.parent))
        for q in sorted((ROOT/'PROTOCOL').glob('*')):
            if q.is_file():z.write(q,Path('PROTOCOL')/q.name)
        for q in [ROOT/'config/rq3_extension.json',ROOT/'SCIENTIFIC_PAYLOAD_LOCK.json',ROOT/'PACKAGE_SHA256SUMS.txt']:
            z.write(q,Path('INPUT_LOCKS')/q.name)
    os.replace(tmp,p);dump(OUT/'FINAL_RESULTS_PACKAGE.json',{'path':p.name,'sha256':sha(p),'bytes':p.stat().st_size});return p

def complete(workers=None):
    OUT.mkdir(exist_ok=True);payload=verify_payload_locks();selector_reproduction_gate();build_selections(workers);generate_run_plan();pre=cluster_preflight();run_science();report=analyze();p=package_results();dump(OUT/'RUN_COMPLETE.json',{'complete':True,'result_package':p.name,'result_package_sha256':sha(p),'summary_sha256':sha(OUT/'RQ3_FINAL_SUMMARY.json'),'accepted_cells':accepted_count()});return report

def status():
    plan=generate_run_plan();return {'accepted_cells':accepted_count(),'expected_cells':plan['n_cells'],'complete':accepted_count()==plan['n_cells'],'analysis_present':(OUT/'RQ3_FINAL_SUMMARY.json').exists(),'results_package_present':(OUT/'PAPER2_RQ3_HYBRID_RESULTS_COMPLETE.zip').exists()}

def main():
    ap=argparse.ArgumentParser();ap.add_argument('command',choices=['verify','reproduce-old','build-selections','preflight','run-science','analyze','package-results','complete','status']);ap.add_argument('--workers',type=int);a=ap.parse_args()
    if a.command=='verify':print(json.dumps(verify_payload_locks(),indent=2));return
    if a.command=='reproduce-old':print(json.dumps(selector_reproduction_gate(),indent=2));return
    if a.command=='build-selections':print(json.dumps(build_selections(a.workers),indent=2));return
    if a.command=='preflight':print(json.dumps(cluster_preflight(),indent=2));return
    if a.command=='run-science':run_science();print(json.dumps(status(),indent=2));return
    if a.command=='analyze':print(json.dumps(analyze(),indent=2));return
    if a.command=='package-results':print(package_results());return
    if a.command=='status':print(json.dumps(status(),indent=2));return
    print(json.dumps(complete(a.workers),indent=2))
if __name__=='__main__':main()
