# Reproducibility scope

## What this **public GitHub repository** contains

- Frozen source and model locks for the original confirmatory comparison and separate fresh Kubernetes extension.
- Prespecified protocols, configuration files and the experiment plans **actually deposited in GitHub**.
- Graph-level RQ1/RQ2 result tables, original high-load Kubernetes records, fresh-extension results and supporting analyses.
- Standard-library point-estimate verification and a public-file SHA-256 manifest.

Run `python3 00_START_HERE/verify_public_graph_results.py` from the repository root for public graph-level checks. Run `python3 verify_public_subset.py` for checksums.

## What exists in the **separate complete offline reviewer archive**, but not here

The ten original raw-study ZIP archives, 108,727 preserved raw record hashes, the full release manifest and the large per-record raw-data file index. The journal's manuscript PDFs, editable LaTeX and figures are distributed separately and do not belong in this GitHub source repository. The archive's `verify_release.py` requires the complete archive, **not** this public subset.

## Explicit scientific limitations

- The original B3 Stage-A `calibration_aggregated.csv` was not recovered. Frozen B3 coefficients are available but that historical fit cannot be independently regenerated.
- A few large original plans are not public. Use `PUBLIC_DEFERRED_FILE_INDEX.csv`; files already present in GitHub are **not** listed as deferred.
- The upstream SNOB5G data are not mirrored. External access and licensing conditions remain with the provider.
- ns-3 and Kubernetes experimental reruns require the declared environments and original inputs; the public verifier does not rerun them.
- The 40-graph initial Kubernetes evaluation and 256-graph post-confirmatory extension are separate cohorts.
- No native TraDE/Diktyo trial, completed DeathStarBench run, or physical 60-GHz-radio validation is represented.

See [Data availability](../DATA_AVAILABILITY.md) and [Experiment–artifact map](../00_START_HERE/EXPERIMENT_ARTIFACT_MAP.md) for the exact boundary. File checksums establish integrity, **not** public-redistribution permission.
