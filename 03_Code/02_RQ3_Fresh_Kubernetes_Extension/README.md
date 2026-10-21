# Fresh Kubernetes RQ3 extension

This is the separately specified fresh-graph Kubernetes extension. Its `src/`, `config/`, `PRE_RUN_FREEZE/`, model locks, `benchmark/`, `simulator/`, and `stage_e_support/` retain the layout expected by the included code.

The archived accepted records are stored in `04_Raw_Experimental_Data/10_Fresh_Kubernetes_RQ3.zip`. To restore the raw directory expected by analysis/rerun tools, run from the package root:

```bash
python 00_START_HERE/unpack_raw_data.py --study 10_Fresh_Kubernetes_RQ3
```

The corresponding derived summaries are under `05_Results_and_Analysis/08_Fresh_Kubernetes_RQ3/`. For an intentional rerun, first configure the Kubernetes cluster and dependencies, then follow the included protocol and use `bash RUN_RQ3_COMPLETE.sh`. This command launches/resumes a resource-intensive experiment; it is not needed to verify archived results. No execution logs are included in this reviewer release.
