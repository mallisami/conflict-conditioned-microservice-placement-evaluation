#!/usr/bin/env python3
"""Verify curated RQ3 code/input hashes before an intentional experiment rerun."""
from pathlib import Path
import hashlib,sys
ROOT=Path(__file__).resolve().parents[1]
errors=[]
# Check the curated RQ3 code/input manifest.
manifest=ROOT/'PACKAGE_SHA256SUMS.txt'
if not manifest.is_file():
    errors.append(('PACKAGE_SHA256SUMS.txt','MISSING'))
else:
    for line in manifest.read_text(encoding='utf-8').splitlines():
        if not line.strip(): continue
        expected,rel=line.split('  ',1)
        p=ROOT/rel
        if not p.is_file(): errors.append((rel,'MISSING')); continue
        h=hashlib.sha256()
        with p.open('rb') as f:
            for chunk in iter(lambda:f.read(1024*1024),b''): h.update(chunk)
        if h.hexdigest()!=expected: errors.append((rel,'HASH_MISMATCH'))
# Verify every preselected graph against the frozen pre-run hash list.
sel=ROOT/'PRE_RUN_FREEZE'/'SELECTION_SHA256SUMS.txt'
if not sel.is_file(): errors.append(('PRE_RUN_FREEZE/SELECTION_SHA256SUMS.txt','MISSING'))
else:
    for line in sel.read_text(encoding='utf-8').splitlines():
        if not line.strip(): continue
        expected,rel=line.split(None,1); rel=rel.strip().lstrip('*')
        p=ROOT/'PRE_RUN_FREEZE'/rel
        if not p.is_file(): errors.append((rel,'MISSING_SELECTION')); continue
        if hashlib.sha256(p.read_bytes()).hexdigest()!=expected: errors.append((rel,'SELECTION_HASH_MISMATCH'))
# Verify the frozen coefficient/model lock sidecars.
for rel,side in [('b3_lock/frozen_coefficients.json','b3_lock/frozen_coefficients.sha256'),('b5_lock/B5_MODEL_LOCK.json','b5_lock/B5_MODEL_LOCK.sha256')]:
    p=ROOT/rel; q=ROOT/side
    if not p.is_file() or not q.is_file(): errors.append((rel,'LOCK_OR_HASH_MISSING')); continue
    expected=q.read_text(encoding='utf-8').split()[0]
    if hashlib.sha256(p.read_bytes()).hexdigest()!=expected: errors.append((rel,'LOCK_HASH_MISMATCH'))
if errors:
    print('RQ3 INPUT VERIFICATION FAILED:',errors[:25]); sys.exit(2)
print('RQ3 FROZEN INPUT VERIFICATION: PASS')
