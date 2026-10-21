# Reproduction guide

## Reproduce primary results from this public checkout

Without obtaining any large raw archive, run from the repository root:

```bash
python 00_START_HERE/verify_public_graph_results.py
```

This verifies the reported primary paired means and the RQ2 change/win/loss/tie counts from the public graph-level and Kubernetes cell tables. The separate complete-release verifier documented below additionally checks original raw archives; it is not intended to run against the partial public checkout. Neither verifier reruns the simulator or independently recalculates every confidence interval.


> **Public checkout status:** This guide describes the full independently verified offline reviewer archive. Original raw ZIP archives are **not yet deposited** in this public repository. Do not run the full-archive verifier against an incomplete checkout or interpret a missing-archive error as a failed experimental result.

## 1. Verify before analysis

Run from the extracted release root:

```bash
python 00_START_HERE/verify_release.py
```

The verifier checks the release SHA-256 manifest, every raw-data ZIP archive and its per-file SHA-256 manifest, then recomputes selected published point estimates for RQ1, RQ2, and fresh Kubernetes RQ3. It is offline verification: it does not rerun ns-3, refit B3/B5, or start Kubernetes workloads. The full integrity pass reads approximately 9.6 GB and may take several minutes.

## 2. Locate evidence

Use `EXPERIMENT_ARTIFACT_MAP.md` to trace a result to its governing protocol, runner, raw study archive, derived result table, and manuscript display. Use `RAW_DATA_INDEX.csv` for study-level selection and `RAW_DATA_FILE_INDEX.csv` to search individual archived paths.

## 3. Extract only what you need

Raw measurements are stored as ten study-level ZIP archives under `04_Raw_Experimental_Data/`. Each archive preserves the original relative paths and carries a file-level SHA-256 manifest. To restore a study to the directory layout expected by existing code:

```bash
python 00_START_HERE/unpack_raw_data.py --study 02_RQ2_Selection_Graphs
```

Use `--all` only if you want to extract every raw study (approximately 9.6 GB). The helper skips the archive's internal metadata directory when extracting raw files.

## 4. Rerun code only when intended

The confirmatory engine lives in `03_Code/01_Confirmatory_Engine/`; the fresh Kubernetes extension lives in `03_Code/02_RQ3_Fresh_Kubernetes_Extension/`. Follow the current protocol and each directory's README. Extract the relevant raw study first if the runner expects its prior records in the raw-data directory. Full simulator and Kubernetes reruns are resource-intensive. `RUN_RQ3_COMPLETE.sh` launches/resumes the fresh Kubernetes experiment and is not needed to verify archived results.

## 5. Scientific scope

See `02_Methods_and_Configuration/REPRODUCIBILITY_SCOPE.md` for availability boundaries. No native TraDE/Diktyo performance results, physical-radio validation, or completed DeathStarBench results are included or implied.
