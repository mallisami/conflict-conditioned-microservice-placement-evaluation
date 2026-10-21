# B5 VM execution helpers

Start with `../VM_3NODE_EXECUTION_GUIDE.md`.

- `01_INSTALL_COMMON.sh` — creates `.venv-b5`, preserves existing Docker, and verifies the frozen package.
- `cluster.env.azure.example` — exact VM2/rack-a, VM1/rack-b, VM3/rack-c private-IP mapping.
- `RUN_VM2_STAGE_A.sh` — authoritative legacy-comparator Stage-A calibration on VM2.
- `02_DISTRIBUTE_STAGE_A_FROM_VM2.sh` — hash-preserving coefficient snapshot distribution.
- `RUN_VM1_RANDOM.sh` — VM1's 80-graph primary shard with 2 workers.
- `RUN_VM2_RANDOM.sh` — VM2's 120-graph primary shard with 3 workers.
- `RUN_VM3_SECONDARY.sh` — 120-identity RQ1 prediction panel + 80 structured graphs + SNOB5G, 1 worker.
- `03_COLLECT_RESULTS_TO_VM2.sh` — collect/hash-check worker result bundles.
- `RUN_VM2_MERGE_AND_FINISH.sh` — exact 200-graph merge, 20-graph oracle, B3-only load pilot, 40-graph RQ3, final analysis.
