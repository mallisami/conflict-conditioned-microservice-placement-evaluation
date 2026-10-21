#!/usr/bin/env python3
"""Paper-II Stage-A packet calibration / held-out execution harness.

Legacy comparator-calibration component retained from B4 v1.6; it is not B5 confirmatory RQ1 evidence.
Component protocol: paper2-contention-shape-stage-a-v1.4

Science-safe phase sequence:
  1) self-test
  2) prepare                 # Docker build + smoke + 25/50/75% duty gates
  3) solo-calibration        # 18 infrastructure/calibration executions
  4) run-calibration         # 1,350 science executions (30 shapes)
  5) fit-freeze              # aggregate RNGs, fit B3/A1/B4, hash coefficients
  6) run-holdout             # blocked until valid coefficient freeze exists
  7) analyze-holdout         # RQ1 only; no model refit

A synthetic offline test exercises the same state machine without Docker/ns-3.
"""
from __future__ import annotations
import argparse, csv, hashlib, json, math, os, platform, random, shutil, statistics, subprocess, sys, time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CFG = json.loads((ROOT/'config/stage_a.json').read_text())
SHAPES = json.loads((ROOT/'config/stage_a_shapes.json').read_text())['shapes']
INTENTS = json.loads((ROOT/'config/stage_a_science_intents.json').read_text())['science_intents']
RESULTS = ROOT/'stage_a_results'
CURRENT = RESULTS/'CURRENT_RUN.txt'
EXEC = {'mode':'waf','binary':None}
EPS=1e-12


def now(): return datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')

