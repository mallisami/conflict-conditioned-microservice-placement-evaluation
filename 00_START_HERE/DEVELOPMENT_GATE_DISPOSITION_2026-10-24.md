# B5 development-gate disposition and repair plan

**Disposition date:** 24 October 2026  
**Current status:** **BLOCKED — historical evidence is preserved; scientific sign-off is not established.**  
**Scope:** public GitHub checkout at the 24 October 2026 audit. This is a retrospective audit, not a new experiment or a model refit.

## Why the old “passed” flag is not current sign-off

The frozen file `02_Methods_and_Configuration/03_Model_Locks/B5_MODEL_LOCK.json` records `development_gate.passed=true`. That field is retained as a historical record and is not overwritten. Its recorded selection criterion compares B5's selected out-of-fold (OOF) near-margin regret with B4's strict-selection regret. Those are different selection rules, so the comparison is not a matched-policy gate.

The corrected retrospective audit in `05_Results_and_Analysis/09_Development_Selection_Audit/outputs/h1b/H1B_SUMMARY_20261019.json` reports:

| Development quantity | B4 | B5 | B5 minus B4 | Interpretation |
|---|---:|---:|---:|---|
| Strict-selection regret | 0.0011208595 | 0.0018020986 | +0.0006812391 | B5 is worse under the strict rule in this retrospective OOF summary |
| Near-margin regret | 0.0012872232 | 0.0011250597 | −0.0001621636 | B5 is lower under the near-margin rule in this retrospective OOF summary |
| Legacy mixed-rule comparison | B4 strict: 0.0011208595 | B5 near: 0.0011250597 | +0.0000042002 | Not a valid matched-policy comparison |

These are archived development-selection quantities, not confirmatory estimates. The direction changes with the selection rule. The old lock's original B4 strict threshold (0.0011698364) differs from the corrected retrospective B4 strict value (0.0011208595); the corrected audit must be used to assess the discrepancy, not to silently rewrite the frozen lock.

## Additional reasons the development result is not independently validated

- The retained H1B audit records `nested_cv_performed=false`. Hyperparameter and margin selection therefore do not have a nested, independent evaluation in that audit.
- The development builder records `explicit_OOD_traffic_family_split_in_development_builder=false`; this is not a demonstrated held-out traffic-family generalization test.
- Ten dense N=8 exhaustive-oracle groups contributed 55,722 non-tied pairs, and the audit reports that they contributed 99.4374% of the pairwise subobjective's pre-loss weight mass. This makes the development objective highly concentrated in that support regime.
- The original Stage-A `calibration_aggregated.csv` is absent from the public checkout. The frozen B3 coefficient payload and derived audit outputs are not a substitute for the missing calibration rows. Historical B3 cannot be independently refitted from this public checkout.
- The ten original raw-study ZIPs and some source-wrapper archives remain outside public GitHub. Their published hashes identify expected files but do not make those files available or establish permission to redistribute them.

## What has been corrected in the public repository now

1. The current interpretation is explicitly separated from the frozen historical lock; the lock and historical outcomes remain unchanged.
2. A read-only audit guard, `00_START_HERE/audit_development_gate_disposition.py`, checks the critical recorded numbers, detects the mixed-rule discrepancy, and reports whether the missing calibration filename appears in the checkout. Its successful exit means only that the disclosed audit state is internally consistent.
3. CI is extended to run the public integrity and result checks, the gate-disposition guard, and the offline/synthetic pytest suites for both the confirmatory engine and fresh Kubernetes extension under pinned Python dependencies and a hard process timeout.
4. The public checksum manifest is refreshed for the updated files.

**A green CI run is not evidence that the scientific development gate passed.** It only shows that the checks and offline software tests in that workflow completed.

## What must wait for the complete reproducibility package

When the full package is supplied, the next audit must:

1. Verify the package and original source archives against their existing SHA-256 records before extracting or changing anything.
2. Locate and authenticate the original B3 Stage-A calibration CSV, its generation procedure, and its exact schema; independently refit B3 and compare the reconstructed coefficients and predictions with the frozen payload.
3. Recover the full development source wrappers and the original CV/selection scripts. Re-run the source audit from those inputs rather than treating retained H1B tables as a complete rerun.
4. Define a grouped/nested development evaluation that keeps graph identities and relevant traffic families separated across folds; explicitly prevent dense-oracle groups from dominating the reported evidence without a justified, predeclared weighting rationale.
5. Compare strict with strict and near-margin with near-margin on identical eligible graph-state groups. Predeclare the primary selection rule, the gate metric, the tolerance, and the failure decision before fitting or looking at new outcomes.
6. Refit and freeze a new candidate only if that protocol is justified and passes its gate. Preserve B5 v1.0 and all historical outcomes as development history; do not relabel them as confirmatory evidence.
7. Only after this gate and the broader source/rights audit, decide whether new experiments are necessary. Do not launch ns-3 or Kubernetes campaigns as a substitute for resolving the development-selection validity problem.

## Automated disclosure check

From the repository root:

```bash
python3 00_START_HERE/audit_development_gate_disposition.py
```

The script is deliberately read-only. It does not refit B3/B5, run ns-3 or Kubernetes, recreate raw traces, or close any scientific blocker.
