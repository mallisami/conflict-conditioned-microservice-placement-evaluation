#!/usr/bin/env python3
from __future__ import annotations
import argparse,hashlib,json,os,platform,shutil,socket,subprocess,sys,tarfile,tempfile
from datetime import datetime,timezone
from pathlib import Path
from typing import Any
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
VM=json.loads((ROOT/'config/vm_execution.json').read_text());FULL=json.loads((ROOT/'config/full_campaign.json').read_text())
EX=ROOT/'vm_exchange';EX.mkdir(exist_ok=True);LOG=ROOT/'operator_logs';LOG.mkdir(exist_ok=True)
def now():return datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for b in iter(lambda:f.read(1<<20),b''):h.update(b)
 return h.hexdigest()
def dump(p,o):
 p=Path(p);p.parent.mkdir(parents=True,exist_ok=True);tmp=p.with_suffix(p.suffix+'.tmp');tmp.write_text(json.dumps(o,indent=2,sort_keys=True,default=str)+'\n',encoding='utf-8');os.replace(tmp,p)
def run(name,args):
 print(f'\n===== {name} =====',flush=True);p=subprocess.Popen(args,cwd=ROOT,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,bufsize=1);lines=[]
 assert p.stdout
 for line in p.stdout:print(line,end='',flush=True);lines.append(line)
 rc=p.wait();(LOG/f'{name}.log').write_text(''.join(lines),encoding='utf-8')
 if rc:raise RuntimeError(f'{name} failed with exit code {rc}')
def source_manifest_sha():
 p=ROOT/'SHA256SUMS.txt'
 if not p.exists():raise RuntimeError('SHA256SUMS.txt missing')
 return sha(p)
def b5_model_lock_sha256():
 p=ROOT/'b5_lock/B5_MODEL_LOCK.json';h=ROOT/'b5_lock/B5_MODEL_LOCK.sha256'
 got=sha(p);want=h.read_text().split()[0]
 if got!=want:raise RuntimeError('B5 model lock hash mismatch')
 o=json.loads(p.read_text())
 if o.get('status')!='FROZEN_PRE_CONFIRMATION' or not o.get('development_gate',{}).get('passed'):raise RuntimeError('B5 lock not eligible for confirmation')
 return got
def coeff_root():
 p=ROOT/'stage_a_results/CURRENT_RUN.txt'
 if not p.exists():raise RuntimeError('legacy comparator Stage-A CURRENT_RUN missing')
 r=Path(p.read_text().strip())
 if not r.exists():raise RuntimeError(f'Stage-A target missing: {r}')
 return r
def coeff_sha():
 r=coeff_root();p=r/'frozen_coefficients.json';h=r/'frozen_coefficients.sha256'
 got=sha(p);want=h.read_text().split()[0]
 if got!=want:raise RuntimeError('legacy comparator coefficient hash mismatch')
 return got
def machine_record(role):
 mid=Path('/etc/machine-id');mh=hashlib.sha256(mid.read_bytes().strip()).hexdigest() if mid.exists() else None
 return {'role':role,'hostname':socket.gethostname(),'machine_id_sha256':mh,'platform':platform.platform(),'source_manifest_sha256':source_manifest_sha(),'stage_a_coefficients_sha256':coeff_sha() if (ROOT/'stage_a_results/CURRENT_RUN.txt').exists() else None,'b5_model_lock_sha256':b5_model_lock_sha256(),'created_utc':now(),'execution_profile':VM['profile_id']}
def verify_role(role):
 if role not in VM['roles']:raise RuntimeError(f'unknown role {role}')
 return VM['roles'][role]
def local_preflight(role,prepare_sim=False):
 verify_role(role)
 for n,a in [('base',[sys.executable,'tools/verify_base.py']),('stagea',[sys.executable,'tools/verify_stage_a_harness.py']),('vm',[sys.executable,'tools/verify_vm_execution.py']),('tests',[sys.executable,'-m','pytest','-q','tests'])]:run(f'{role}_{n}',a)
 if prepare_sim:run(f'{role}_prepare_simulator',[sys.executable,'src/run_stage_a.py','prepare'])
 rec=machine_record(role);rec['configured_heavy_workers']=VM['roles'][role]['heavy_workers'];dump(EX/f'{role}_LOCAL_PREFLIGHT.json',rec);print(json.dumps(rec,indent=2))
