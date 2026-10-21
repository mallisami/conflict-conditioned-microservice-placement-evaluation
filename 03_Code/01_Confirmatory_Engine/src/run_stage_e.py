#!/usr/bin/env python3
from __future__ import annotations
import argparse,hashlib,json,math,os,random,re,shutil,statistics,subprocess,sys,time
from dataclasses import replace
from pathlib import Path
from typing import Any,Mapping
import numpy as np
from scipy.stats import wilcoxon

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'));sys.path.insert(0,str(ROOT/'stage_e_support'));sys.path.insert(0,str(ROOT/'deps'))
import run_stage_c as C
import live_confirmatory as lc
from mape_cap_bplus.models import NodeSpec

FULL=json.loads((ROOT/'config/full_campaign.json').read_text()); CFG=FULL['stage_e']; OUT=ROOT/'stage_e_results'
METHOD_MAP={m:m for m in CFG['methods']}
TIMEOUT_MS=3000.0

def dump(p:Path,o:Any):p.parent.mkdir(parents=True,exist_ok=True);tmp=p.with_suffix(p.suffix+'.tmp');tmp.write_text(json.dumps(o,indent=2,sort_keys=True,default=str),encoding='utf-8');os.replace(tmp,p)
def sh(p:Path):return hashlib.sha256(p.read_bytes()).hexdigest()
def load_regimes():
    p=ROOT/CFG['load_lock_file']
    if not p.exists(): raise RuntimeError('Stage-E load lock missing. Run src/calibrate_stage_e_loads.py after Stage-C and before confirmatory Stage-E.')
    obj=json.loads(p.read_text())
    if obj.get('status')!='FROZEN_PRE_RQ3': raise RuntimeError('Stage-E load lock not frozen')
    return {k:float(v) for k,v in obj['multipliers'].items()}
def setup_lc():
    if shutil.which('kubectl') is None: raise RuntimeError('kubectl required')
    ctx=subprocess.run(['kubectl','config','current-context'],capture_output=True,text=True,check=True).stdout.strip()
    lc.CONTEXT=ctx; lc.NS=CFG['namespace']; lc.IMAGE=CFG['benchmark_image']; lc.CANONICAL_TRACE_FILE=ROOT/'deps/ns3_simulation_backed_traces.csv'
    lc.CFG={**lc.CFG,'namespace':lc.NS,'benchmark_image':lc.IMAGE,'wireless_medium_service':'wireless-medium','wireless_medium_deployment':'wireless-medium','wireless_medium_timeout_seconds':5.0,'benchmark_http_timeout_seconds':3.0,'settle_seconds':CFG['settle_seconds'],'max_rollout_seconds':300,'emulated_scenario':'conflict-dense'}
    return ctx

def cluster_info():
    obj=lc.kubectl_json('get','nodes');items=obj.get('items',[])
    if len(items)!=3:raise RuntimeError(f'exactly 3 k3s nodes required, got {len(items)}')
    rack_to_node={};rows=[]
    for n in items:
        name=n['metadata']['name']; labels=n['metadata'].get('labels',{}); rack=labels.get('mape-cap-ws/rack') or labels.get('topology.kubernetes.io/zone')
        if rack not in ('rack-a','rack-b','rack-c'):raise RuntimeError(f'node {name} lacks rack-a/b/c label')
        if rack in rack_to_node:raise RuntimeError(f'duplicate rack label {rack}')
        rack_to_node[rack]=name
        cond={c.get('type'):c.get('status') for c in n.get('status',{}).get('conditions',[])}
        if cond.get('Ready')!='True':raise RuntimeError(f'node {name} not Ready')
        for x in ('MemoryPressure','DiskPressure','PIDPressure'):
            if cond.get(x)=='True':raise RuntimeError(f'node {name} has {x}')
        ips=[a.get('address') for a in n.get('status',{}).get('addresses',[]) if a.get('type')=='InternalIP']; ip=ips[0] if ips else ''
        ver=n.get('status',{}).get('nodeInfo',{}).get('kubeletVersion','');arch=n.get('status',{}).get('nodeInfo',{}).get('architecture','');osname=n.get('status',{}).get('nodeInfo',{}).get('operatingSystem','')
        if ver!=CFG['expected_kubelet_version']:raise RuntimeError(f'{name}: kubelet {ver} != {CFG["expected_kubelet_version"]}')
        if arch!=CFG['expected_architecture'] or osname!=CFG['expected_os']:raise RuntimeError(f'{name}: platform {osname}/{arch} unexpected')
        rows.append({'name':name,'rack':rack,'internal_ip':ip,'kubelet_version':ver})
    if len({r['internal_ip'] for r in rows})!=3 or any(not r['internal_ip'] for r in rows):raise RuntimeError('three distinct InternalIP values required')
    return {'rack_to_node':rack_to_node,'rack_to_worker':rack_to_node,'control_plane':rack_to_node['rack-a'],'nodes':rows}

