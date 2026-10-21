# Reproduction guide

This guide separates **quick verification of publicly deposited results** from **full offline-archive integrity** and **resource-intensive reruns**. Start from the repository root.

## 1. Run the public result check (no large downloads)

```bash
python3 00_START_HERE/verify_public_graph_results.py
```

This checks the primary graph-level paired mean differences for RQ1, RQ2, original and fresh Kubernetes panels, and the RQ2 selection/win/loss/tie accounting. It uses public CSV tables and the Python standard library. It does **not** generate new simulation outcomes. Independently recalculate selected primary percentile-bootstrap intervals over paired graph identities with `python3 00_START_HERE/recompute_public_bootstrap_cis.py --resamples 100000`; historical bootstrap random draws and every secondary interval are not reproduced.

### Public supporting results

For six secondary RQ2 policy contrasts, B5-minus-B3 state transfer, the fixed three-state composite and exploratory graph-size effects, run `python3 00_START_HERE/verify_public_supporting_results.py`. This independently recalculates graph-level point estimates and does not purport to reproduce every historical signed-rank or bootstrap analysis.

## 2. Validate deposited source and result files

```bash
python3 verify_public_subset.py
```

The manifest `PUBLIC_FILE_SHA256SUMS.txt` is specific to public GitHub files. The check compares recorded SHA-256 digests with current file bytes and detects unindexed files. It does not cover ZIP archives or historical inputs that are absent.

## 3. Trace a claim to its inputs

The [experiment–artifact crosswalk](EXPERIMENT_ARTIFACT_MAP.md) connects each question to protocols, runner code, original study-archive names and derived results. The [data dictionary](DATA_DICTIONARY.md) describes file formats and the archived study ZIPs. The [data availability page](../DATA_AVAILABILITY.md) distinguishes public files from the full offline evidence release.

| Intended check | File path |
| --- | --- |
| RQ1 prediction | [Graph metrics](../05_Results_and_Analysis/01_RQ1_Prediction/PREDICTION_PANEL_GRAPH_METRICS.csv) |
| RQ2 paired delivery and selection | [Graph-level comparison](../05_Results_and_Analysis/02_RQ2_Selection_and_Packet_Execution/RQ2_Selection_and_Delivery_Graph_Level.csv) |
| Original Kubernetes panel | [Execution cells](../05_Results_and_Analysis/07_Initial_Kubernetes_Experiment/STAGE_E_CELLS.csv) |
| Fresh Kubernetes panel | [Fresh extension results](../05_Results_and_Analysis/08_Fresh_Kubernetes_RQ3/) |

## 4. Recovered frozen execution plans

Verify original JSON SHA-256s and compressed containers with `python3 00_START_HERE/verify_frozen_plan_archives.py`. Extract either ZIP from repository root using `python3 -m zipfile -e ZIPFILE .`. These are execution inputs, not the original execution logs.

## 5. Full archived evidence (not included on GitHub)

The complete offline reviewer archive has `04_Raw_Experimental_Data/` (ten ZIPs), an original top-level release manifest and a per-file raw index. **Do not run the original full-archive verifier against this public subset.**

After obtaining the complete release legitimately and extracting it to its original root directory:

```bash
python3 00_START_HERE/verify_release.py
python3 00_START_HERE/unpack_raw_data.py --study 02_RQ2_Selection_Graphs
```

The original verifier performs archived-file and record integrity checks and selected point-estimate checks. Raw unpacking requires the specified ZIP archive. Neither command reruns ns-3 or the Kubernetes cluster.

## 6. Experimental reruns (optional and environment dependent)

The frozen [confirmatory implementation](../03_Code/01_Confirmatory_Engine/) and [separate Kubernetes extension](../03_Code/02_RQ3_Fresh_Kubernetes_Extension/) include their own READMEs and scripts. Their frozen experiment plans, dependencies, model locks, resource needs, and any unavailable original inputs must be respected. Do not run `RUN_RQ3_COMPLETE.sh` to perform a routine data verification: it launches/resumes a resource-intensive experiment.

**Known constraints:** The original B3 Stage-A calibration CSV is not available; the public checkout has no raw-study ZIPs and cannot independently reconstruct every simulator result. No native TraDE/Diktyo benchmark results, physical 60-GHz validation, or completed DeathStarBench results are claimed.