def sha(path: Path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for b in iter(lambda:f.read(1<<20),b''): h.update(b)
    return h.hexdigest()

def dump(path: Path, obj):
    path.parent.mkdir(parents=True,exist_ok=True)
    tmp=path.with_suffix(path.suffix+'.tmp')
    tmp.write_text(json.dumps(obj,indent=2,sort_keys=True),encoding='utf-8')
    os.replace(tmp,path)

def run_cmd(args,timeout=300,check=True):
    p=subprocess.run(args,capture_output=True,text=True,timeout=timeout)
    if check and p.returncode:
        raise RuntimeError(f"command failed ({p.returncode}): {' '.join(map(str,args))}\n{p.stdout[-3000:]}\n{p.stderr[-3000:]}")
    return p

def docker_ok():
    return shutil.which('docker') is not None and run_cmd(['docker','version'],timeout=60,check=False).returncode==0

def image_id(name):
    p=run_cmd(['docker','image','inspect',name,'--format','{{.Id}}'],timeout=60,check=False)
    return p.stdout.strip() if p.returncode==0 else ''

def image_commit(name):
    p=run_cmd(['docker','run','--rm',name,'git','rev-parse','HEAD'],timeout=60,check=False)
    return p.stdout.strip() if p.returncode==0 else ''

def manifest(root: Path):
    rows=[]
    for p in sorted(root.rglob('*')):
        if p.is_file() and p.name!='SHA256SUMS.txt': rows.append(f"{sha(p)}  {p.relative_to(root).as_posix()}")
    (root/'SHA256SUMS.txt').write_text('\n'.join(rows)+'\n',encoding='utf-8')

def verify_inherited_hashes():
    m=json.loads((ROOT/'provenance_reuse_manifest.json').read_text())
    bad=[]
    for rec in m.get('copied_files',[]):
        p=ROOT/rec['paper2_path']
        if not p.exists() or sha(p)!=rec['sha256']: bad.append(rec['paper2_path'])
    if bad: raise RuntimeError('inherited infrastructure hash mismatch: '+', '.join(bad))

def self_test(check_disk=True):
    assert CFG['protocol_id']=='paper2-contention-shape-stage-a-v1.4'
    assert CFG['resource_shares']==[0.25,0.5,0.75]
    assert CFG['utilization_levels']==[0.6,0.75,0.85,0.95,1.0]
    assert CFG['active_stream_counts']==[2,3,4,5,6]
    assert len(SHAPES)==60 and sum(s['split']=='calibration' for s in SHAPES)==30 and sum(s['split']=='holdout' for s in SHAPES)==30
    assert len(INTENTS)==2700 and sum(c['split']=='calibration' for c in INTENTS)==1350 and sum(c['split']=='holdout' for c in INTENTS)==1350
    ids=[x['cell_id'] for x in INTENTS]
    assert len(ids)==len(set(ids))
    shape_by={s['shape_id']:s for s in SHAPES}
    for c in INTENTS:
        s=shape_by[c['shape_id']]
        assert c['split']==s['split'] and c['m']==s['m']
        assert math.isclose(c['n_eff'],s['n_eff'],rel_tol=1e-12)
        assert math.isclose(sum(c['weights']),1.0,rel_tol=1e-12,abs_tol=1e-12)
        assert sum(w>0 for w in c['weights'])==c['m']
    verify_inherited_hashes()
    cpp=(ROOT/'simulator/evaluate_shared_airtime_boundary.cc').read_text()
    for forbidden in ['planner_admissible','worst_conflict_utilization','planned_feasible']:
        assert forbidden not in cpp
    free=shutil.disk_usage(ROOT).free/1024**3
    if check_disk and free<float(CFG['min_results_free_gib']): raise RuntimeError(f'insufficient free disk: {free:.2f} GiB')
    return {'passed':True,'shapes':60,'science_intents':2700,'calibration_intents':1350,'holdout_intents':1350,'free_gib':free}

def ensure_runroot():
    RESULTS.mkdir(parents=True,exist_ok=True)
    if CURRENT.exists(): return Path(CURRENT.read_text().strip())
    root=RESULTS/f'run-{now()}'
    root.mkdir(parents=True)
    CURRENT.write_text(str(root.resolve())+'\n',encoding='utf-8')
    dump(root/'provenance.json',{
        'protocol':'paper2-v1.4-stage-a','platform':platform.platform(),'python':sys.version,
        'stage_a_config_sha256':sha(ROOT/'config/stage_a.json'),
        'shape_plan_sha256':sha(ROOT/'config/stage_a_shapes.json'),
        'science_intents_sha256':sha(ROOT/'config/stage_a_science_intents.json'),
        'simulator_sha256':sha(ROOT/'simulator/evaluate_shared_airtime_boundary.cc'),
        'runner_sha256':sha(Path(__file__)),'started_utc':now()
    })
    return root

def freeze_package():
    out=ROOT/'PREEXECUTION_SHA256SUMS.txt'
    rows=[]
    for sub in ['PROTOCOL','config','src','simulator','deps']:
        for p in sorted((ROOT/sub).rglob('*')):
            if p.is_file() and 'stage_a_results' not in str(p): rows.append(f"{sha(p)}  {p.relative_to(ROOT).as_posix()}")
    out.write_text('\n'.join(rows)+'\n',encoding='utf-8')
    return {'freeze_file':str(out),'entries':len(rows),'sha256':sha(out)}

def container_spec(evidence: Path, rates, rng, duty, name, mode=None):
    rates_csv=','.join(f'{x:.6f}' for x in rates)
    spec=(f"evaluate_shared_airtime_boundary --simulationTime={CFG['simulation_seconds']} "
          f"--packetSize={CFG['packet_size_bytes']} --socketType={CFG['socket_type']} "
          f"--numSTAs={CFG['num_streams']} --ratesMbpsCsv={rates_csv} --csv=true "
          f"--reportDataSnr=true --directory=/evidence/ --qdChannelFolder={CFG['qd_channel_folder']} "
          f"--phyMode={CFG['phy_mode']} --dutyFraction={duty:.12g} --trafficStartSeconds={CFG['traffic_start_seconds']} "
          f"--minimumAssociationLeadMs={CFG['minimum_association_lead_ms']} --RngRun={rng}")
    mode=mode or EXEC['mode']
    if mode=='direct':
        inner=f"set -o pipefail; mkdir -p Traces; LD_LIBRARY_PATH=build/lib:$LD_LIBRARY_PATH {EXEC['binary']} {spec.split(' ',1)[1]}"
    else:
        inner=f"set -o pipefail; mkdir -p Traces; ./waf --run-no-build {json.dumps(spec)}"
    return ['docker','run','--rm','--name',name,'-v',f'{evidence.resolve()}:/evidence',CFG['experiment_image'],'/bin/bash','-lc',inner],spec

def parse_packet(path: Path, expected_rates, require_positive=False):
    if not path.exists(): raise RuntimeError('packet_summary.csv missing')
    rows=list(csv.DictReader(path.open(newline='',encoding='utf-8')))
    active={i:r for i,r in enumerate(expected_rates) if r>0}
    got={int(r['sta_index']):r for r in rows}
    if set(got)!=set(active): raise RuntimeError(f'active STA mismatch: expected {sorted(active)}, got {sorted(got)}')
    out=[]
    for i,offered in active.items():
        row=got[i]; configured=float(row['configured_mbps']); achieved=float(row['achieved_mbps'])
        if not math.isclose(configured,offered,rel_tol=1e-6,abs_tol=1e-3): raise RuntimeError('configured rate mismatch')
        if float(row['active_seconds'])<=0: raise RuntimeError('non-positive active interval')
        if require_positive and achieved<=0: raise RuntimeError('non-positive achieved throughput')
        out.append({'sta_index':i,'offered_mbps':offered,'achieved_mbps':achieved,
                    'delivered_fraction':min(1.0,float(row['delivered_fraction'])),
                    'active_seconds':float(row['active_seconds']),'rx_bytes':int(row['rx_bytes'])})
    return out

def parse_resource(path: Path,duty):
    rows=list(csv.DictReader(path.open(newline='',encoding='utf-8')))
    if len(rows)!=1: raise RuntimeError('resource_summary.csv must contain one row')
    r=rows[0]
    if not math.isclose(float(r['duty_fraction']),duty,abs_tol=1e-9): raise RuntimeError('duty fraction mismatch')
    if int(r['traffic_started'])!=1: raise RuntimeError('pre-traffic association/resource gate failed')
    if duty<0.999999 and int(r['scheduled_cbap_duration_us'])<=0: raise RuntimeError('shared CBAP was not scheduled')
    if float(r['association_lead_seconds'])+1e-9<float(CFG['minimum_association_lead_ms'])/1000: raise RuntimeError('association lead guard not met')
    return r

def run_cell(root: Path,phase,cid,rates,rng,duty,extra):
    croot=root/'cells'/phase/cid; accepted=croot/'accepted.json'
    if accepted.exists(): return json.loads(accepted.read_text())
    for attempt in range(1,int(CFG['max_cell_attempts'])+1):
        adir=croot/f'attempt-{attempt}'; adir.mkdir(parents=True,exist_ok=True)
        name=('p2-'+phase+'-'+cid+'-a'+str(attempt)).lower().replace('.','p').replace('_','-')[:120]
        cmd,spec=container_spec(adir,rates,rng,duty,name)
        (adir/'command.txt').write_text(spec+'\n',encoding='utf-8')
        t0=time.time()
        try: p=run_cmd(cmd,timeout=int(CFG['cell_timeout_seconds']),check=False)
        except subprocess.TimeoutExpired:
            subprocess.run(['docker','rm','-f',name],capture_output=True,text=True); p=None
        elapsed=time.time()-t0
        if p is not None: (adir/'stdout_stderr.log').write_text(p.stdout+p.stderr,encoding='utf-8')
        if p is None or p.returncode!=0:
            dump(adir/'failure.json',{'timeout':p is None,'returncode':None if p is None else p.returncode,'elapsed_seconds':elapsed}); continue
        try:
            packets=parse_packet(adir/'packet_summary.csv',rates,require_positive=(phase in ['solo','smoke','duty']))
            resource=parse_resource(adir/'resource_summary.csv',duty)
            off=sum(x['offered_mbps'] for x in packets); ach=sum(x['achieved_mbps'] for x in packets)
            rec={'phase':phase,'cell_id':cid,'rng_run':rng,'duty_fraction':duty,'rates_mbps':rates,
                 'aggregate_offered_mbps':off,'aggregate_achieved_mbps':ach,
                 'aggregate_delivered_fraction':min(1.0,ach/off) if off>0 else 1.0,
                 'packets':packets,'resource':resource,'attempt':attempt,'elapsed_seconds':elapsed,**extra}
            dump(accepted,rec); return rec
        except Exception as e:
            dump(adir/'failure.json',{'validation_error':str(e),'elapsed_seconds':elapsed})
    raise RuntimeError(f'cell failed after attempt limit: {phase}/{cid}')

def prepare():
    st=self_test(); freeze=freeze_package()
    if not docker_ok(): raise RuntimeError('Docker is required for prepare/science execution')
    base=CFG['base_image']; exp=CFG['experiment_image']
    if not image_id(base): run_cmd(['docker','build','-f',str(ROOT/'simulator/Dockerfile.ns3-wigig'),'-t',base,str(ROOT/'simulator')],timeout=4*3600)
    if image_commit(base)!=CFG['wigig_commit']: raise RuntimeError('base WiGig commit mismatch')
    run_cmd(['docker','build','--pull=false','-t',exp,str(ROOT/'simulator')],timeout=3600)
    EXEC.update({'mode':'waf','binary':None})
    root=ensure_runroot()
    # low-rate smoke at 50% share
    rates=[float(CFG['smoke_rate_mbps_per_stream'])]*6
    smoke=run_cell(root,'smoke','low-rate',rates,int(CFG['smoke_rng_run']),0.5,{})
    # Optional direct binary equivalence check.
    exec_note='waf wrapper'
    try:
        ls=run_cmd(['docker','run','--rm',exp,'/bin/bash','-lc','ls build/scratch'],timeout=120,check=False).stdout.split()
        cands=[x for x in ls if 'evaluate_shared_airtime_boundary' in x and '.' not in x]
        if cands:
            EXEC.update({'mode':'direct','binary':'build/scratch/'+cands[0]})
            d=root/'direct-equivalence'; d.mkdir(exist_ok=True)
            cmd,_=container_spec(d,rates,int(CFG['smoke_rng_run']),0.5,'p2-direct-equivalence','direct')
            p=run_cmd(cmd,timeout=int(CFG['cell_timeout_seconds']),check=False)
            if p.returncode==0:
                parse_packet(d/'packet_summary.csv',rates,True); parse_resource(d/'resource_summary.csv',0.5)
                # Compare packet summary bytes with accepted smoke attempt.
                smoke_attempt=root/'cells/smoke/low-rate'/f"attempt-{smoke['attempt']}"/'packet_summary.csv'
                if (d/'packet_summary.csv').read_bytes()==smoke_attempt.read_bytes(): exec_note='direct binary verified byte-identical';
                else: EXEC.update({'mode':'waf','binary':None})
            else: EXEC.update({'mode':'waf','binary':None})
    except Exception:
        EXEC.update({'mode':'waf','binary':None})
    # duty gates all shares; compare against full duty using same saturating offer/rng.
    gate={}
    gr=[float(CFG['duty_gate_offer_mbps'])]+[0.0]*5
    full=run_cell(root,'duty','full',gr,int(CFG['duty_gate_rng_run']),1.0,{})
    full_t=full['aggregate_achieved_mbps']
    for s in CFG['resource_shares']:
        rec=run_cell(root,'duty',f'share-{s:.2f}',gr,int(CFG['duty_gate_rng_run']),float(s),{})
        ratio=rec['aggregate_achieved_mbps']/full_t
        lo=max(0.05,0.5*float(s)); hi=min(0.95,1.5*float(s))
        if not (lo<=ratio<=hi): raise RuntimeError(f'duty gate failed s={s}: ratio={ratio:.4f}, band=[{lo:.4f},{hi:.4f}]')
        gate[str(s)]={'limited_mbps':rec['aggregate_achieved_mbps'],'full_mbps':full_t,'ratio':ratio,'band':[lo,hi]}
    out={'prepared':True,'self_test':st,'freeze':freeze,'image_id':image_id(exp),'wigig_commit':CFG['wigig_commit'],'execution_mode':dict(EXEC),'execution_mode_note':exec_note,'duty_gates':gate}
    dump(root/'PREPARE.json',out); return out

def solo_calibration(root: Path,cell_fn=run_cell):
    offered=float(CFG['solo_calibration_offer_mbps']); cells=[]
    for sta in range(6):
        for rng in CFG['solo_calibration_rng_runs']:
            rates=[0.0]*6; rates[sta]=offered
            cells.append(cell_fn(root,'solo',f'sta{sta}-rng{rng}',rates,int(rng),1.0,{'sta_index':sta}))
    good=[]; rows=[]
    for sta in range(6):
        vals=[c['aggregate_achieved_mbps'] for c in cells if c['sta_index']==sta]
        dfs=[c['aggregate_delivered_fraction'] for c in cells if c['sta_index']==sta]
        g=statistics.median(vals)
        if g<=0: raise RuntimeError(f'zero solo goodput STA {sta}')
        if statistics.median(dfs)>=0.98: raise RuntimeError(f'solo offer did not saturate STA {sta}')
        good.append(g); rows.append({'sta_index':sta,'median_solo_goodput_mbps':g,'values_mbps':vals,'median_delivered_fraction':statistics.median(dfs)})
    rec={'solo_goodputs_mbps':good,'rows':rows,'calibration_runs':18}
    dump(root/'solo_calibration_summary.json',rec); return rec

def load_goodputs(root):
    p=root/'solo_calibration_summary.json'
    if not p.exists(): raise RuntimeError('solo calibration missing')
    g=json.loads(p.read_text())['solo_goodputs_mbps']
    if len(g)!=6 or any(x<=0 for x in g): raise RuntimeError('invalid solo calibration')
    return g

def phase_cells(split,goodputs):
    rows=[]
    for c in INTENTS:
        if c['split']!=split: continue
        s=float(c['resource_share']); U=float(c['U'])
        rates=[float(w)*U*s*float(g) for w,g in zip(c['weights'],goodputs)]
        implied=sum((r/g) for r,g in zip(rates,goodputs) if r>0)/s
        if not math.isclose(implied,U,rel_tol=1e-10,abs_tol=1e-10): raise RuntimeError('rate construction mismatch')
        if max(rates)>float(CFG['max_science_rate_mbps_per_stream']): raise RuntimeError(f'rate guard exceeded: {max(rates):.3f}')
        rows.append({**c,'rates_mbps':rates})
    seed=int(CFG['run_order_seed'])+(0 if split=='calibration' else 1)
    random.Random(seed).shuffle(rows)
    return rows

def execute_split(root: Path,split,cell_fn=run_cell,workers=None):
    if split=='holdout' and not coefficient_freeze_valid(root): raise RuntimeError('holdout is LOCKED until coefficient freeze is valid')
    good=load_goodputs(root); cells=phase_cells(split,good)
    dump(root/f'{split}_science_plan.json',{'split':split,'n_cells':len(cells),'run_order_seed':int(CFG['run_order_seed'])+(0 if split=='calibration' else 1),'solo_goodputs_mbps':good})
    done=[0]; t0=time.time()
    def one(c):
        cid=c['cell_id']
        extra={k:c[k] for k in ['shape_id','split','resource_share','U','m','n_eff','weights']}
        rec=cell_fn(root,split,cid,c['rates_mbps'],int(c['rng_run']),float(c['resource_share']),extra)
        done[0]+=1
        if done[0]%50==0 or done[0]==len(cells):
            el=time.time()-t0; print(f'[{split} {done[0]}/{len(cells)}] elapsed {el/60:.1f} min',flush=True)
        return rec
    with ThreadPoolExecutor(max_workers=int(workers or CFG.get('parallel_workers',4))) as ex: list(ex.map(one,cells))
    manifest(root)
    return {'split':split,'accepted':len(cells)}

def aggregate_split(root: Path,split):
    recs=[json.loads(p.read_text()) for p in sorted((root/'cells'/split).glob('*/accepted.json'))]
    expected=1350
    if len(recs)!=expected: raise RuntimeError(f'{split}: expected {expected} accepted RNG cells, found {len(recs)}')
    grouped={}
    for r in recs:
        key=(r['shape_id'],float(r['resource_share']),float(r['U']))
        grouped.setdefault(key,[]).append(r)
    rows=[]
    for (shape,s,U),rr in sorted(grouped.items()):
        if len(rr)!=len(CFG['science_rng_runs']): raise RuntimeError(f'missing nested RNGs for {shape},s={s},U={U}')
        D=sum(x['aggregate_delivered_fraction'] for x in rr)/len(rr)
        rows.append({'shape_id':shape,'resource_share':s,'U':U,'m':rr[0]['m'],'n_eff':rr[0]['n_eff'],'D':D,'loss':1-D,'n_rng':len(rr)})
    if len(rows)!=450: raise RuntimeError(f'{split}: expected 450 aggregated rows, found {len(rows)}')
    out=root/f'{split}_aggregated.csv'
    with out.open('w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
    return rows,out

def design_u(U): return [1.0,U,U*U]
def design_neff(U,n):
    z=math.log(max(1.0,n)); return [1.0,U,U*U,z,U*z]
def design_full(U,n,m):
    z=math.log(max(1.0,n)); q=math.log(max(1,m)); return [1.0,U,U*U,z,U*z,q,U*q]

def fit_freeze(root: Path):
    import numpy as np
    from scipy.optimize import nnls
    rows,csv_path=aggregate_split(root,'calibration')
    fits={}
    for s in CFG['resource_shares']:
        rr=[r for r in rows if math.isclose(r['resource_share'],float(s),abs_tol=1e-12)]
        y=np.array([r['loss'] for r in rr],float)
        Xu=np.array([design_u(r['U']) for r in rr],float)
        Xn=np.array([design_neff(r['U'],r['n_eff']) for r in rr],float)
        Xf=np.array([design_full(r['U'],r['n_eff'],r['m']) for r in rr],float)
        bu=nnls(Xu,y)[0]; bn=nnls(Xn,y)[0]; bf=nnls(Xf,y)[0]
        fits[str(s)]={'B3_U_only':bu.tolist(),'A1_U_Neff':bn.tolist(),'B4_full_shape':bf.tolist(),'n_aggregated_rows':len(rr)}
    obj={'protocol':'paper2-v1.4-stage-a','source_csv':csv_path.name,'source_csv_sha256':sha(csv_path),'fits':fits,'frozen_utc':now()}
    p=root/'frozen_coefficients.json'; dump(p,obj)
    freeze=root/'frozen_coefficients.sha256'; freeze.write_text(sha(p)+'  '+p.name+'\n',encoding='utf-8')
    manifest(root); return obj

def coefficient_freeze_valid(root):
    p=root/'frozen_coefficients.json'; f=root/'frozen_coefficients.sha256'
    if not p.exists() or not f.exists(): return False
    token=f.read_text().strip().split()[0] if f.read_text().strip() else ''
    return token==sha(p)

def predict(coef,x): return min(1.0,max(0.0,sum(a*b for a,b in zip(coef,x))))
def percentile(xs,p):
    import numpy as np
    return float(np.percentile(xs,p))

def analyze_holdout(root: Path):
    if not coefficient_freeze_valid(root): raise RuntimeError('invalid/missing coefficient freeze')
    rows,csv_path=aggregate_split(root,'holdout')
    co=json.loads((root/'frozen_coefficients.json').read_text())
    per_shape={}
    detailed=[]
    for r in rows:
        fit=co['fits'][str(r['resource_share'])]
        pu=predict(fit['B3_U_only'],design_u(r['U']))
        pn=predict(fit['A1_U_Neff'],design_neff(r['U'],r['n_eff']))
        pf=predict(fit['B4_full_shape'],design_full(r['U'],r['n_eff'],r['m']))
        e={'shape_id':r['shape_id'],'resource_share':r['resource_share'],'U':r['U'],'m':r['m'],'n_eff':r['n_eff'],'loss':r['loss'],
           'pred_B3':pu,'pred_A1':pn,'pred_B4':pf,'ae_B3':abs(pu-r['loss']),'ae_A1':abs(pn-r['loss']),'ae_B4':abs(pf-r['loss'])}
        detailed.append(e); per_shape.setdefault(r['shape_id'],[]).append(e)
    shape_rows=[]
    for shape,rr in sorted(per_shape.items()):
        mean=lambda k:sum(x[k] for x in rr)/len(rr)
        shape_rows.append({'shape_id':shape,'mae_B3':mean('ae_B3'),'mae_A1':mean('ae_A1'),'mae_B4':mean('ae_B4'),'delta_B4_minus_B3':mean('ae_B4')-mean('ae_B3'),'delta_A1_minus_B3':mean('ae_A1')-mean('ae_B3'),'delta_B4_minus_A1':mean('ae_B4')-mean('ae_A1')})
    import numpy as np
    def contrast(field, seed_offset):
        d=np.array([r[field] for r in shape_rows],float)
        rng=np.random.default_rng(int(CFG['bootstrap_seed'])+seed_offset)
        B=int(CFG['bootstrap_resamples']); idx=rng.integers(0,len(d),(B,len(d))); bm=d[idx].mean(axis=1)
        ci=[percentile(bm,2.5),percentile(bm,97.5)]
        return {'n_shapes':len(d),'mean_delta_MAE':float(d.mean()),'ci95':ci,'supported_lower_MAE':bool(ci[1]<0)}
    primary=contrast('delta_B4_minus_B3',0)
    primary['contrast']='B4_FULL_SHAPE-minus-B3_U_ONLY'
    primary['mean_delta_MAE_B4_minus_B3']=primary.pop('mean_delta_MAE')
    ab1=contrast('delta_A1_minus_B3',1); ab1['contrast']='A1_U_NEFF-minus-B3_U_ONLY'
    ab2=contrast('delta_B4_minus_A1',2); ab2['contrast']='B4_FULL_SHAPE-minus-A1_U_NEFF'
    report={'protocol':'paper2-v1.4-stage-a','heldout_aggregated_sha256':sha(csv_path),'coefficient_sha256':sha(root/'frozen_coefficients.json'),
            'primary_RQ1':primary,'ablation_contrasts':[ab1,ab2],
            'mean_MAE':{k:float(np.mean([r[k] for r in shape_rows])) for k in ['mae_B3','mae_A1','mae_B4']},
            'interpretation':'Primary support requires the entire 95% shape-resampling interval for B4-minus-B3 MAE to be below zero. A1-minus-B3 and B4-minus-A1 are prespecified ablation contrasts with independent shape-level bootstrap intervals. No refitting is performed on held-out data.'}
    dump(root/'RQ1_HOLDOUT_SUMMARY.json',report)
    with (root/'holdout_shape_errors.csv').open('w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=list(shape_rows[0])); w.writeheader(); w.writerows(shape_rows)
    with (root/'holdout_predictions.csv').open('w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=list(detailed[0])); w.writeheader(); w.writerows(detailed)
    manifest(root); return report

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('command',choices=['self-test','freeze','prepare','solo-calibration','run-calibration','fit-freeze','run-holdout','analyze-holdout','status'])
    ap.add_argument('--workers',type=int)
    ap.add_argument('--run-root',type=Path)
    a=ap.parse_args()
    if a.command=='self-test': print(json.dumps(self_test(),indent=2)); return
    if a.command=='freeze': print(json.dumps(freeze_package(),indent=2)); return
    root=a.run_root or ensure_runroot()
    if a.command=='prepare': print(json.dumps(prepare(),indent=2)); return
    if a.command=='solo-calibration': print(json.dumps(solo_calibration(root),indent=2)); return
    if a.command=='run-calibration': print(json.dumps(execute_split(root,'calibration',workers=a.workers),indent=2)); return
    if a.command=='fit-freeze': print(json.dumps(fit_freeze(root),indent=2)); return
    if a.command=='run-holdout': print(json.dumps(execute_split(root,'holdout',workers=a.workers),indent=2)); return
    if a.command=='analyze-holdout': print(json.dumps(analyze_holdout(root),indent=2)); return
    status={'run_root':str(root),'prepare':(root/'PREPARE.json').exists(),'solo':(root/'solo_calibration_summary.json').exists(),
            'calibration_accepted':len(list((root/'cells/calibration').glob('*/accepted.json'))) if (root/'cells/calibration').exists() else 0,
            'coefficient_freeze_valid':coefficient_freeze_valid(root),'holdout_accepted':len(list((root/'cells/holdout').glob('*/accepted.json'))) if (root/'cells/holdout').exists() else 0,
            'rq1_summary':(root/'RQ1_HOLDOUT_SUMMARY.json').exists()}
    print(json.dumps(status,indent=2))

if __name__=='__main__': main()
