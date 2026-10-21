# Development-selection evidence bundle

This is a reviewer-facing evidence bundle for the retrospective B5 development-selection disclosures in the manuscript. It contains existing source records and read-only audit outputs; it is not a new experiment, a new model fit, or a confirmatory result.

## Corrected development-gate reconstruction

`audit_development_gate.py` reconstructs the aligned B3/B4 state-specific development comparisons from the four supplied B4 CSVs and the frozen RQ3 science ZIP in `inputs/`. It verifies the embedded B3 coefficient payload and the four B4 input hashes against the frozen model lock. It does not fit a model, run ns-3, or launch Kubernetes.

From this directory, the read-only reconstruction can be rerun with:

```bash
python audit_development_gate.py --inputs-dir inputs --out-dir outputs_rebuilt
```

The retained outputs report 2,128 rows across 360 graph-state groups. Corrected state-specific MAE is 0.0377003485 for B3 and 0.0430836335 for B4; archived B5 out-of-fold MAE is 0.0359344201. At the frozen B5 near-margin, matched regret is 0.0018998547 for B3 and 0.0011250597 for B5. The B5 value is a selected out-of-fold quantity, not nested independent validation. These development results do not override held-out RQ1 or confirmatory RQ2/RQ3 outcomes.

## Existing CV-grid, margin, fold, and pair-weight audit outputs

`outputs/h1b/` preserves the existing 19 October read-only source-audit tables and summary. The summary records that 54,337 of 55,722 non-tied pairs came from ten dense N=8 oracle groups and that these groups contributed 99.4374% of the pairwise subobjective's pre-loss weight mass—not 99.4374% of the total fitting objective. The CV-grid and margin tables preserve the audited selection support; the fold table records how dense-oracle groups were distributed across the grouped folds.

The original large source wrapper archives used for that separate H1B audit are not included in this reviewer release. The H1B tables are therefore retained source-audit outputs with source hashes recorded in `outputs/h1b/SOURCE_INPUTS.md`; they are not presented as a full rerun of that separate audit from this release alone. Their included-file hashes can be checked from `outputs/h1b/` with:

```bash
sha256sum -c H1B_OUTPUT_SHA256SUMS_20261019.txt
```

## Integrity

The release-level `SHA256SUMS.txt` covers every file in this bundle. Raw experimental records and primary RQ1/RQ2/RQ3 point estimates remain in the ten curated study archives and are checked by `00_START_HERE/verify_release.py`.
