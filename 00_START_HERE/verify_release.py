#!/usr/bin/env python3
"""Verify release hashes, every archived raw file, and selected published estimates.

Standard-library only. Does not rerun ns-3, refit models, or start Kubernetes.
Run from any working directory: python 00_START_HERE/verify_release.py
Full verification reads approximately 9.6 GB of raw records and may take several minutes.
"""
from pathlib import Path
import hashlib, csv, json, math, statistics, zipfile
from collections import defaultdict
ROOT=Path(__file__).resolve().parents[1]
MANIFEST=ROOT/'SHA256SUMS.txt'
RAW=ROOT/'04_Raw_Experimental_Data'

def hash_file(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        for chunk in iter(lambda:f.read(1024*1024),b''): h.update(chunk)
    return h.hexdigest()

def check_hashes():
    bad=[]; checked=0
    for line in MANIFEST.read_text(encoding='utf-8').splitlines():
        if not line.strip(): continue
        expected,rel=line.split('  ',1); p=ROOT/rel
        if not p.is_file(): bad.append((rel,'MISSING')); continue
        got=hash_file(p); checked+=1
        if got!=expected: bad.append((rel,'HASH_MISMATCH'))
    if bad: raise SystemExit('RELEASE SHA-256 FAILED: '+repr(bad[:20]))
    print(f'Release SHA-256: PASS ({checked} files, including all ten raw study archives)',flush=True)

def check_raw_archives():
    total=0
    archives=sorted(RAW.glob('*.zip'))
    if len(archives)!=10: raise SystemExit(f'Expected 10 raw study archives, found {len(archives)}')
    for archive in archives:
        with zipfile.ZipFile(archive) as z:
            names=set(z.namelist())
            mname='__ARCHIVE_METADATA__/SHA256SUMS.txt'
            if mname not in names: raise SystemExit(f'Missing inner manifest: {archive.name}')
            entries={}
            for line in z.read(mname).decode('utf-8').splitlines():
                if line.strip():
                    h,rel=line.split('  ',1); entries[rel]=h
            raw_names={n for n in names if not n.startswith('__ARCHIVE_METADATA__/') and not n.endswith('/')}
            if raw_names!=set(entries):
                missing=sorted(set(entries)-raw_names)[:5]; extra=sorted(raw_names-set(entries))[:5]
                raise SystemExit(f'Raw archive inventory mismatch in {archive.name}: missing={missing}, extra={extra}')
            checked=0
            for rel,expected in entries.items():
                h=hashlib.sha256()
                with z.open(rel) as f:
                    for chunk in iter(lambda:f.read(1024*1024),b''): h.update(chunk)
                if h.hexdigest()!=expected: raise SystemExit(f'Raw-file SHA-256 failed: {archive.name}:{rel}')
                checked+=1
            total+=checked
            print(f'Raw archive PASS: {archive.name} ({checked} files)',flush=True)
    if total!=108727: raise SystemExit(f'Expected 108727 raw files, verified {total}')
    print(f'All raw-data member SHA-256 checks: PASS ({total} files)',flush=True)

def rows(path):
    with path.open(newline='',encoding='utf-8-sig') as f: return list(csv.DictReader(f))
def near(a,b,tol=1e-6): return abs(a-b)<=tol
def check(name,n,value,expected_n,expected_value,tol=1e-6):
    ok=(n==expected_n and near(value,expected_value,tol))
    print(f'{name}: n={n}, mean={value:.12f}; expected n={expected_n}, mean={expected_value:.12f}: {"PASS" if ok else "FAIL"}')
    if not ok: raise SystemExit(2)
def main():
    check_hashes()
    check_raw_archives()
    pred=rows(ROOT/'05_Results_and_Analysis/01_RQ1_Prediction/PREDICTION_PANEL_GRAPH_METRICS.csv')
    for split,label,expected in [('ID','RQ1 in-distribution MAE difference',0.0013081413131482166),('OOD','RQ1 traffic-shift MAE difference',0.003650035911987598)]:
        x=[float(r['mae_B5_CONFLICT_RANK'])-float(r['mae_B3_U_ONLY']) for r in pred if r['split'].upper()==split]
        check(label,len(x),statistics.mean(x),60,expected)
    dr=rows(ROOT/'05_Results_and_Analysis/02_RQ2_Selection_and_Packet_Execution/STAGE_D_GRAPH_METHOD_STATE.csv')
    pairs=defaultdict(dict)
    for r in dr:
        if r['state']=='conflict-dense' and r['method'] in ('B3_U_ONLY','B5_CONFLICT_RANK'):
            pairs[(r['size'],r['seed'])][r['method']]=float(r['delivered_fraction'])
    diffs=[v['B5_CONFLICT_RANK']-v['B3_U_ONLY'] for v in pairs.values() if set(v)=={'B3_U_ONLY','B5_CONFLICT_RANK'}]
    check('RQ2 conflict-dense delivered-fraction difference',len(diffs),statistics.mean(diffs),200,-0.0019799247653576654)
    wins=sum(x>1e-12 for x in diffs); losses=sum(x< -1e-12 for x in diffs); ties=len(diffs)-wins-losses
    print(f'RQ2 directional decomposition: wins={wins}, losses={losses}, ties={ties}; expected 81/59/60: {"PASS" if (wins,losses,ties)==(81,59,60) else "FAIL"}')
    if (wins,losses,ties)!=(81,59,60): raise SystemExit(2)
    graph_archive=RAW/'02_RQ2_Selection_Graphs.zip'
    changed=0; b5_mae_changed=0; graph_count=0
    with zipfile.ZipFile(graph_archive) as z:
        graph_names=sorted(n for n in z.namelist() if n.startswith('graphs/') and n.endswith('.json'))
        for name in graph_names:
            obj=json.loads(z.read(name).decode('utf-8')); s=obj.get('selections',{}); graph_count+=1
            if 'B3_U_ONLY' in s and 'B5_CONFLICT_RANK' in s and s['B3_U_ONLY'].get('placement_key')!=s['B5_CONFLICT_RANK'].get('placement_key'): changed+=1
            if 'B5_MAE_ONLY' in s and 'B5_CONFLICT_RANK' in s and s['B5_MAE_ONLY'].get('placement_key')!=s['B5_CONFLICT_RANK'].get('placement_key'): b5_mae_changed+=1
    print(f'RQ2 selection records: graphs={graph_count}, B3/B5 changed={changed}, B5/B5-MAE-only changed={b5_mae_changed}; expected 200/140/1: {"PASS" if (graph_count,changed,b5_mae_changed)==(200,140,1) else "FAIL"}')
    if (graph_count,changed,b5_mae_changed)!=(200,140,1): raise SystemExit(2)
    fresh=rows(ROOT/'05_Results_and_Analysis/08_Fresh_Kubernetes_RQ3/RQ3_MAIN_INFERENCE_CELLS.csv')
    groups=defaultdict(dict)
    for r in fresh:
        if str(r.get('replicate','1'))!='1': continue
        groups[(r['panel'],r['seed'])][r['method']]=float(r['completion'])
    a=[v['B5_COMPLETE']-v['B3_STRICT'] for v in groups.values() if 'B5_COMPLETE' in v and 'B3_STRICT' in v]
    check('Fresh RQ3 B5 complete minus B3 strict',len(a),statistics.mean(a),256,-0.005678518,tol=2e-6)
    b=[v['B5_COMPLETE']-v['B3_STABILIZED'] for (panel,seed),v in groups.items() if panel=='A' and 'B5_COMPLETE' in v and 'B3_STABILIZED' in v]
    check('Fresh RQ3 matched-stabilizer contrast (panel A)',len(b),statistics.mean(b),128,-0.007082988,tol=2e-6)
    all_cells=rows(ROOT/'05_Results_and_Analysis/08_Fresh_Kubernetes_RQ3/RQ3_ALL_CELLS.csv')
    print(f'Fresh RQ3 all-cell records: {len(all_cells)}; expected 1152: {"PASS" if len(all_cells)==1152 else "FAIL"}')
    if len(all_cells)!=1152: raise SystemExit(2)
    print('All release integrity and selected point-estimate checks passed.')
if __name__=='__main__': main()
