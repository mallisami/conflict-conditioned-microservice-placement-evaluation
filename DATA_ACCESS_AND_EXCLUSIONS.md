# Data availability, license boundaries and repository exclusions

The complete frozen reviewer archive was verified offline and is not equivalent to this repository's partial, rights-screened public deposit. This document records the **actual** exclusions instead of suggesting every input is publicly downloadable.

1. **Raw experimental results:** Ten original study-level ZIP archives are retained separately. The corresponding public release has not yet been approved for redistribution. Their inner 108,727 record checks passed offline; they are not included here.
2. **External/third-party simulator source:** `03_Code/01_Confirmatory_Engine/simulator/evaluate_shared_airtime_boundary.cc` includes a copyright notice naming IMDEA Networks Institute / Hany Assasa. It is withheld until the exact upstream license and redistribution conditions are confirmed. This creates a real limitation on independently rebuilding the full simulator workflow from this checkout.
3. **External measured-rate data:** The full SNOB5G upstream source is not included. A local-path-containing derived replay vector metadata file is omitted pending public-path sanitization and source-rights review; derived aggregate results have their stated experimental scope.
4. **Large frozen plans and indexes:** Selected large payloads are not included in this initial public commit due to transfer limitations. The source bundle and offline verified archive retain them unchanged. See `PUBLIC_DEFERRED_FILE_INDEX.csv` for the exact paths and byte sizes.
5. **Missing historical input:** Original Stage-A B3 `calibration_aggregated.csv` was not recovered. Original parameter fitting cannot be rerun using that missing dataset, though model coefficients and documented downstream analyses are available in the retained provenance.
6. **Manuscript:** Submission PDFs and editable LaTeX are delivered to the journal, not stored in this public reproducibility repository.

The original archive's `verify_release.py` requires the complete 537-file release and all study archives and is not a standalone verifier for this subset. Use `verify_public_subset.py` with `PUBLIC_FILE_SHA256SUMS.txt` for the files actually published. The public subset's internal source paths and model locks are deliberately unchanged.

No release DOI, permanent dataset citation, or journal-approved restricted-data transfer mechanism is asserted until confirmed.