def coordinator_stage_a():
 role='vm2';w=int(VM['roles'][role]['heavy_workers']);b5_model_lock_sha256()
 local_preflight(role)
 run('vm2_stage_a_selftest',[sys.executable,'src/run_stage_a.py','self-test'])
 run('vm2_stage_e_pre_science_preflight',[sys.executable,'src/run_stage_e.py','preflight'])
 run('vm2_fetch_snob5g_pre_science',['bash','external/01_FETCH_SNOB5G.sh'])
 if FULL.get('deathstarbench_validation',{}).get('enabled'):
  run('vm2_fetch_deathstarbench_pre_science',['bash','external/02_FETCH_DEATHSTARBENCH.sh'])
  run('vm2_build_distribute_deathstarbench_images',['bash','deathstarbench/01_BUILD_AND_DISTRIBUTE_IMAGES.sh'])
  run('vm2_deathstarbench_preflight',[sys.executable,'src/run_deathstarbench_validation.py','preflight'])
 run('vm2_external_prepare_pre_science',[sys.executable,'src/run_external_validation.py','prepare'])
 run('vm2_stage_c_reproduction_gate',[sys.executable,'src/run_stage_c.py','gate'])
 for n,a in [('freeze',['freeze']),('prepare',['prepare']),('solo',['solo-calibration']),('calibration',['run-calibration','--workers',str(w)]),('fit',['fit-freeze']),('holdout',['run-holdout','--workers',str(w)]),('analyze',['analyze-holdout'])]:run('vm2_stage_a_'+n,[sys.executable,'src/run_stage_a.py',*a])
 run('vm2_stage_a_ood_legacy_diagnostic',[sys.executable,'src/run_stage_a_ood.py','run','--workers',str(w)])
 return export_stage_a()
def _tar_add(tf,p,arc):
 p=Path(p)
 if not p.exists():raise RuntimeError(f'missing bundle input: {p}')
 tf.add(p,arcname=arc,recursive=True)
def export_stage_a():
 r=coeff_root();bundle=EX/'STAGE_A_FROZEN_FOR_WORKERS.tar.gz';meta=machine_record('vm2');meta.update({'bundle_type':'legacy_comparator_stage_a_snapshot','coefficient_sha256':coeff_sha()})
 with tempfile.TemporaryDirectory() as td:
  t=Path(td);snap=t/'stage_a_snapshot';snap.mkdir()
  for name in ['frozen_coefficients.json','frozen_coefficients.sha256','solo_calibration_summary.json','provenance.json']:
   if (r/name).exists():shutil.copy2(r/name,snap/name)
  shutil.copy2(ROOT/'stage_c_results/REPRODUCTION_GATE.json',t/'REPRODUCTION_GATE.json');dump(t/'BUNDLE_MANIFEST.json',meta)
  with tarfile.open(bundle,'w:gz') as tf:_tar_add(tf,snap,'stage_a_snapshot');_tar_add(tf,t/'REPRODUCTION_GATE.json','REPRODUCTION_GATE.json');_tar_add(tf,t/'BUNDLE_MANIFEST.json','BUNDLE_MANIFEST.json')
 (bundle.with_suffix(bundle.suffix+'.sha256')).write_text(f'{sha(bundle)}  {bundle.name}\n',encoding='utf-8');print(f'WROTE {bundle} sha256={sha(bundle)}');return bundle
def _safe_extract(tf,dst):
 dst=Path(dst).resolve()
 for m in tf.getmembers():
  target=(dst/m.name).resolve()
  if target!=dst and dst not in target.parents:raise RuntimeError('unsafe tar path')
 tf.extractall(dst)
