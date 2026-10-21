# Methods, frozen configurations and experimental protocols

Use this directory to identify the **exact methods and parameters** governing the published results. Files carrying internal names such as `PAPER2`, `B5`, or an original protocol revision are **frozen provenance identifiers**, not GitHub release names; their contents must not be renamed or silently altered.

| Subdirectory | What to inspect | Reason |
| --- | --- | --- |
| [`01_Protocols/`](01_Protocols/) | Original confirmatory design, candidate-set invariants, sample-size rationale, independent fresh-RQ3 protocol and locks | Separates prespecified evidence from post-confirmatory work |
| [`02_Experiment_Plans/`](02_Experiment_Plans/) | RQ1 prediction plan; structured topologies; measured-rate replay; oracle/packet-execution plan inventories | Specifies graph identities, conditions and source-locked execution plans |
| [`03_Model_Locks/`](03_Model_Locks/) | Frozen B3 and B5 coefficient records and accompanying hashes | Establishes the exact baseline and candidate-scoring coefficients |
| [`04_Model_Development_Inputs/`](04_Model_Development_Inputs/) | Preserved B4 development inputs used in model-selection history | Development provenance, **not held-out results** |
| [`REPRODUCIBILITY_SCOPE.md`](REPRODUCIBILITY_SCOPE.md) | Public-versus-offline availability and methodological limits | Prevents misleading reproduction claims |

**Important:** The original historical B3 Stage-A calibration CSV is not available, although the frozen B3 coefficients and downstream evaluation are retained. The exact oracle and packet-execution plans are now provided as [oracle ZIP](02_Experiment_Plans/Oracle_Execution/ORACLE_PLAN.json.zip) and [Stage-D ZIP](02_Experiment_Plans/RQ2_Packet_Execution/STAGE_D_PLAN.json.zip), with original JSON paths and digests verified. Raw execution logs are separately retained; see the [outstanding-file index](../PUBLIC_DEFERRED_FILE_INDEX.csv) for remaining omissions.

For paper-outcome mappings, start with [experiment–artifact map](../00_START_HERE/EXPERIMENT_ARTIFACT_MAP.md). For file-access terms and limitations, see [data availability](../DATA_AVAILABILITY.md).
