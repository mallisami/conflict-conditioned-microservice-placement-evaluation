# Conflict-Conditioned Microservice Placement Evaluation

**Reproducibility companion** to *Evaluating Conflict-Conditioned Ranking for Microservice Placement Under Shared Wireless Airtime* (research manuscript; no publication DOI assigned).

This repository contains the frozen implementation, methods, selected experiment plans and graph-level outcome tables for a controlled comparison of **B5 (conflict-conditioned ranking)** versus **B3 (utilization-only ranking)** on the **same state-dependent hard-admissible placement set**. Outcomes are assessed separately for prediction, packet-level delivery, and Kubernetes shared-medium application completion. **The evidence does not establish improved mean executed performance for B5.**

## Start here — three reviewer checks

1. **Recalculate the public primary results** without installing ns-3 or Kubernetes:

   ```bash
   git clone https://github.com/mallisami/conflict-conditioned-microservice-placement-evaluation.git
   cd conflict-conditioned-microservice-placement-evaluation
   python3 00_START_HERE/verify_public_graph_results.py
   ```

2. **Check the published-file integrity manifest** (separate from the full offline-archive verifier):

   ```bash
   python3 verify_public_subset.py
   ```

3. **Trace each outcome to its protocol and evidence** using the [experiment–artifact map](00_START_HERE/EXPERIMENT_ARTIFACT_MAP.md), [reproduction guide](00_START_HERE/REPRODUCTION_GUIDE.md), and [data dictionary](00_START_HERE/DATA_DICTIONARY.md).

These quick checks recompute retained **point estimates and accounting identities** and compare deposited files with their checksums. They do not rerun the original experiments or validate the ten unpublished original raw-data archives. The separate independent bootstrap check recomputes selected primary intervals, not all historical secondary intervals.

## Full original raw-data backup (not this GitHub ZIP)

The **separate** author-controlled full reviewer backup is **417,004,855 bytes (398 MiB compressed)**, containing ten original raw-study ZIP archives with 108,727 indexed records, plus the updated manuscript, code, frozen experiments and results. GitHub does **not** host that full archive.

For the exact SHA-256, checksums of all ten original study archives, verification instructions and current access restrictions, see [full reviewer evidence guide](00_START_HERE/REVIEWER_FULL_EVIDENCE.md). The full archive has not been cleared for public distribution or approved for a particular confidential journal transfer route.

## Recovered frozen execution plans and bootstrap verification

- [Oracle plan ZIP](02_Methods_and_Configuration/02_Experiment_Plans/Oracle_Execution/ORACLE_PLAN.json.zip) — original 4,445,441-byte JSON restored under its original path.
- [Stage-D packet plan ZIP](02_Methods_and_Configuration/02_Experiment_Plans/RQ2_Packet_Execution/STAGE_D_PLAN.json.zip) — original 6,209,838-byte JSON restored under its original path.
- Recalculate the secondary RQ2 B5-versus-comparator effects, three-state weighted effect, and graph-size strata with `python3 00_START_HERE/verify_public_supporting_results.py`.
- Verify both containers and original JSON hashes with `python3 00_START_HERE/verify_frozen_plan_archives.py`.
- Recalculate selected primary graph-level paired percentile-bootstrap confidence intervals using `python3 00_START_HERE/recompute_public_bootstrap_cis.py --resamples 100000`.

These are losslessly compressed *input plans*, not packet/oracle execution outcomes. ZIPs can be extracted at repository root using `python3 -m zipfile -e ZIPFILE .`. Independent bootstrap results use a published RNG seed; they do not claim identical historical random draws or reconstruct all secondary intervals.

## Study results and direct evidence paths