def import_stage_a(bundle,role):
 verify_role(role);b5_model_lock_sha256()
 with tempfile.TemporaryDirectory() as td:
  t=Path(td)
  with tarfile.open(bundle,'r:gz') as tf:_safe_extract(tf,t)
  meta=json.loads((t/'BUNDLE_MANIFEST.json').read_text())
  if meta['source_manifest_sha256']!=source_manifest_sha() or meta['b5_model_lock_sha256']!=b5_model_lock_sha256():raise RuntimeError('cross-VM source/B5 lock mismatch')
  local=ROOT/'stage_a_results/imported-vm2-frozen'
  if local.exists():shutil.rmtree(local)
  shutil.copytree(t/'stage_a_snapshot',local);(ROOT/'stage_a_results').mkdir(exist_ok=True);(ROOT/'stage_a_results/CURRENT_RUN.txt').write_text(str(local.resolve())+'\n',encoding='utf-8')
  if coeff_sha()!=meta['coefficient_sha256']:raise RuntimeError('imported comparator coefficient hash mismatch')
  (ROOT/'stage_c_results').mkdir(exist_ok=True);shutil.copy2(t/'REPRODUCTION_GATE.json',ROOT/'stage_c_results/REPRODUCTION_GATE.json')
 dump(EX/f'{role}_STAGE_A_IMPORT.json',machine_record(role));print(f'{role} STAGE-A IMPORT: PASS')
def random_shard(role):
 if role not in ('vm1','vm2'):raise RuntimeError('random shard only vm1/vm2')
 w=int(VM['roles'][role]['heavy_workers']);coeff_sha();b5_model_lock_sha256();run(f'{role}_prepare_simulator',[sys.executable,'src/run_stage_a.py','prepare'])
 run(f'{role}_stage_c',[sys.executable,'src/run_stage_c.py','run','--vm-role',role,'--workers',str(w)])
 run(f'{role}_robustness',[sys.executable,'src/run_stage_c_robustness.py','--workers',str(w)])
 run(f'{role}_stage_d_plan',[sys.executable,'src/run_stage_d.py','build-plan']);run(f'{role}_stage_d_packet',[sys.executable,'src/run_stage_d.py','run','--workers',str(w)])
 return export_random(role)
def export_random(role):
 meta=machine_record(role);meta['bundle_type']='b5_random_shard';bundle=EX/f'{role}_RANDOM_SHARD.tar.gz'
 with tempfile.TemporaryDirectory() as td:
  t=Path(td);dump(t/'BUNDLE_MANIFEST.json',meta)
  with tarfile.open(bundle,'w:gz') as tf:
   _tar_add(tf,ROOT/'stage_c_results/graphs','stage_c_results/graphs');_tar_add(tf,ROOT/'stage_c_robustness_results','stage_c_robustness_results');_tar_add(tf,ROOT/'stage_d_results/STAGE_D_PLAN.json','stage_d_results/STAGE_D_PLAN.json');_tar_add(tf,ROOT/'stage_d_results/packet_run','stage_d_results/packet_run');_tar_add(tf,t/'BUNDLE_MANIFEST.json','BUNDLE_MANIFEST.json')
 (bundle.with_suffix(bundle.suffix+'.sha256')).write_text(f'{sha(bundle)}  {bundle.name}\n',encoding='utf-8');print(f'WROTE {bundle} sha256={sha(bundle)}');return bundle
def secondary_vm3(fetch_external=True):
 role='vm3';w=int(VM['roles'][role]['heavy_workers']);coeff_sha();b5_model_lock_sha256();run('vm3_prepare_simulator',[sys.executable,'src/run_stage_a.py','prepare'])
 run('vm3_prediction_panel_plan',[sys.executable,'src/run_b5_prediction_panel.py','build-plan']);run('vm3_prediction_panel_packet',[sys.executable,'src/run_b5_prediction_panel.py','run','--workers',str(w)])
 run('vm3_structured_graphs',[sys.executable,'src/run_structured_topologies.py','build-graphs','--workers',str(w)]);run('vm3_structured_plan',[sys.executable,'src/run_structured_topologies.py','build-plan','--workers',str(w)]);run('vm3_structured_packet',[sys.executable,'src/run_structured_topologies.py','run','--workers',str(w)])
 if fetch_external:run('vm3_fetch_snob5g',['bash','external/01_FETCH_SNOB5G.sh'])
 run('vm3_external_prepare',[sys.executable,'src/run_external_validation.py','prepare']);run('vm3_external_plan',[sys.executable,'src/run_external_validation.py','build-plan']);run('vm3_external_packet',[sys.executable,'src/run_external_validation.py','run','--workers',str(w)])
 return export_secondary()
