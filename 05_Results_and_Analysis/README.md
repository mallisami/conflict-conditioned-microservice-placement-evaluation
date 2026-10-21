# Experimental results and analysis

This directory holds **derived, reviewer-readable outcomes** from the frozen experiments. It is **not** the original per-run raw packet-log archive. To recompute the primary reported paired means and counts, run from the repository root:

```bash
python3 00_START_HERE/verify_public_graph_results.py
```

## Results by research question and supporting analysis

| Folder | Main use | Suggested starting file |
| --- | --- | --- |
| [01 — RQ1 prediction](01_RQ1_Prediction/) | In-distribution and shifted-traffic predictor comparison | [Graph-level metrics](01_RQ1_Prediction/PREDICTION_PANEL_GRAPH_METRICS.csv) |
| [02 — RQ2 selection and packet delivery](02_RQ2_Selection_and_Packet_Execution/) | Same-admissible-set placement decisions, packet delivery, win/loss/tie decomposition | [RQ2 graph-level paired outcomes](02_RQ2_Selection_and_Packet_Execution/RQ2_Selection_and_Delivery_Graph_Level.csv) |
| [03 — robustness](03_Robustness/) | Telemetry-perturbation sensitivity | [Robustness summary](03_Robustness/ROBUSTNESS_SUMMARY.json) |
| [04 — structured topologies](04_Structured_Topologies/) | Generalization to structured graphs | [Structured graph outcomes](04_Structured_Topologies/STRUCTURED_GRAPH_METHOD.csv) |
| [05 — exhaustive oracle](05_Oracle_Execution/) | Execution-oracle regret and stabilizer attribution | [Oracle summary](05_Oracle_Execution/ORACLE_SUMMARY.json) |
| [06 — measured-rate replay](06_Measured_Rate_State_Replay/) | Sensitivity to external measured link-rate states | [Replay summary](06_Measured_Rate_State_Replay/EXTERNAL_VALIDATION_SUMMARY.json) |
| [07 — initial Kubernetes experiment](07_Initial_Kubernetes_Experiment/) | **Original 40-graph panel**, high-load and pilot outputs | [Execution cells](07_Initial_Kubernetes_Experiment/STAGE_E_CELLS.csv) |
| [08 — fresh Kubernetes RQ3](08_Fresh_Kubernetes_RQ3/) | **Separate post-confirmatory 256-graph panel**, paired effects, 128-graph mechanism check | [Final summary](08_Fresh_Kubernetes_RQ3/RQ3_FINAL_SUMMARY.json) · [Paired inference cells](08_Fresh_Kubernetes_RQ3/RQ3_MAIN_INFERENCE_CELLS.csv) |
| [09 — development selection audit](09_Development_Selection_Audit/) | Retrospective audit of model-selection and training history | [Audit guide](09_Development_Selection_Audit/README.md) |

The **graph identity**, not a nested simulator packet, station, or Kubernetes repeat, is the independent unit for the primary paired inferences. Do **not** pool the initial 40-graph Kubernetes study with the 256-graph post-confirmatory study.

**Scope:** The public verification script recalculates selected point estimates and RQ2 accounting from these tables. Complete raw-trace integrity, every confidence interval, historical Stage-A refitting, and ns-3/Kubernetes reruns require other evidence or environments. See [reproduction guide](../00_START_HERE/REPRODUCTION_GUIDE.md) and [data availability](../DATA_AVAILABILITY.md).
