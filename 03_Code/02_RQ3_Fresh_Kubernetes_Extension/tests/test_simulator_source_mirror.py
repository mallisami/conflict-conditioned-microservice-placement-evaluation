from pathlib import Path
import hashlib

ROOT = Path(__file__).resolve().parents[1]
LOCAL_SOURCE = ROOT / "simulator" / "evaluate_shared_airtime_boundary.cc"
CANONICAL_SOURCE = ROOT.parent / "01_Confirmatory_Engine" / "simulator" / "evaluate_shared_airtime_boundary.cc"
EXPECTED_SHA256 = "d8f262c864448cc6a9910d121d3cb9a46074c0d6264b5ce4c5a397d268b8913a"


def test_extension_simulator_source_is_exact_canonical_mirror():
    assert LOCAL_SOURCE.is_file(), "the extension's Stage-A source path is required"
    assert CANONICAL_SOURCE.is_file(), "the canonical archived simulator source is required"
    local_bytes = LOCAL_SOURCE.read_bytes()
    assert local_bytes == CANONICAL_SOURCE.read_bytes(), "extension source must remain byte-identical"
    assert hashlib.sha256(local_bytes).hexdigest() == EXPECTED_SHA256
