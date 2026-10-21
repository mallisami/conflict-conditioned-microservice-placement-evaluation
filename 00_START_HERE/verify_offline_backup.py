#!/usr/bin/env python3
"""Authenticate the retained full reviewer backup and original raw study ZIPs."""
import argparse
import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXPECTED = "4e683de510c5bb45c5687c2f78b14fe10849ca8023009e638b749127ceae2752"

def checksum(p):
    h = hashlib.sha256()
    with p.open("rb") as file:
        for chunk in iter(lambda: file.read(8 * 1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()

def verify(p, expected):
    if not p.is_file():
        raise SystemExit(f"FAIL missing {p}")
    actual = checksum(p)
    if actual != expected:
        raise SystemExit(f"FAIL {p}: expected {expected}, got {actual}")
    print(f"PASS {p}: {actual}")

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--archive", type=Path, help="Complete 417,004,855-byte compressed author backup")
    parser.add_argument("--root", type=Path, help="Extracted archive root (contains 04_Raw_Experimental_Data)")
    args = parser.parse_args()
    if not args.archive and not args.root:
        parser.error("Supply --archive or --root")
    if args.archive:
        if not args.archive.is_file() or args.archive.stat().st_size != 417004855:
            raise SystemExit("FAIL missing archive or incorrect compressed length")
        verify(args.archive, EXPECTED)
    if args.root:
        manifest = ROOT / "00_START_HERE/OFFLINE_RAW_STUDY_SHA256SUMS.txt"
        entries = [line.split("  ", 1) for line in manifest.read_text().splitlines() if line.strip()]
        if len(entries) != 10:
            raise SystemExit("FAIL expected 10 original study digests")
        for expected, relative in entries:
            verify(args.root / relative, expected)
    print("PASS specified SHA-256 checks; full record audit requires extracted 00_START_HERE/verify_release.py.")

if __name__ == "__main__":
    main()
