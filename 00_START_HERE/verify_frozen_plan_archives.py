#!/usr/bin/env python3
"""Verify recovered frozen execution plans and their lossless compressed containers."""
from hashlib import sha256
from pathlib import Path
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[1]
ARCHIVES = (
    ("02_Methods_and_Configuration/02_Experiment_Plans/Oracle_Execution/ORACLE_PLAN.json.zip",
     "3fd1d83eada416adcacb33eafa6d163d6ffc7de7cad1fce45edf6f83a977d2b9",
     "02_Methods_and_Configuration/02_Experiment_Plans/Oracle_Execution/ORACLE_PLAN.json",
     4445441, "601c53bd1200b9dbefabbcf3bb8a946cba2b10b8428ac73438d37716719ead7e"),
    ("02_Methods_and_Configuration/02_Experiment_Plans/RQ2_Packet_Execution/STAGE_D_PLAN.json.zip",
     "c36c243b824ad146334921cbe434d616b9cbecc8b4e1fcf4a4e72998d7868e2b",
     "02_Methods_and_Configuration/02_Experiment_Plans/RQ2_Packet_Execution/STAGE_D_PLAN.json",
     6209838, "42534a8cf3f1c71a7da26e0fff8788c8fc6df06610922a3f157456ff494b0e1a"),
)
for archive, outer_hash, member, length, inner_hash in ARCHIVES:
    path = ROOT / archive
    assert sha256(path.read_bytes()).hexdigest() == outer_hash, f"ZIP mismatch: {archive}"
    with ZipFile(path) as z:
        assert z.namelist() == [member], f"Unexpected ZIP members: {archive}"
        data = z.read(member)
    assert len(data) == length, f"Wrong uncompressed length: {member}"
    assert sha256(data).hexdigest() == inner_hash, f"Wrong JSON digest: {member}"
    print(f"PASS {member}: {length:,} bytes")
print("FROZEN PLAN INTEGRITY: PASS")
