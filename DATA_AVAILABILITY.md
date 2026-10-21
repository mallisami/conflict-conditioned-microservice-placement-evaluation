# Data availability and reproducibility scope

This page is the single public reference for **what a reviewer can reproduce from GitHub today**. It consolidates prior overlapping data-access and provenance notes. The experiment source and frozen model files retain their original, traceable paths.

## What is available

- Source implementation for the original confirmatory study and separate fresh Kubernetes extension, including the [adapted WiGig/ns-3 source](03_Code/01_Confirmatory_Engine/simulator/evaluate_shared_airtime_boundary.cc).
- Governing protocols, frozen parameter/model locks, selected configuration and experiment-plan inputs.
- Derived graph-level RQ1 and RQ2 results, initial Kubernetes result tables, and the separate fresh-RQ3 extension result tables.
- Public verification: point estimates (`00_START_HERE/verify_public_graph_results.py`), independently seeded paired graph bootstrap confidence intervals (`00_START_HERE/recompute_public_bootstrap_cis.py`), original frozen plan SHA-256 verification (`00_START_HERE/verify_frozen_plan_archives.py`), and all public-file SHA-256 checks (`verify_public_subset.py`).
- [Source-to-evidence crosswalk](00_START_HERE/EXPERIMENT_ARTIFACT_MAP.md), [public file checksum manifest](PUBLIC_FILE_SHA256SUMS.txt), [environment notes](06_Environment_and_Execution/ENVIRONMENT_NOTES.md).

**These commands do not require large packet logs**. They check recorded results, recompute selected primary graph-bootstrap intervals with a disclosed seed, and verify public-file integrity. They do not rerun simulation, refit historical models, reconstruct every secondary interval or reproduce the archived historical bootstrap random draws.

## Original raw-study archives not on GitHub

The complete offline evidence release contains the following ten ZIP archives. The listed sizes and record counts come from the archived inventory; **none is currently downloadable from this GitHub repository**.

| Study | Original ZIP | Approximate ZIP size | Record count |
| --- | --- | ---: | ---: |
| Prediction panels | `01_RQ1_Prediction_Panel.zip` | 27.24 MiB | 17,280 |
| RQ2 selected graphs | `02_RQ2_Selection_Graphs.zip` | 14.14 MiB | 200 |
| Telemetry robustness | `03_Telemetry_Robustness.zip` | 0.65 MiB | 1 |
| Packet execution | `04_RQ2_Packet_Execution.zip` | 4,067.61 MiB | 53,985 |
| Structured topologies | `05_Structured_Topologies.zip` | 7.07 MiB | 1,988 |
| Exhaustive oracle | `06_Oracle_Execution.zip` | 4,831.51 MiB | 24,651 |
| Measured-rate replay | `07_Measured_Rate_State_Replay.zip` | 12.67 MiB | 8,304 |
| Load pilot | `08_StageE_Load_Pilot.zip` | 0.07 MiB | 45 |
| Original Kubernetes panel | `09_Initial_Kubernetes_Experiment.zip` | 95.66 MiB | 1,120 |
| Fresh Kubernetes panel | `10_Fresh_Kubernetes_RQ3.zip` | 120.47 MiB | 1,153 |

Total: **108,727 records** in approximately **8.96 GiB of study ZIPs**. Offline SHA-256 integrity verification of the original release, study archives and internal record indexes previously passed. This does not mean those archive contents are publicly deposited, independently rerun, or cleared for public redistribution.

## Technical and historical reproducibility boundaries

- The original Stage-A B3 calibration input `calibration_aggregated.csv` was **not recovered**. Frozen coefficients and downstream audit evidence are retained, but re-estimating historical baseline parameters from the missing source is not certified.
- This GitHub checkout does not include the original ten raw ZIPs, the complete per-file raw index, or the complete release manifest. The full offline verifier `00_START_HERE/verify_release.py` requires these assets and **is not intended for this checkout**.
- The two previously omitted original plan payloads are now deposited as losslessly compressed [oracle ZIP](02_Methods_and_Configuration/02_Experiment_Plans/Oracle_Execution/ORACLE_PLAN.json.zip) and [Stage-D ZIP](02_Methods_and_Configuration/02_Experiment_Plans/RQ2_Packet_Execution/STAGE_D_PLAN.json.zip). The original JSON bytes, paths and SHA-256 hashes are verified by `00_START_HERE/verify_frozen_plan_archives.py`. The RQ1, replay, and structured-topology plans were already present; see the [remaining outstanding-file index](PUBLIC_DEFERRED_FILE_INDEX.csv).
- The dataset-sensitive measured-rate replay uses frozen vectors derived from external [SNOB5GData](https://github.com/nap-it/SNOB5GData). The complete upstream measurement dataset is **not** redistributed. A path-sanitized derived vector companion is included in this repository; the original source metadata remains in the offline evidence.
- The original 40-graph Kubernetes study and fresh 256-graph post-confirmatory study are **separate** and must not be pooled.
- No native TraDE/Diktyo scheduler performance trials, completed DeathStarBench execution, or concurrent physical 60-GHz radio validation are claimed.

## Third-party code and redistribution

The exact frozen study file `03_Code/01_Confirmatory_Engine/simulator/evaluate_shared_airtime_boundary.cc` **is on GitHub** (it was incorrectly described as withheld in an older provenance note). The header attributes **IMDEA Networks Institute (2015–2020)** and **Hany Assasa**. It derives from the [WiGig/ns-3 module](https://github.com/wigig-tools/wigig-module/tree/v0.5), licensed under **GPL-2.0**. The [GPL license text](THIRD_PARTY_LICENSES/WIGIG_GPL-2.0.txt) and [third-party notice](THIRD_PARTY_NOTICES.md) are retained. The detailed historical modification lineage and all combined-code obligations have not been independently certified.

The [SNOB5GData](https://github.com/nap-it/SNOB5GData) repository did not expose a general redistribution license in the previous source-rights check; the full dataset is linked rather than mirrored here.

The former raw-record security screen checked all 27,939 JSON/TXT entries and only the initial 8,192 bytes of each of 80,808 CSV records (approximately 416 MB examined). No targeted credential/email/private-IP/path patterns were detected within those inspected portions. That is **not a comprehensive privacy, authorship or rights clearance**. Do not publish the full raw-study ZIPs solely on the basis of the partial screen. Author and coauthor permissions for first-party experimental outputs still require confirmation.

## Reviewer access and integrity

1. Public point-estimate checks: `python3 00_START_HERE/verify_public_graph_results.py`.
2. Public published-file SHA-256 check: `python3 verify_public_subset.py`.
3. Full offline release integrity: requires obtaining all original study archives, frozen release manifest and supporting indexes **by a separate permission-cleared distribution route**; no public raw download URL or repository DOI is claimed.
4. Full simulator or Kubernetes reruns: require separately documented runtime dependencies and configurations, and may be resource intensive.

The journal manuscript, supplement, editable LaTeX and figures are supplied **separately**, not committed here. No unassigned publication DOI or data-archive link is asserted.