| Research question | What the public tables support | Open evidence |
| --- | --- | --- |
| **RQ1 — prediction** | Mean absolute error is higher for B5 in both in-distribution and shifted-traffic panels (60 graphs each) | [Prediction tables](05_Results_and_Analysis/01_RQ1_Prediction/) |
| **RQ2 — packet delivery** | B5 minus B3 mean delivered fraction ≈ **−0.001980** on 200 graphs. Of 140 changed placements, 81 improve and 59 worsen; 60 outcomes are unchanged | [Selection and packet delivery](05_Results_and_Analysis/02_RQ2_Selection_and_Packet_Execution/) |
| **RQ3 — application completion** | Original 40-graph Kubernetes comparison is inconclusive. Separate post-confirmatory 256-graph extension has B5 minus B3 mean completion ≈ **−0.005679** | [Original Kubernetes panel](05_Results_and_Analysis/07_Initial_Kubernetes_Experiment/) · [Fresh extension](05_Results_and_Analysis/08_Fresh_Kubernetes_RQ3/) |
| **Supporting analyses** | Robustness, structured topologies, exhaustive-oracle attribution, measured-rate replay and development-stage audits | [All analysis folders](05_Results_and_Analysis/) |

Graph identity is the independent analysis unit; original and post-confirmatory cohorts must not be pooled.

## Current development-gate disposition (24 October 2026)

The frozen B5 model lock retains its historical `development_gate.passed=true` field. **Do not interpret that field as current scientific sign-off.** Its selection criterion compares B5 near-margin regret with B4 strict-selection regret, which are different decision rules. The corrected retrospective audit reports B5 strict regret of 0.0018021 versus B4 strict regret of 0.0011209; the near-margin comparison points in the opposite direction, but was not nested independent validation. Ten dense N=8 oracle groups contribute approximately 99.44% of the pairwise subobjective's pre-loss weight mass, and the development builder did not define an explicit held-out traffic-family split.

The historical lock is preserved unchanged. The current interpretation and remaining blockers are recorded in [the development-gate disposition](00_START_HERE/DEVELOPMENT_GATE_DISPOSITION_2026-10-24.md). Run `python3 00_START_HERE/audit_development_gate_disposition.py` to check the documented values and detect whether the missing historical B3 calibration file has appeared. This is an audit guard, not a scientific validation or a substitute for the full evidence package.


## Repository directory guide

The numeric prefixes are **frozen artifact-directory names from the verified experiment package**, not public release version numbers. They are kept to preserve executable paths, provenance and references.

| Directory | Purpose |
| --- | --- |
| [`00_START_HERE/`](00_START_HERE/) | Reviewer navigation, study index, reproducibility guides and verification scripts |
| [`02_Methods_and_Configuration/`](02_Methods_and_Configuration/) | Prespecified protocols, frozen coefficients, configurations, and selected plans |
| [`03_Code/`](03_Code/) | Confirmatory research engine, WiGig/ns-3 source, tests, Kubernetes extension |
| [`05_Results_and_Analysis/`](05_Results_and_Analysis/) | Public-derived graph-level outcomes and supporting diagnostic tables |
| [`06_Environment_and_Execution/`](06_Environment_and_Execution/) | Execution-environment prerequisites |

`01_Manuscript/` is intentionally excluded (submission materials are handled by the journal). `04_Raw_Experimental_Data/` is absent from this public checkout because the ten original study ZIPs have not yet been released. These gaps are **not missing experimental observations in the offline verified archive**.

## Evidence availability and licensing

See **[Data availability and reproducibility limits](DATA_AVAILABILITY.md)** for the exact included/excluded file classes, the ten-study raw archive inventory, the missing historical B3 calibration input, and the difference between lightweight result verification and a full simulator rerun. The [outstanding-file index](PUBLIC_DEFERRED_FILE_INDEX.csv) lists **only files actually absent** as of the public audit.

The adapted WiGig C++ simulator file [`evaluate_shared_airtime_boundary.cc`](03_Code/01_Confirmatory_Engine/simulator/evaluate_shared_airtime_boundary.cc) **is present**, with attribution and upstream GPL-2.0 license in [third-party notices](THIRD_PARTY_NOTICES.md). The upstream SNOB5G dataset is not redistributed. No blanket license is asserted for the entire repository.

**Citing this artifact:** Link to this repository alongside the manuscript's Data and Code Availability statement, describing it as a *public code, configuration, and derived-results deposit*, not a complete raw-data deposit. The manuscript and Supplementary Material are provided separately.
