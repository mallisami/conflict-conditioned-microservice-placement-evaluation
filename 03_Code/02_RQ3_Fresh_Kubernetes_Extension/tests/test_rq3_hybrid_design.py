import json,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

def test_hybrid_run_plan():
    p=json.loads((ROOT/'PRE_RUN_FREEZE/RUN_PLAN.json').read_text())
    assert p['n_cells']==1152
    cells=p['cells']
    assert sum(1 for c in cells if c['replicate']==1)==768
    assert sum(1 for c in cells if c['replicate'] in (2,3))==384
    ids={(c['panel'],c['seed'],c['method'],c['replicate']) for c in cells}
    assert len(ids)==1152

def test_repeatability_subset_lock():
    r=json.loads((ROOT/'PRE_RUN_FREEZE/REPEATABILITY_SUBSET_LOCK.json').read_text())
    assert len(r['panel_a']['seeds'])==32 and len(r['panel_b']['seeds'])==32
    assert r['primary_inference_uses_additional_repeats'] is False
    assert r['performance_outcomes_observed_before_freeze']==0

def test_primary_inference_uniform():
    c=json.loads((ROOT/'config/rq3_extension.json').read_text())
    assert c['primary_analysis_replicate']==1
    assert c['expected_science_cells']==1152
