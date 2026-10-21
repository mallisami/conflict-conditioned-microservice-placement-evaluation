#!/usr/bin/env python3
"""Verify only the files actually included in the published subset."""
import hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parent
manifest=ROOT/'PUBLIC_FILE_SHA256SUMS.txt'
rows=[x.strip() for x in manifest.read_text().splitlines() if x.strip()]
for row in rows:
    digest,relative=row.split('  ',1)
    f=ROOT/relative
    if not f.is_file(): raise SystemExit(f'MISSING: {relative}')
    h=hashlib.sha256()
    with f.open('rb') as stream:
        for chunk in iter(lambda:stream.read(1<<20),b''):h.update(chunk)
    if h.hexdigest()!=digest:raise SystemExit(f'HASH MISMATCH: {relative}')
print(f'PASS: {len(rows)} published files checked. This does not verify omitted raw archives.')
