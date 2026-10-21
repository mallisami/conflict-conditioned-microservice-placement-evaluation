import json, math, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
import run_stage_c as C
import run_stage_d as D
import run_stage_e as E

def coeff_file(tmp_path):
    obj={'fits':{}}
    for s in [0.25,0.5,0.75]:
        obj['fits'][str(s)]={
            'B3_U_only':[0,0.05,0.05],
            'A1_U_Neff':[0,0.05,0.05,0.01,0.01],
            'B4_full_shape':[0,0.05,0.05,0.01,0.01,0.01,0.01],
        }
    p=tmp_path/'coef.json';p.write_text(json.dumps(obj));return p

def test_stage_c_n8_exact_same_set_and_rankers(tmp_path):
    r=C.solve_graph(('n8',71001,str(coeff_file(tmp_path))))
    assert r['valid'] and r['n_admissible']>1 and len(r['x_adm_sha256'])==64
    assert set(r['selections'])=={'B0_AFFINITY_ADMISSION','B1_MAPE_CAP_WS','B2_MAX_HEADROOM','B3_U_ONLY','A1_U_NEFF','B4_FULL_SHAPE','B5_CONFLICT_RANK','B5_MAE_ONLY','B5_GLOBAL_RANK','B5_NOTIE'}
    assert all(x['worst_u']<=1+1e-9 for x in r['selections'].values())

def test_stage_d_mapping_preserves_planner_u():
    p,_=C.build_scaled_problem('n8',71001)
    assert p is not None
    pl=dict(p.current_placement)
    good=[2000.0]*6
    for sid in ['conflict-dense','persistent-degradation','partial-blockage']:
        cells,_=D.make_group_cells(p,pl,sid,good)
        sc=next(s for s in p.scenarios if s.scenario_id==sid)
        for c in cells:
            implied=sum((r/g) for r,g in zip(c['rates_mbps'],good) if r>0)/c['duty_fraction']
            assert math.isclose(implied,c['planner_group_u'],rel_tol=1e-10,abs_tol=1e-10)

def test_stage_e_n8_maps_one_planning_node_per_rack():
    info={'rack_to_node':{'rack-a':'host-a','rack-b':'host-b','rack-c':'host-c'}}
    ep,node_map=E.execution_problem(71001,info)
    assert len(ep.nodes)==3
    assert {n.node_id for n in ep.nodes}=={'host-a','host-b','host-c'}
    assert set(node_map.values())=={'host-a','host-b','host-c'}
    assert all(math.isclose(r.cpu_request,0.1) and math.isclose(r.memory_request_mb,128.0) for r in ep.replicas)
