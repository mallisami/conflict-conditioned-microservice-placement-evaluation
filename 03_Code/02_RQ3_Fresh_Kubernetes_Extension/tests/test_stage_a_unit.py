import json, math, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
import run_stage_a as M

def test_self_test_counts():
    x=M.self_test(check_disk=False)
    assert x['science_intents']==2700 and x['calibration_intents']==1350 and x['holdout_intents']==1350

def test_rate_construction_exact_U():
    g=[2100,2110,2120,2130,2140,2150]
    cells=M.phase_cells('calibration',g)
    assert len(cells)==1350
    for c in cells[:100]:
        s=float(c['resource_share']); implied=sum(r/gg for r,gg in zip(c['rates_mbps'],g) if r>0)/s
        assert math.isclose(implied,float(c['U']),rel_tol=1e-10,abs_tol=1e-10)

def test_split_disjoint():
    cal={c['cell_id'] for c in M.INTENTS if c['split']=='calibration'}
    ho={c['cell_id'] for c in M.INTENTS if c['split']=='holdout'}
    assert len(cal)==1350 and len(ho)==1350 and not (cal&ho)
