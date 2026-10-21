# Audit of public raw-data release and external code provenance

**Scope:** The public repository versus the existing independently verified offline reviewer release. The manuscript is handled separately, and internal working-version numbers are not a publication identifier.

## What is actually public

The repository contains source/configuration files and derived research results, with a separate public-subset SHA-256 manifest. It does **not** yet contain the ten original raw-study ZIPs or the 30,330-byte adapted WiGig simulator source `03_Code/01_Confirmatory_Engine/simulator/evaluate_shared_airtime_boundary.cc`. A full-archive verifier cannot pass against this incomplete public checkout.

## Original raw-study ZIPs: verified inventory

| Study archive | ZIP size | Raw research records |
| --- | ---: | ---: |
| `01_RQ1_Prediction_Panel.zip` | 27.24 MiB | 17,280 |
| `02_RQ2_Selection_Graphs.zip` | 14.14 MiB | 200 |
| `03_Telemetry_Robustness.zip` | 0.65 MiB | 1 |
| `04_RQ2_Packet_Execution.zip` | 4,067.61 MiB | 53,985 |
| `05_Structured_Topologies.zip` | 7.07 MiB | 1,988 |
| `06_Oracle_Execution.zip` | 4,831.51 MiB | 24,651 |
| `07_Measured_Rate_State_Replay.zip` | 12.67 MiB | 8,304 |
| `08_StageE_Load_Pilot.zip` | 0.07 MiB | 45 |
| `09_Initial_Kubernetes_Experiment.zip` | 95.66 MiB | 1,120 |
| `10_Fresh_Kubernetes_RQ3.zip` | 120.47 MiB | 1,153 |

**Total:** 10 ZIP containers, 108,727 original records, approximately 8.96 GiB of ZIP files. The frozen offline archive previously passed all per-container and per-record SHA-256 validations. These are retained experimental-output files, not a bundled copy of the full SNOB5G upstream dataset.

**Security/privacy screening performed:** Every one of 27,939 JSON/TXT records was searched throughout for patterns indicating credentials, email addresses, private IPv4 addresses and local execution paths; the first 8,192 bytes of each of 80,808 CSV records were also searched. In total approximately 416,003,002 bytes were inspected with **no targeted pattern matches**. This screening is not an exhaustive inspection of the multi-gigabyte CSV contents; an additional all-byte scan was attempted but did not finish in the available execution window. It also cannot establish contributor ownership or a complete absence of sensitive or copyrighted material. Do not describe these ZIPs as permission-cleared for public distribution on this evidence alone.

## Adapted WiGig ns-3 example: specific license established

- Withheld study file: `03_Code/01_Confirmatory_Engine/simulator/evaluate_shared_airtime_boundary.cc`.
- Header identifies **IMDEA Networks Institute** (2015–2020), **Hany Assasa**. Its descriptive comments and implementation basis correspond to upstream `scratch/evaluate_qd_dense_scenario_single_ap.cc`.
- Upstream **tag `v0.5`**: [WiGig simulator](https://github.com/wigig-tools/wigig-module/tree/v0.5), [original example](https://github.com/wigig-tools/wigig-module/blob/v0.5/scratch/evaluate_qd_dense_scenario_single_ap.cc), [GPL-2.0 license](https://github.com/wigig-tools/wigig-module/blob/v0.5/LICENSE). The frozen Dockerfile pins commit `f3404236d05eb1da1cab80eec06c56ea8ab43f7d`.
- **Disposition:** The upstream is GPL-2.0 licensed, rather than unlicensed or automatically prohibited from redistribution. Publishing the modified source requires appropriate copyright and modification notices, license text, and compliance with the applicable GPL obligations. A complete compatibility/attribution review of combined code has not been certified. Do not erase the original copyright or apply a blanket unrelated license to the modified upstream file.

## SNOB5G inputs: link to upstream, do not rehost original CSV

The external data source is [nap-it/SNOB5GData](https://github.com/nap-it/SNOB5GData). The upstream GitHub repository does not declare a license in its repository metadata and does not contain a root LICENSE file in the reviewed listing. Its public availability therefore should **not** be equated with a blanket redistribution license.

The study's `EXTERNAL_RATE_VECTORS.json` is a locally generated quantile/multiplier record derived from that source, not the full upstream dataset. Its original metadata includes an absolute local execution path. For an independently published version, create a clearly identified public companion with the path removed or parameterized **without silently replacing the original frozen artifact or its checksum**. Retain the pinned upstream dataset hash and access instructions.

## Public release plan and conditions

1. **Confirm author/coauthor rights** to publish the first-party raw measurements and code; this has not yet been documented.
2. **Complete security screening**, particularly the unsampled portions of the large CSV traces. Avoid claiming the privacy check has passed exhaustively.
3. **Resolve the GPL-2.0 attribution and modification notices** for the adapted simulator example; publish the unmodified original or link upstream only when technically sufficient for the frozen workflow, otherwise distribute the modified source with compliant notices and source terms.
4. **Publish the original ten ZIP files unchanged** in a stable artifact hosting system with working public download links and SHA-256 checksums. The large 4.3 GB and 5.1 GB ZIP files and the 126 MB fresh-RQ3 ZIP do not fit ordinary GitHub Git blobs; use appropriately split release assets or a citable dataset archive such as Zenodo instead of forcing large data into Git history.
5. Update the repository to give exact retrieval, reassembly, checksum, and `verify_release.py` commands for the **complete** reviewer evidence, and run a verification against those publicly fetched files before claiming end-to-end reproducibility.
6. Keep the original Stage-A `calibration_aggregated.csv` limitation visible; no release will regenerate this unavailable historical dataset.

**Current disposition:** Public source/derived-results deposit exists. The raw archive has passed scientific file-integrity checks, but public distribution and the complete online reproduction gate remain open. The adapted simulator source has an identified GPL-2.0 upstream license, subject to appropriate compliance rather than automatic exclusion.