def image_probe(info):
    lc.ensure_namespace();docs=[]
    for rack,node in info['rack_to_node'].items():
        docs.append({'apiVersion':'v1','kind':'Pod','metadata':{'name':f'p2-image-probe-{rack}','namespace':lc.NS},'spec':{'restartPolicy':'Never','nodeName':node,'containers':[{'name':'probe','image':lc.IMAGE,'imagePullPolicy':'Never','command':['python','-c','print("ok")']}]}})
    lc.kubectl('apply','-f','-',input_text='\n---\n'.join(json.dumps(x) for x in docs)+'\n',timeout=120)
    try:
        for rack in info['rack_to_node']:
            deadline=time.time()+90;phase=''
            while time.time()<deadline:
                pod=lc.kubectl_json('get','pod',f'p2-image-probe-{rack}','-n',lc.NS);phase=pod.get('status',{}).get('phase','')
                if phase in ('Running','Succeeded','Failed'):break
                time.sleep(2)
            if phase not in ('Running','Succeeded'):raise RuntimeError(f'benchmark image unavailable on {rack}; phase={phase}')
    finally:
        for rack in info['rack_to_node']:lc.kubectl('delete','pod',f'p2-image-probe-{rack}','-n',lc.NS,'--ignore-not-found=true',check=False)

def fingerprint_probe(info):
    docs=[]
    for rack,node in info['rack_to_node'].items():
        docs.append({'apiVersion':'v1','kind':'Pod','metadata':{'name':f'p2-host-fingerprint-{rack}','namespace':lc.NS},'spec':{'restartPolicy':'Never','nodeName':node,'containers':[{'name':'fp','image':lc.IMAGE,'imagePullPolicy':'Never','command':['python','-c',"import hashlib;print(hashlib.sha256(open('/host-etc/machine-id','rb').read().strip()).hexdigest())"],'volumeMounts':[{'name':'host-etc','mountPath':'/host-etc','readOnly':True}]}],'volumes':[{'name':'host-etc','hostPath':{'path':'/etc','type':'Directory'}}]}})
    lc.kubectl('apply','-f','-',input_text='\n---\n'.join(json.dumps(x) for x in docs)+'\n',timeout=120);vals={}
    try:
        for rack in info['rack_to_node']:
            deadline=time.time()+90;phase=''
            while time.time()<deadline:
                pod=lc.kubectl_json('get','pod',f'p2-host-fingerprint-{rack}','-n',lc.NS);phase=pod.get('status',{}).get('phase','')
                if phase in ('Succeeded','Failed'):break
                time.sleep(2)
            if phase!='Succeeded':raise RuntimeError(f'host fingerprint failed {rack}')
            v=lc.kubectl('logs',f'p2-host-fingerprint-{rack}','-n',lc.NS,timeout=30).strip().splitlines()[-1].strip()
            if not re.fullmatch(r'[0-9a-f]{64}',v):raise RuntimeError('invalid machine-id hash')
            vals[rack]=v
        if len(set(vals.values()))!=3:raise RuntimeError('hosts are not distinct by machine-id hash')
        return vals
    finally:
        for rack in info['rack_to_node']:lc.kubectl('delete','pod',f'p2-host-fingerprint-{rack}','-n',lc.NS,'--ignore-not-found=true',check=False)

def preflight():
    setup_lc();info=cluster_info();image_probe(info);fps=fingerprint_probe(info);medium=lc.ensure_wireless_medium(info)
    rec={'passed':True,'context':lc.CONTEXT,'cluster':info,'host_machine_id_sha256':fps,'medium':medium,'benchmark_image':lc.IMAGE}
    OUT.mkdir(parents=True,exist_ok=True);dump(OUT/'PREFLIGHT.json',rec);return rec

def selection_path(seed):
    return OUT/'selection_graphs'/f'n8-{int(seed)}.json'

