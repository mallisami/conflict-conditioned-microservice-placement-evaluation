import math,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"src"))
from contention_features import from_airtime_by_directed_pair
def test_balanced_two():
    s=from_airtime_by_directed_pair({"a>b":1,"b>a":1},4)
    assert math.isclose(s.utilization,.5) and s.active_streams==2 and math.isclose(s.n_eff,2)
def test_concentrated():
    s=from_airtime_by_directed_pair({"a>b":9,"b>a":1},20)
    assert 1<s.n_eff<2
def test_zero():
    s=from_airtime_by_directed_pair({},10)
    assert s.utilization==0 and s.active_streams==0 and s.n_eff==0
