import json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
import rq3_selector as S

def test_lock_values():
    cfg=json.loads((ROOT/'config/rq3_extension.json').read_text());assert cfg['load_multiplier']==2.0;assert cfg['panel_a']['seed_end']-cfg['panel_a']['seed_start']+1==128;assert cfg['panel_b']['seed_end']-cfg['panel_b']['seed_start']+1==128

def test_selector_reproduces_one_historical_seed():
    ref=json.loads((ROOT/'PROVENANCE/reference_stage_e_selections_98001_98040.json').read_text())['98001'];r=S.solve_seed(98001)
    assert r['x_adm_sha256']==ref['x_adm_sha256'];assert r['selections']['B3_STRICT']['placement']==ref['B3_STRICT'];assert r['selections']['B5_NOTIE']['placement']==ref['B5_NOTIE'];assert r['selections']['B5_COMPLETE']['placement']==ref['B5_COMPLETE']

def test_b3_stabilizer_is_exact_frozen_rule():
    r=S.solve_seed(98001);x=r['selections']['B3_STABILIZED'];assert abs(x['near_margin']-0.002833387432321216)<1e-15;assert x['score']<=x['strict_min_score']+x['near_margin']+1e-12