def export_secondary():
 meta=machine_record('vm3');meta['bundle_type']='b5_secondary_vm3';bundle=EX/'vm3_SECONDARY_RESULTS.tar.gz'
 with tempfile.TemporaryDirectory() as td:
  t=Path(td);dump(t/'BUNDLE_MANIFEST.json',meta)
  with tarfile.open(bundle,'w:gz') as tf:
   for d in ['b5_prediction_panel_results','structured_topology_results','external_validation_results']:_tar_add(tf,ROOT/d,d)
   _tar_add(tf,t/'BUNDLE_MANIFEST.json','BUNDLE_MANIFEST.json')
 (bundle.with_suffix(bundle.suffix+'.sha256')).write_text(f'{sha(bundle)}  {bundle.name}\n',encoding='utf-8');print(f'WROTE {bundle} sha256={sha(bundle)}');return bundle
def _copy_file_identical(src,dst):
 src,dst=Path(src),Path(dst);dst.parent.mkdir(parents=True,exist_ok=True)
 if dst.exists():
  if sha(src)!=sha(dst):raise RuntimeError(f'non-identical artifact collision: {dst}')
 else:shutil.copy2(src,dst)
def _copy_tree_identical(src,dst):
 src,dst=Path(src),Path(dst)
 for p in src.rglob('*'):
  if p.is_file():_copy_file_identical(p,dst/p.relative_to(src))
def _load_bundle(bundle,expected_role):
 td=tempfile.TemporaryDirectory();t=Path(td.name)
 with tarfile.open(bundle,'r:gz') as tf:_safe_extract(tf,t)
 meta=json.loads((t/'BUNDLE_MANIFEST.json').read_text())
 if meta.get('role')!=expected_role:raise RuntimeError('bundle role mismatch')
 if meta.get('source_manifest_sha256')!=source_manifest_sha() or meta.get('b5_model_lock_sha256')!=b5_model_lock_sha256() or meta.get('stage_a_coefficients_sha256')!=coeff_sha():raise RuntimeError('bundle provenance mismatch')
 return td,t,meta
def _merge_stage_d_plans(plans):
 graphs={};cells={};meta=None
 for p in plans:
  d=json.loads(Path(p).read_text())
  if meta is None:meta={k:d[k] for k in ['protocol','stage_a_solo_goodputs_mbps','rng_runs','states']}
  elif any(d[k]!=meta[k] for k in meta):raise RuntimeError('Stage-D shard plan metadata mismatch')
  for g in d['graphs']:
   k=(g['size'],int(g['seed']))
   if k in graphs and graphs[k]!=g:raise RuntimeError(f'conflicting graph {k}')
   graphs[k]=g
  for c in d['unique_cells']:
   k=c['cell_id']
   if k in cells and cells[k]!=c:raise RuntimeError(f'conflicting cell {k}')
   cells[k]=c
 return {**meta,'graphs':[graphs[k] for k in sorted(graphs)],'unique_cells':[cells[k] for k in sorted(cells)]}
def _summarize_robustness(records):
 rep={'implementation':{'policy':'nominal hard admission enumerated once per graph; all perturbations rescore identical frozen X_adm','distributed_workers':'VM1=2, VM2=3'}}
 for eps in FULL['stage_c_robustness']['eps']:
  rr=[x for x in records if float(x['eps'])==float(eps)]
  rep[str(eps)]={'n':len(rr),'B3_stability':float(np.mean([x['B3_stable'] for x in rr])),'B5_stability':float(np.mean([x['B5_stable'] for x in rr])),'B3_B5_same_fraction':float(np.mean([x['B3_B5_same'] for x in rr]))}
 return rep
