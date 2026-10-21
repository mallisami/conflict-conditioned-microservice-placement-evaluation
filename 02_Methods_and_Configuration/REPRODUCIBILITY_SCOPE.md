# Reproducibility scope

## Included

The raw evidence is organized into ten curated per-study ZIP archives rather than preserving the original Stage A--D and Stage E wrapper archives byte-for-byte. The supplement provides a display-level derivation table; `EXPERIMENT_ARTIFACT_MAP.md` and the searchable indexes map study evidence to actual paths. No separate `RESULT_SOURCE_CROSSWALK.csv`, `DISPLAY_DERIVATION_LEDGER.csv`, or `verify_key_claims.py` is included.

- Current clean main manuscript, supplement, editable LaTeX source, and figure assets.
- Governing confirmatory and fresh-RQ3 protocols, frozen model/coefficient locks, relevant plans/configurations, and B4 model-development inputs.
- Source code, dependencies, tests, and run instructions for the reported studies.
- Accepted per-run CSV/JSON records and derived results for RQ1 prediction, RQ2 selection and packet execution, telemetry robustness, structured topologies, oracle execution, measured-rate-state replay, the initial Kubernetes study, and the fresh Kubernetes RQ3 extension.
- An offline verifier for package integrity and selected reported point estimates.

## Limits of reproduction

- The historical Stage-A aggregated calibration input `calibration_aggregated.csv`, identified by the frozen B3 fit record, was not present in the available source archives. Frozen B3 coefficients and the fit record are included, but this package cannot independently refit the historical B3 coefficients from that missing CSV.
- No native TraDE or Diktyo performance trials were run; no such results are included or implied.
- Real DeathStarBench execution and concurrent physical 60-GHz radio validation were not completed and are not represented as results.
- The measured-rate replay includes frozen rate vectors, the replay plan, and accepted records, but not a separate copy of the entire upstream SNOB5G dataset.
- Full simulator and Kubernetes reruns require their documented runtime environments and may be resource-intensive. Offline verification does not launch them.
- SHA-256 and CRC checks establish file integrity, not redistribution rights. Public release requires separate data/code license, privacy, and consent clearance.
