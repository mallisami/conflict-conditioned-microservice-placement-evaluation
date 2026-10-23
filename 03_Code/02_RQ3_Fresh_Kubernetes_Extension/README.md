# Fresh Kubernetes RQ3 extension

This is the separately specified fresh-graph Kubernetes extension. Its `src/`, `config/`, `PRE_RUN_FREEZE/`, model locks, `benchmark/`, `simulator/`, and `stage_e_support/` retain the layout expected by the included code.

The `simulator/evaluate_shared_airtime_boundary.cc` file is now included as a byte-for-byte mirror of the canonical source in `../01_Confirmatory_Engine/simulator/`. The Stage-A self-test and run provenance expect that local path. The mirror is not a new simulator implementation; its SHA-256 must remain `d8f262c864448cc6a9910d121d3cb9a46074c0d6264b5ce4c5a397d268b8913a`.


The archived accepted records are stored in `04_Raw_Experimental_Data/10_Fresh_Kubernetes_RQ3.zip`. To restore the raw directory expected by analysis/rerun tools, run from the package root:

```bash
python 00_START_HERE/unpack_raw_data.py --study 10_Fresh_Kubernetes_RQ3
```

The corresponding derived summaries are under `05_Results_and_Analysis/08_Fresh_Kubernetes_RQ3/`. For an intentional rerun, first configure the Kubernetes cluster and dependencies, then follow the included protocol and use `bash RUN_RQ3_COMPLETE.sh`. This command launches/resumes a resource-intensive experiment; it is not needed to verify archived results. No execution logs are included in this reviewer release.