def merge_random(vm1,vm2):
 holders=[]
 try:
  td1,t1,m1=_load_bundle(vm1,'vm1');td2,t2,m2=_load_bundle(vm2,'vm2');holders=[td1,td2];dest=ROOT/'stage_c_results/graphs';dest.mkdir(parents=True,exist_ok=True)
  for t in [t1,t2]:_copy_tree_identical(t/'stage_c_results/graphs',dest)
  expected={(label,s) for label,(lo,hi) in VM['merge_policy']['required_seed_ranges'].items() for s in range(lo,hi+1)};got=set()
  for p in dest.glob('*.json'):
   d=json.loads(p.read_text());got.add((d['size'],int(d['seed'])))
  if got!=expected or len(got)!=200:raise RuntimeError(f'primary graph merge mismatch: got {len(got)} expected 200')
  rec=[]
  for t in [t1,t2]:rec+=json.loads((t/'stage_c_robustness_results/ROBUSTNESS_RECORDS.json').read_text())
  keys=[(x['size'],int(x['seed']),float(x['eps']),int(x['rep'])) for x in rec]
  if len(keys)!=len(set(keys)):raise RuntimeError('duplicate robustness units')
  dump(ROOT/'stage_c_robustness_results/ROBUSTNESS_RECORDS.json',rec);dump(ROOT/'stage_c_robustness_results/ROBUSTNESS_SUMMARY.json',_summarize_robustness(rec))
  for t in [t1,t2]:_copy_tree_identical(t/'stage_d_results/packet_run',ROOT/'stage_d_results/packet_run')
  plan=_merge_stage_d_plans([t1/'stage_d_results/STAGE_D_PLAN.json',t2/'stage_d_results/STAGE_D_PLAN.json'])
  if len(plan['graphs'])!=200:raise RuntimeError(f'merged Stage-D plan count {len(plan["graphs"])} != 200')
  dump(ROOT/'stage_d_results/STAGE_D_PLAN.json',plan);run('vm2_merged_stage_c_analysis',[sys.executable,'src/run_stage_c.py','analyze']);run('vm2_merged_stage_d_analysis',[sys.executable,'src/run_stage_d.py','analyze'])
  dump(EX/'RANDOM_MERGE_MANIFEST.json',{'merged_utc':now(),'vm1':m1,'vm2':m2,'random_graphs':200,'stage_d_graphs':200,'b5_model_lock_sha256':b5_model_lock_sha256()});print('RANDOM SHARD MERGE: PASS')
 finally:
  for td in holders:td.cleanup()
def import_secondary(bundle):
 td,t,meta=_load_bundle(bundle,'vm3')
 try:
  for d in ['b5_prediction_panel_results','structured_topology_results','external_validation_results']:_copy_tree_identical(t/d,ROOT/d)
  run('vm2_imported_rq1_analysis',[sys.executable,'src/run_b5_prediction_panel.py','analyze']);run('vm2_imported_structured_analysis',[sys.executable,'src/run_structured_topologies.py','analyze']);run('vm2_imported_external_analysis',[sys.executable,'src/run_external_validation.py','analyze']);dump(EX/'SECONDARY_IMPORT_MANIFEST.json',{'imported_utc':now(),'vm3':meta})
 finally:td.cleanup()
 print('VM3 SECONDARY IMPORT: PASS')
