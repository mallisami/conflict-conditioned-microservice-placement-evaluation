# Conflict-Conditioned Microservice Placement Evaluation

Reproducibility artifacts accompanying **Evaluating Conflict-Conditioned Ranking for Microservice Placement Under Shared Wireless Airtime** (*Engineering Reports* submission candidate, v1.7).

The study compares a conflict-conditioned ranking policy (B5) with a calibrated utilization-only placement policy (B3), holding their state-dependent hard-admissible candidate sets identical. Its distinct outcomes include predictor error, modeled ns-3 packet delivery, and request completion in a Kubernetes shared-medium emulator. **The primary evidence does not establish a mean-execution benefit of B5 over B3.**

## Publication status

**The full reviewer release has not yet been deposited in this public repository.** The verified offline v1.7 release contains ten original raw-study archives, locked configurations, experiment plans, source code, graph-level results, artifact indexes, and SHA-256 verification scripts. Publishing code and selected derived results alone must not be represented as a complete independent reproduction.

The external-data provenance, redistributable third-party materials, and raw-record privacy and permission boundaries require review before public transfer. No blanket open-source license is asserted for unreviewed material.

## Verified offline reviewer-release layout

The offline archive has this established structure (the journal manuscript is supplied separately):

- `00_START_HERE/`: reviewer guide, artifact crosswalk, data dictionary, source indexes, verification and unpacking scripts
- `02_Methods_and_Configuration/`: protocol locks, development configuration, experiment plans
- `03_Code/`: confirmatory engine and fresh Kubernetes extension
- `04_Raw_Experimental_Data/`: ten per-study raw data archives
- `05_Results_and_Analysis/`: graph-level derived results and analysis records
- `06_Environment_and_Execution/`: software and runtime environment notes

The full archived release has passed offline file hashes of 537 manifest-covered files, all ten raw archives and 108,727 internal raw-data records, plus selected point-estimate consistency checks. Those checks do not independently rerun simulations, refit the missing original calibration dataset, or recompute every confidence interval.

## Scientific boundaries

- The original Stage-A B3 `calibration_aggregated.csv` was not recovered. Frozen baseline coefficients are retained, but the historical calibration cannot be reproduced from that missing source file.
- The original 40-graph Kubernetes study is separate from the 256-graph post-confirmatory study.
- No native TraDE/Diktyo scheduler trials, completed DeathStarBench validation, or physical concurrent 60-GHz radio validation are claimed.
- The complete external SNOB5G dataset is not bundled.

## Reproduction

This README will be updated with direct file paths and commands when the deposited material is complete and independently checked. The offline `00_START_HERE/verify_release.py` expects the entire archived release and does not pass on a subset missing the original data archives.
