#!/usr/bin/env python3
"""Validate public GitHub contents; the original ten raw ZIPs are excluded.

Manifest deliberately excludes itself to avoid a self-referential checksum.
"""
from pathlib import Path
import hashlib
import sys

root = Path(__file__).resolve().parent
manifest_path = root / "PUBLIC_FILE_SHA256SUMS.txt"
entries = {}
errors = []

for no, line in enumerate(manifest_path.read_text(encoding="utf-8").splitlines(), 1):
    if not line.strip():
        continue
    try:
        expected, relative = line.split("  ", 1)
    except ValueError:
        errors.append(f"INVALID ROW {no}: no two-space delimiter")
        continue
    if not relative or len(expected) != 64 or any(c not in "0123456789abcdef" for c in expected):
        errors.append(f"INVALID ROW {no}: hash or path")
        continue
    path = Path(relative)
    if path.is_absolute() or ".." in path.parts or relative in entries or relative == manifest_path.name:
        errors.append(f"INVALID ROW {no}: unsafe, duplicated, or self-referential path")
        continue
    entries[relative] = expected

actual_files = set()
for item in root.rglob("*"):
    if not item.is_file() or ".git" in item.relative_to(root).parts:
        continue
    relative = item.relative_to(root).as_posix()
    if relative == manifest_path.name:
        continue
    actual_files.add(relative)

for relative in sorted(entries):
    item = root / relative
    if not item.is_file():
        errors.append(f"MISSING {relative}")
        continue
    digest = hashlib.sha256()
    with item.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    value = digest.hexdigest()
    if value != entries[relative]:
        errors.append(f"HASH MISMATCH {relative}: expected {entries[relative]}, actual {value}")
for relative in sorted(actual_files - entries.keys()):
    path = root / relative
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    errors.append(f"NOT INDEXED {relative}: actual {digest}")

if errors:
    for error in errors:
        print(error)
    sys.exit(f"FAIL: {len(errors)} public file-integrity/coverage issue(s)")
print(f"PASS: {len(entries)} public repository files match the complete published-subset manifest")
print("SCOPE: no ten original raw-study ZIPs, full-archive verification, simulator rerun, or historical B3 refit")
