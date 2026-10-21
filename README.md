# Conflict-Conditioned Microservice Placement Evaluation

**Raw evidence and third-party rights audit:** [RAW_DATA_AND_THIRD_PARTY_PROVENANCE.md](RAW_DATA_AND_THIRD_PARTY_PROVENANCE.md) documents the exact ten raw-study archive sizes and record counts, the limited content screening, the upstream GPL-2.0 simulator license, the external SNOB5G source, and the remaining public-release steps.


**Research artifact companion** for *Evaluating Conflict-Conditioned Ranking for Microservice Placement Under Shared Wireless Airtime* (Engineering Reports manuscript under consideration).

The study compares a conflict-conditioned complete-placement ranking policy (B5) with a calibrated utilization-only baseline (B3) over **identical state-dependent hard-admissible placements**. It examines pointwise degradation prediction, modeled ns-3 shared-airtime packet delivery, and request completion on a Kubernetes shared-medium emulator. The prespecified policy-level results do **not** establish that B5 improves mean executed performance.

## Reviewer navigation

| Directory | Contents |
| --- | --- |
| [`00_START_HERE/`](00_START_HERE/) | Reproduction guide, experiment-to-artifact map, data dictionary, and offline verifier |
| [`02_Methods_and_Configuration/`](02_Methods_and_Configuration/) | Locked methodology, model calibration records, experiment plans, reproducibility scope |
| [`03_Code/`](03_Code/) | Frozen confirmatory engine, test scripts, and separate Kubernetes extension |
| [`05_Results_and_Analysis/`](05_Results_and_Analysis/) | Original derived numerical results and audit tables |
| [`06_Environment_and_Execution/`](06_Environment_and_Execution/) | Execution-environment notes |

**Begin with:** [`00_START_HERE/EXPERIMENT_ARTIFACT_MAP.md`](00_START_HERE/EXPERIMENT_ARTIFACT_MAP.md) and [`00_START_HERE/REPRODUCTION_GUIDE.md`](00_START_HERE/REPRODUCTION_GUIDE.md).

## Fast, public, data-light verification

The public graph-level CSV tables are sufficient to independently recompute the primary **mean paired differences and the RQ2 selection/win-loss accounting**, without downloading the multi-gigabyte original packet logs.

```bash
python 00_START_HERE/verify_public_graph_results.py
```

This standard-library-only check covers 60 in-distribution and 60 shifted RQ1 graph identities, 200 RQ2 graph identities, the original 40-graph high-load Kubernetes panel, the separate 256-graph fresh panel, and the 128-graph matched-stabilizer contrast. It does **not** recompute bootstrap confidence intervals or establish simulator bit-level reproducibility; for those stronger claims, use the full evidence release and original protocols.

## Publication and verification scope

This is a **publicly deposited subset** of the original verified reviewer archive. The ten original raw-study ZIP archives are **not in this repository**, and the public repository alone cannot perform the archive's complete raw-data integrity verification or independently reconstruct every original simulation. A public-subset checksum list is provided in [`PUBLIC_FILE_SHA256SUMS.txt`](PUBLIC_FILE_SHA256SUMS.txt), covering only the files actually deposited here. The original offline archive separately passed complete release-file hashes, ten study-archive checks, and 108,727 archived raw-record hashes. Those offline results must not be mistaken for a verifier pass of this partial public checkout.

This repository does **not** distribute the external SNOB5G raw dataset. The frozen IMDEA Networks Institute / Hany Assasa C++ simulator file is **restored byte-for-byte** with the upstream WiGig GPL-2.0 license and explicit attribution in [`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md). The original SNOB5G dataset, ten large raw-study ZIPs, and selected oversized frozen plans/indexes are not yet included; consult [`DATA_ACCESS_AND_EXCLUSIONS.md`](DATA_ACCESS_AND_EXCLUSIONS.md) and [`PUBLIC_DEFERRED_FILE_INDEX.csv`](PUBLIC_DEFERRED_FILE_INDEX.csv). Consequently, running every simulator stage from this checkout alone is not yet certified. No blanket license is asserted for the full repository.

The manuscript and supplementary PDF are supplied to the journal separately; this repository hosts research artifacts, not the submission files. The historical B3 Stage-A `calibration_aggregated.csv` remains unrecovered and cannot be regenerated from the archived files. Original and post-confirmatory Kubernetes cohorts are separate. No external-scheduler superiority, physical concurrent 60-GHz experiment, or completed DeathStarBench run is claimed.

## Research result guide

- **RQ1:** B5 has higher mean absolute prediction error than B3 in both in-distribution and shifted-traffic panels (60 independent graph identities each).
- **RQ2:** On 200 conflict-dense graphs, the mean B5 minus B3 delivered-fraction contrast is approximately **−0.001980**; 140 placements change, with 81 favorable switches, 59 unfavorable switches and 60 unchanged outcomes.
- **RQ3:** The original 40-graph Kubernetes comparison was inconclusive. The *separately specified* post-confirmatory 256-graph panel showed a B5 minus B3 completion-fraction difference of approximately **−0.005679**.

Read the methods, data dictionary, and archived result tables for precise estimands, protocol limitations, and uncertainty measures.

**Status:** Study artifacts released for scientific inspection; original raw-study archive release and third-party redistribution permissions remain a separate access decision.