def build_selections(workers=3):
    coeffs,aroot=C.load_coeffs(); cp=aroot/'frozen_coefficients.json'
    (OUT/'selection_graphs').mkdir(parents=True,exist_ok=True)
    todo=[]
    for seed in CFG['graph_seeds']:
        dest=selection_path(seed)
        if not dest.exists(): todo.append(('n8',int(seed),str(cp)))
    if int(workers)<=1:
        results=[C.solve_graph(j) for j in todo]
    else:
        from multiprocessing import Pool
        with Pool(int(workers)) as pool: results=list(pool.imap_unordered(C.solve_graph,todo))
    for r in results: dump(selection_path(r['seed']),r)
    rows=[json.loads(selection_path(s).read_text()) for s in CFG['graph_seeds']]
    valid=[r for r in rows if r.get('valid') and not r.get('no_admissible_placement')]
    dump(OUT/'SELECTION_ACCOUNTING.json',{'scheduled':len(rows),'valid_with_admissible_set':len(valid),'structural_nonexecuted':[{'seed':r['seed'],'invalid_reason':r.get('invalid_reason'),'no_admissible_placement':r.get('no_admissible_placement',False)} for r in rows if r not in valid]})
    return {'scheduled':len(rows),'valid':len(valid)}

def graph_result(seed):
    p=selection_path(seed)
    if not p.exists():raise RuntimeError(f'missing frozen Stage-E selection graph {p}; run build-selections first')
    r=json.loads(p.read_text())
    if not r.get('valid') or r.get('no_admissible_placement'):raise RuntimeError(f'n8-{seed} not executable for Stage E')
    return r

def execution_problem(seed,info,load_multiplier=1.0):
    p,cal=C.build_scaled_problem('n8',seed)
    if p is None:raise RuntimeError(f'cannot reconstruct n8/{seed}: {cal}')
    p=replace(p,flows=tuple(replace(f,requests_per_window=float(f.requests_per_window)*float(load_multiplier),bits_per_window=float(f.bits_per_window)*float(load_multiplier)) for f in p.flows),metadata={**p.metadata,'stage_e_load_multiplier':float(load_multiplier)})
    # n8 has exactly one synthetic node per rack; map it exactly to one k3s node/rack.
    syn_by_rack={n.rack_id:n.node_id for n in p.nodes}
    node_map={syn_by_rack[rack]:node for rack,node in info['rack_to_node'].items()}
    nodes=tuple(NodeSpec(node_map[n.node_id],n.rack_id,100.0,100000.0) for n in p.nodes)
    allowed=tuple(n.node_id for n in nodes)
    reps=tuple(replace(r,allowed_nodes=allowed,cpu_request=float(CFG['execution_cpu_request']),memory_request_mb=float(CFG['execution_memory_request_mb'])) for r in p.replicas)
    current={rid:node_map[nid] for rid,nid in p.current_placement.items()}
    ep=replace(p,nodes=nodes,replicas=reps,current_placement=current,metadata={**p.metadata,'execution_only_reservations':True})
    return ep,node_map

def selected_plan(seed,method,node_map):
    g=graph_result(seed);pl=g['selections'][method]['placement'];return {rid:node_map[nid] for rid,nid in pl.items()}

def timeout_augmented_p95(traffic,metrics):
    vals=[]
    for pm in traffic.get('pod_metrics',{}).values():
        for row in pm.get('flows',{}).values():vals.extend(float(x) for x in row.get('latencies_ms',[]))
    missing=max(0,int(metrics['expected_scheduled_requests'])-len(vals)); vals.extend([TIMEOUT_MS]*missing)
    return lc.nearest_rank(vals,.95) if vals else None

