#!/usr/bin/env python3
"""Extract one or all raw-data study ZIPs to their original study folders."""
from pathlib import Path
import argparse, zipfile
ROOT=Path(__file__).resolve().parents[1]
RAW=ROOT/'04_Raw_Experimental_Data'
STUDIES=sorted(p.stem for p in RAW.glob('*.zip'))
def main():
    ap=argparse.ArgumentParser(description=__doc__)
    g=ap.add_mutually_exclusive_group(required=True)
    g.add_argument('--study',choices=STUDIES,help='study archive name without .zip')
    g.add_argument('--all',action='store_true',help='extract all ten studies (about 9.6 GB)')
    args=ap.parse_args(); selected=STUDIES if args.all else [args.study]
    for study in selected:
        archive=RAW/(study+'.zip'); target=RAW/study; target.mkdir(parents=True,exist_ok=True)
        with zipfile.ZipFile(archive) as z:
            bad=z.testzip()
            if bad: raise SystemExit(f'ZIP CRC failure in {archive.name}: {bad}')
            for info in z.infolist():
                if info.is_dir() or info.filename.startswith('__ARCHIVE_METADATA__/'): continue
                dest=(target/info.filename).resolve()
                if not dest.is_relative_to(target.resolve()): raise SystemExit(f'Unsafe archive path: {info.filename}')
                dest.parent.mkdir(parents=True,exist_ok=True)
                with z.open(info) as src, dest.open('wb') as out:
                    while True:
                        chunk=src.read(1024*1024)
                        if not chunk: break
                        out.write(chunk)
        print(f'Extracted {study} -> {target}')
if __name__=='__main__': main()
