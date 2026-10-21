# Confirmatory experiment engine

This directory preserves the source layout for the original Paper 2 experiment engine: `src/`, `config/`, `deps/`, `stage_e_support/`, `benchmark/`, `simulator/`, `b5_lock/`, `development_reference/`, and the VM execution helpers.

The individual runners correspond to the reported prediction, placement, packet-execution, structured-topology, oracle, measured-rate replay, and initial Kubernetes studies. The all-stage campaign launcher and code for gated, unperformed DeathStarBench/physical-radio stages are intentionally excluded. Derived outcomes are under `05_Results_and_Analysis/`; accepted raw data are preserved byte-for-byte in the per-study ZIP archives under `04_Raw_Experimental_Data/`. Extract the needed study using `python 00_START_HERE/unpack_raw_data.py --study <STUDY_NAME>` before a tool that expects a restored raw-data directory.

The four B4 development input tables are present here and in `02_Methods_and_Configuration/04_Model_Development_Inputs/` because the fitting script expects the `development_reference/` path. They are development-only inputs used to freeze B5, not confirmatory outcomes. `deps/mape_cap_bplus/` is the model/scheduler dependency used by this engine.
