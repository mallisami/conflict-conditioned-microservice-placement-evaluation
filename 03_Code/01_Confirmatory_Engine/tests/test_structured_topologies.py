import importlib.util,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
import run_structured_topologies as S

def test_structured_edge_counts():
    assert len(S.edges('pipeline',8))==7
    assert len(S.edges('fanout_fanin',8))==12
    assert len(S.edges('hub_spoke',8))==14
    assert len(S.edges('mesh',8))==20
    assert len(S.edges('mesh',12))==34
    assert len(S.edges('mesh',16))==48

def test_structured_schedule_count():
    n=0
    for top in S.CFG['topologies']:
        for s in S.CFG['sizes']:
            n += len(list(S.seed_range(top,s['label'])))
    assert n==80

def test_structured_problem_flow_identity():
    p,meta=S.structured_problem('pipeline','n8',81001)
    assert p is not None
    assert len(p.flows)==7
    assert p.max_relocations==2
    assert all(f.source_replica != f.destination_replica for f in p.flows)
