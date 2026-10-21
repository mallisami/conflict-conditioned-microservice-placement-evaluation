import json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

def test_vm_partition_exact_cover():
    vm=json.loads((ROOT/'config/vm_execution.json').read_text()); sets=[]
    for role in ('vm1','vm2'):
        s=set()
        for label,(lo,hi) in vm['random_graph_partition'][role].items():s |= {(label,x) for x in range(int(lo),int(hi)+1)}
        sets.append(s)
    assert len(sets[0])==80 and len(sets[1])==120 and sets[0].isdisjoint(sets[1]) and len(sets[0]|sets[1])==200

def test_vm_worker_profile_and_stage_e_map():
    vm=json.loads((ROOT/'config/vm_execution.json').read_text())
    assert [vm['roles'][r]['heavy_workers'] for r in ('vm1','vm2','vm3')]==[2,3,1]
    assert vm['stage_e_rack_map']=={'rack-a':'vm2','rack-b':'vm1','rack-c':'vm3'}

def test_merge_stage_d_plans_exact_union(tmp_path):
    sys.path.insert(0,str(ROOT/'src'));import vm_cluster_runner as v
    common={'protocol':'paper2-b5-stage-d','stage_a_solo_goodputs_mbps':[1,2,3,4,5,6],'rng_runs':[811,812,813],'states':['conflict-dense']}
    p1=tmp_path/'p1.json';p2=tmp_path/'p2.json';p1.write_text(json.dumps({**common,'graphs':[{'size':'n8','seed':91001}],'unique_cells':[{'cell_id':'d-a','x':1}]}));p2.write_text(json.dumps({**common,'graphs':[{'size':'n8','seed':91002}],'unique_cells':[{'cell_id':'d-b','x':2}]}))
    m=v._merge_stage_d_plans([p1,p2]);assert [g['seed'] for g in m['graphs']]==[91001,91002];assert [c['cell_id'] for c in m['unique_cells']]==['d-a','d-b']