def cell_path(seed,load,method,rep):return OUT/'science'/f'load-{load}'/f'seed-{seed}'/method/f'rep-{rep}'
def run_one(seed,load,multiplier,method,rep,info):
    root=cell_path(seed,load,method,rep);accepted=root/'accepted.json'
    if accepted.exists():return json.loads(accepted.read_text())
    problem,node_map=execution_problem(seed,info,multiplier);pl=selected_plan(seed,method,node_map);sc=next(s for s in problem.scenarios if s.scenario_id=='conflict-dense')
    for attempt in range(1,int(CFG['max_cell_attempts'])+1):
        ad=root/f'attempt-{attempt}';ad.mkdir(parents=True,exist_ok=True);partial={}
        try:
            run_id=f'p2b5:{load}:{seed}:{method}:{rep}:a{attempt}'
            rollout=lc.apply_placement(problem,pl,run_id); actual=lc.current_live_placement(problem)
            if actual!=pl:raise RuntimeError(f'actual pod placement mismatch: {actual} != {pl}')
            time.sleep(float(CFG['settle_seconds']))
            traffic=lc.configure_and_run_for_scenario(problem,pl,run_id,int(CFG['measurement_seconds']),sc)
            metrics=lc.aggregate_metrics(problem,pl,traffic); medium=traffic.get('wireless_medium_metrics',{}).get('metrics',{})
            if int(metrics['attempted_requests'])<=0:raise RuntimeError('zero attempted requests')
            expected_cross=float(metrics['cross_rack_attempted_bytes'])>0
            if expected_cross and int(medium.get('requests',0))<=0:raise RuntimeError('shared medium observed zero requests')
            health=lc.deployment_health(problem)
            if not health['healthy']:raise RuntimeError('deployment unhealthy after execution')
            rec={'seed':seed,'load_regime':load,'load_multiplier':float(multiplier),'method':method,'replicate':rep,'attempt':attempt,'accepted_infrastructure':True,'rollout':rollout,'metrics':metrics,
                 'timeout_augmented_p95_ms':timeout_augmented_p95(traffic,metrics),'wireless_medium_metrics':medium,'placement':pl,'host_racks':info['rack_to_node']}
            dump(accepted,rec);return rec
        except Exception as e:
            dump(ad/'failure.json',{'error':f'{type(e).__name__}: {e}','accepted_infrastructure':False})
            time.sleep(2)
    raise RuntimeError(f'Stage-E cell exhausted retries load={load} seed={seed} method={method} rep={rep}')

def method_order(seed,rep):
    ms=list(CFG['methods']);random.Random(int(CFG['method_order_seed'])+int(seed)*17+int(rep)).shuffle(ms);return ms

def run():
    setup_lc();info=cluster_info()
    if not (OUT/'PREFLIGHT.json').exists():preflight()
    seeds=[int(x) for x in CFG['graph_seeds']];loads=load_regimes();valid=[];structural=[]
    for seed in seeds:
        gp=selection_path(seed)
        if not gp.exists(): raise RuntimeError(f'missing scheduled Stage-C graph {gp}')
        g=json.loads(gp.read_text())
        if not g.get('valid') or g.get('no_admissible_placement'):
            structural.append({'seed':seed,'valid':bool(g.get('valid')),'no_admissible_placement':bool(g.get('no_admissible_placement')),'invalid_reason':g.get('invalid_reason')});continue
        valid.append(seed)
        for load,mult in loads.items():
            for rep in CFG['replicates']:
                for method in method_order(seed,rep): run_one(seed,load,mult,method,int(rep),info)
    dump(OUT/'STRUCTURAL_GRAPH_ACCOUNTING.json',{'scheduled':len(seeds),'executed_graphs':valid,'structural_nonexecuted':structural,'load_regimes':loads})
    return analyze()

def boot(x,seed):
    x=np.asarray(x,float);rng=np.random.default_rng(seed);B=int(FULL['bootstrap_resamples']);chunks=[];left=B
    while left:
        n=min(5000,left);idx=rng.integers(0,len(x),(n,len(x)));chunks.append(x[idx].mean(axis=1));left-=n
    v=np.concatenate(chunks);return float(x.mean()),[float(np.quantile(v,.025)),float(np.quantile(v,.975))]
def wp(x):
    a=np.asarray(x,float);a=a[np.abs(a)>1e-12]
    return 1.0 if len(a)==0 else float(wilcoxon(a,alternative='two-sided').pvalue)

