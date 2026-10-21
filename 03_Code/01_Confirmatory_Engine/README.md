# Confirmatory experiment engine

This is the frozen implementation for the original prediction, selection, packet-execution, robustness, structured-topology, oracle, measured-rate replay and initial Kubernetes studies. Preserve relative source, configuration and dependency paths when running these scripts; code names such as `B3`, `B5`, and `Stage A–E` are scientific identifiers.

## Find the relevant implementation

| Experimental component | Main entry point |
| --- | --- |
| Generate calibration or base workloads | [`src/run_stage_a.py`](src/run_stage_a.py) and [`src/generate_stage_a_cases.py`](src/generate_stage_a_cases.py) |
| Generate shifted-demand cases | [`src/run_stage_a_ood.py`](src/run_stage_a_ood.py) |
| Freeze development-model coefficients | [`src/fit_b5_development.py`](src/fit_b5_development.py) and [`b5_lock/`](b5_lock/) |
| Evaluate RQ1 prediction | [`src/run_b5_prediction_panel.py`](src/run_b5_prediction_panel.py) |
| Stage C: hard admission and placement selection | [`src/run_stage_c.py`](src/run_stage_c.py) |
| Stage C robustness | [`src/run_stage_c_robustness.py`](src/run_stage_c_robustness.py) |
| Stage D: packet execution | [`src/run_stage_d.py`](src/run_stage_d.py) and [`simulator/`](simulator/) |
| Execution oracle and structured-topology tests | [`src/run_stage_d_oracle.py`](src/run_stage_d_oracle.py) and [`src/run_structured_topologies.py`](src/run_structured_topologies.py) |
| Measured-rate-state replay | [`src/run_external_validation.py`](src/run_external_validation.py) |
| Stage E: initial Kubernetes execution | [`src/run_stage_e.py`](src/run_stage_e.py), [`benchmark/`](benchmark/) and [`stage_e_support/`](stage_e_support/) |

The source tree also includes the `deps/mape_cap_bplus/` modeling dependency, `config/` runtime and scenario settings, `development_reference/` model-development inputs, and `vm/` execution helpers. Development-only inputs must not be reported as held-out results.

## Reproduce responsibly

1. To **check reported graph-level results without rerunning**, use the public [result verification script](../../00_START_HERE/verify_public_graph_results.py).
2. To **trace experimental evidence**, open the [experiment–artifact map](../../00_START_HERE/EXPERIMENT_ARTIFACT_MAP.md) and [frozen methods](../../02_Methods_and_Configuration/).
3. To **rerun** a study, first obtain the corresponding locked plans and any original raw inputs through a permitted route, configure the documented simulator/Kubernetes environment, and follow the governing protocol.

The ten original raw-study ZIPs are **not** deposited in this public repository. Some original Stage-D and oracle plans are also absent; see [data availability](../../DATA_AVAILABILITY.md). The adapted WiGig/ns-3 C++ file is present, with upstream [GPL-2.0 attribution](../../THIRD_PARTY_NOTICES.md). No unperformed DeathStarBench or physical-radio results are implied.