def post_merge(run_stage_e=True):
 if len(list((ROOT/'stage_c_results/graphs').glob('*.json')))!=200:raise RuntimeError('need exactly 200 merged primary graphs')
 if not (ROOT/'b5_prediction_panel_results/RQ1_B5_PREDICTION_SUMMARY.json').exists():raise RuntimeError('RQ1 prediction panel results missing; import VM3 secondary bundle first')
 if not (ROOT/'structured_topology_results/STRUCTURED_TOPOLOGY_SUMMARY.json').exists():raise RuntimeError('structured results missing')
 w=int(VM['roles']['vm2']['heavy_workers']);run('vm2_oracle_plan',[sys.executable,'src/run_stage_d_oracle.py','build-plan']);run('vm2_oracle_packet',[sys.executable,'src/run_stage_d_oracle.py','run','--workers',str(w)])
 if run_stage_e:
  run('vm2_stage_e_preflight',[sys.executable,'src/run_stage_e.py','preflight']);run('vm2_stage_e_load_pilot_selections',[sys.executable,'src/calibrate_stage_e_loads.py','build-selections']);run('vm2_stage_e_load_pilot',[sys.executable,'src/calibrate_stage_e_loads.py','run']);run('vm2_stage_e_build_confirmatory_selections',[sys.executable,'src/run_stage_e.py','build-selections','--workers',str(w)]);run('vm2_stage_e_science',[sys.executable,'src/run_stage_e.py','run'])
 if FULL.get('deathstarbench_validation',{}).get('enabled'):
  run('vm2_deathstarbench_full',[sys.executable,'src/run_deathstarbench_validation.py','full'])
 run('vm2_final_analysis',[sys.executable,'src/analyze_full_campaign.py']);run('vm2_generate_journal_artifacts',[sys.executable,'src/generate_journal_artifacts.py']);run('vm2_build_journal_reproducibility_package',[sys.executable,'src/build_reproducibility_package.py']);print('B5 3-VM CAMPAIGN POST-MERGE COMPLETE')
def status():
 out={'source_manifest_sha256':source_manifest_sha(),'b5_model_lock_sha256':b5_model_lock_sha256(),'stage_a_coefficients_sha256':None,'primary_random_graphs':0,'rq1_prediction_panel':False,'structured':False,'external':False,'oracle':False,'stage_e':False,'deathstarbench':False}
 try:out['stage_a_coefficients_sha256']=coeff_sha()
 except Exception:pass
 out['primary_random_graphs']=len(list((ROOT/'stage_c_results/graphs').glob('*.json'))) if (ROOT/'stage_c_results/graphs').exists() else 0
 for key,p in [('rq1_prediction_panel','b5_prediction_panel_results/RQ1_B5_PREDICTION_SUMMARY.json'),('structured','structured_topology_results/STRUCTURED_TOPOLOGY_SUMMARY.json'),('external','external_validation_results/EXTERNAL_VALIDATION_SUMMARY.json'),('oracle','stage_d_oracle_results/ORACLE_SUMMARY.json'),('stage_e','stage_e_results/RQ3_APPLICATION_SUMMARY.json'),('deathstarbench','deathstarbench_validation_results/DEATHSTARBENCH_SUMMARY.json')]:out[key]=(ROOT/p).exists()
 print(json.dumps(out,indent=2))
def main():
 ap=argparse.ArgumentParser(description='Frozen deterministic B5 three-VM confirmatory runner');sp=ap.add_subparsers(dest='command',required=True)
 q=sp.add_parser('local-preflight');q.add_argument('--role',required=True,choices=['vm1','vm2','vm3']);q.add_argument('--prepare-sim',action='store_true')
 sp.add_parser('coordinator-stage-a');q=sp.add_parser('import-stage-a');q.add_argument('--role',required=True,choices=['vm1','vm3']);q.add_argument('--bundle',type=Path,required=True)
 q=sp.add_parser('random-shard');q.add_argument('--role',required=True,choices=['vm1','vm2']);q=sp.add_parser('secondary-vm3');q.add_argument('--no-fetch-external',action='store_true')
 q=sp.add_parser('merge-random');q.add_argument('--vm1',type=Path,required=True);q.add_argument('--vm2',type=Path,required=True);q=sp.add_parser('import-secondary');q.add_argument('--bundle',type=Path,required=True)
 q=sp.add_parser('post-merge');q.add_argument('--skip-stage-e',action='store_true');sp.add_parser('status');a=ap.parse_args()
 if a.command=='local-preflight':local_preflight(a.role,a.prepare_sim)
 elif a.command=='coordinator-stage-a':coordinator_stage_a()
 elif a.command=='import-stage-a':import_stage_a(a.bundle,a.role)
 elif a.command=='random-shard':random_shard(a.role)
 elif a.command=='secondary-vm3':secondary_vm3(not a.no_fetch_external)
 elif a.command=='merge-random':merge_random(a.vm1,a.vm2)
 elif a.command=='import-secondary':import_secondary(a.bundle)
 elif a.command=='post-merge':post_merge(not a.skip_stage_e)
 else:status()
if __name__=='__main__':main()
