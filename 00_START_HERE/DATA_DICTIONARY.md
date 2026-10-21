# Data dictionary and folder conventions

## File formats

- **CSV:** row-oriented measurement records, graph-level metrics, or accepted per-run summaries. Column names are retained from the experimental output.
- **JSON:** frozen plans/configurations, graph/cell records, accepted-run metadata, and derived machine-readable summaries.
- **`accepted.json`:** metadata and accepted output for the specific run/cell/replicate represented by its parent directory. It is an experimental result record, not an operational log.
- **`SHA256SUMS.txt`:** release-level SHA-256 manifest. Each raw study ZIP also contains `__ARCHIVE_METADATA__/SHA256SUMS.txt`, a file-level manifest for the original raw records in that archive.
- **`RAW_DATA_FILE_INDEX.csv`:** searchable inventory of each raw file with its archive, original relative path, size, SHA-256, type, and any graph/seed/method/replicate/attempt fields explicitly encoded in the path. Blank fields mean the path does not encode that value; the index does not infer missing metadata.

## Raw-data study archives

The raw-data folder contains ten ZIP archives rather than tens of thousands of nested directories. Each ZIP preserves the original relative path structure. `RAW_DATA_INDEX.csv` lists each study, its purpose, raw file count, uncompressed byte count, and archive size. Extract one study with `python 00_START_HERE/unpack_raw_data.py --study <STUDY_NAME>`; use `--all` to extract all studies.

- `01_RQ1_Prediction_Panel.zip`: prediction panels and per-run records for RQ1.
- `02_RQ2_Selection_Graphs.zip`: graph identities and selection decisions for RQ2.
- `03_Telemetry_Robustness.zip`: per-graph robustness records under telemetry perturbation.
- `04_RQ2_Packet_Execution.zip`: accepted packet-execution runs and packet-level records.
- `05_Structured_Topologies.zip`: structured-topology graph and execution records.
- `06_Oracle_Execution.zip`: exhaustive admitted-placement execution records.
- `07_Measured_Rate_State_Replay.zip`: frozen measured-rate vectors and accepted replay records.
- `08_StageE_Load_Pilot.zip`: accepted load-pilot cell records.
- `09_Initial_Kubernetes_Experiment.zip`: graph inputs and accepted cell/replicate records for the initial Kubernetes study.
- `10_Fresh_Kubernetes_RQ3.zip`: fresh RQ3 graph identities and accepted execution cells, including panel/seed/method/replicate records.

## Derived results

`05_Results_and_Analysis/` contains compact summaries and analysis tables used to interpret the reported paper displays. It is intentionally separate from raw per-run records.

## Model and protocol files

`02_Methods_and_Configuration/01_Protocols/` contains the governing confirmatory protocol and the separate fresh-RQ3 protocol/lock/seed registry. The superseded v1.0 confirmatory protocol is intentionally not included; v1.1 is the governing version. Model-lock JSON and associated SHA-256 sidecars define the coefficients and configuration used by the reported runs.

## Exclusions

No internal audit/review reports, workflow logs, command transcripts, superseded manuscript/protocol versions, or unperformed experiment result files are included. No raw measurement file was removed from the original workspace; the ZIP archives are a curated copy preserving the raw file bytes and relative paths.