def analyze():
    rows=[]
    for p in sorted((OUT/'science').glob('load-*/seed-*/*/rep-*/accepted.json')):
        d=json.loads(p.read_text());m=d['metrics'];dur=float(CFG['measurement_seconds'])
        rows.append({'seed':d['seed'],'load_regime':d['load_regime'],'load_multiplier':d['load_multiplier'],'method':d['method'],'replicate':d['replicate'],'completion':m['scheduled_completion_fraction'],'ta_p95_ms':d['timeout_augmented_p95_ms'],
                     'attempted_p95_ms':m['p95_ms'],'throughput_success_rps':m['successful_requests']/dur,'errors':m['errors'],
                     'medium_queue_wait_mean_ms':statistics.fmean(d['wireless_medium_metrics'].get('queue_wait_ms',[])) if d['wireless_medium_metrics'].get('queue_wait_ms') else 0.0})
    acc=json.loads((OUT/'STRUCTURAL_GRAPH_ACCOUNTING.json').read_text()) if (OUT/'STRUCTURAL_GRAPH_ACCOUNTING.json').exists() else {'executed_graphs':CFG['graph_seeds'],'scheduled':len(CFG['graph_seeds']),'structural_nonexecuted':[],'load_regimes':load_regimes()}
    seeds=[int(x) for x in acc['executed_graphs']]; expected=len(seeds)*len(CFG['methods'])*len(CFG['replicates'])*len(acc['load_regimes'])
    if len(rows)!=expected:raise RuntimeError(f'Stage-E incomplete: {len(rows)} accepted cells, expected {expected}')
    import csv
    with (OUT/'STAGE_E_CELLS.csv').open('w',newline='',encoding='utf-8') as f:w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    # average nested replicates per graph/method
    agg={}
    for r in rows:
        k=(r['seed'],r['load_regime'],r['method']);agg.setdefault(k,[]).append(r)
    gm=[]
    for k,rr in sorted(agg.items()):
        gm.append({'seed':k[0],'load_regime':k[1],'method':k[2],**{field:float(np.mean([x[field] for x in rr])) for field in ['completion','ta_p95_ms','attempted_p95_ms','throughput_success_rps','errors','medium_queue_wait_mean_ms']}})
    by={(r['seed'],r['load_regime'],r['method']):r for r in gm};primary_load=CFG['primary_load_regime'];diff=[by[(s,primary_load,'B5_CONFLICT_RANK')]['completion']-by[(s,primary_load,'B3_U_ONLY')]['completion'] for s in seeds]
    if diff:
        mean,ci=boot(diff,int(FULL['bootstrap_seed'])+70); supported=bool(ci[0]>0)
    else:
        mean=float('nan');ci=[float('nan'),float('nan')];supported=False
    sesoi=float(FULL.get('practical_significance',{}).get('RQ3_scheduled_completion_improvement_min',0.005)); report={'scheduled_graph_identities':int(acc.get('scheduled',40)),'structural_nonexecuted':acc.get('structural_nonexecuted',[]),'primary_RQ3':{'contrast':'B5_CONFLICT_RANK-minus-B3_U_ONLY','endpoint':'scheduled_completion_fraction','load_regime':primary_load,'n_graphs':len(seeds),'mean_difference':mean,'ci95':ci,'supported':supported,'sesoi':sesoi,'practically_relevant':bool(mean>=sesoi),'strong_operational_support':bool(supported and mean>=sesoi)},'secondary':[]}
    for comp in ['B1_MAPE_CAP_WS']:
        d=[by[(s,primary_load,'B5_CONFLICT_RANK')]['completion']-by[(s,primary_load,comp)]['completion'] for s in seeds];m,c=boot(d,int(FULL['bootstrap_seed'])+71);report['secondary'].append({'contrast':f'B5_CONFLICT_RANK-minus-{comp}','mean_completion_difference':m,'ci95':c,'wilcoxon_p':wp(d)})
    # Endpoint secondary B4-B3
    for field,beneficial in [('ta_p95_ms','lower'),('throughput_success_rps','higher'),('medium_queue_wait_mean_ms','lower')]:
        d=[by[(s,primary_load,'B5_CONFLICT_RANK')][field]-by[(s,primary_load,'B3_U_ONLY')][field] for s in seeds];m,c=boot(d,int(FULL['bootstrap_seed'])+72+len(report['secondary']));report['secondary'].append({'contrast':'B5_CONFLICT_RANK-minus-B3_U_ONLY','endpoint':field,'beneficial':beneficial,'mean_difference':m,'ci95':c,'wilcoxon_p':wp(d)})
    # Holm across secondary p-values
    ps=[x['wilcoxon_p'] for x in report['secondary']];order=sorted(range(len(ps)),key=lambda i:ps[i]);out=[1.0]*len(ps);running=0
    for j,i in enumerate(order):running=max(running,min(1.0,ps[i]*(len(ps)-j)));out[i]=running
    for x,p in zip(report['secondary'],out):x['holm_p']=p
    dump(OUT/'RQ3_APPLICATION_SUMMARY.json',report);return report

def main():
    ap=argparse.ArgumentParser();ap.add_argument('command',choices=['preflight','build-selections','run','analyze']);ap.add_argument('--workers',type=int,default=3);a=ap.parse_args()
    if a.command=='preflight':print(json.dumps(preflight(),indent=2));return
    if a.command=='build-selections':print(json.dumps(build_selections(a.workers),indent=2));return
    if a.command=='run':print(json.dumps(run(),indent=2));return
    print(json.dumps(analyze(),indent=2))
if __name__=='__main__':main()
