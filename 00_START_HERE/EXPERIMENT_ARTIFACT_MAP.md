# Experiment-to-artifact map

Follow each reported result from its protocol/configuration through source code, the per-study raw-data archive, derived result table, and paper display. Raw paths listed inside the archives are relative to the corresponding study folder; use `RAW_DATA_FILE_INDEX.csv` to search those paths.

| Study / paper component | Governing method/configuration | Main code | Accepted raw archive | Derived results |
|---|---|---|---|---|
| RQ1 prediction: in-distribution and traffic-shift panels | `02_Methods_and_Configuration/01_Protocols/PAPER2_B5_CONFIRMATORY_PROTOCOL_V1_1_20261009.md`; prediction-panel plan and Stage-A configs | `03_Code/01_Confirmatory_Engine/src/run_b5_prediction_panel.py`, Stage-A runners | `04_Raw_Experimental_Data/01_RQ1_Prediction_Panel.zip` | `05_Results_and_Analysis/01_RQ1_Prediction/` |
| RQ2 common feasible-set selection | Stage-C protocol and `stage_c.json`; candidate-set invariants | `03_Code/01_Confirmatory_Engine/src/run_stage_c.py` | `04_Raw_Experimental_Data/02_RQ2_Selection_Graphs.zip` | `05_Results_and_Analysis/02_RQ2_Selection_and_Packet_Execution/` |
| RQ2 packet execution / delivery | Stage-D plan and frozen B3/B5 model locks | `03_Code/01_Confirmatory_Engine/src/run_stage_d.py` | `04_Raw_Experimental_Data/04_RQ2_Packet_Execution.zip` | `05_Results_and_Analysis/02_RQ2_Selection_and_Packet_Execution/` |
| Telemetry robustness | Confirmatory protocol and robustness configuration | `03_Code/01_Confirmatory_Engine/src/run_stage_c_robustness.py` | `04_Raw_Experimental_Data/03_Telemetry_Robustness.zip` | `05_Results_and_Analysis/03_Robustness/` |
| Structured-topology transfer | Structured-topology plan and configuration | `03_Code/01_Confirmatory_Engine/src/run_structured_topologies.py` | `04_Raw_Experimental_Data/05_Structured_Topologies.zip` | `05_Results_and_Analysis/04_Structured_Topologies/` |
| Exhaustive packet-execution oracle | Oracle plan and candidate inputs | `03_Code/01_Confirmatory_Engine/src/run_stage_d_oracle.py` | `04_Raw_Experimental_Data/06_Oracle_Execution.zip` | `05_Results_and_Analysis/05_Oracle_Execution/` |
| Measured-rate-state replay | Frozen rate vectors and replay plan | `03_Code/01_Confirmatory_Engine/src/run_external_validation.py` | `04_Raw_Experimental_Data/07_Measured_Rate_State_Replay.zip` | `05_Results_and_Analysis/06_Measured_Rate_State_Replay/` |
| Stage-E load pilot | B3 pilot selections and load-pilot plan | `03_Code/01_Confirmatory_Engine/src/run_stage_e.py` and calibration support | `04_Raw_Experimental_Data/08_StageE_Load_Pilot.zip` | Pilot summary in `05_Results_and_Analysis/07_Initial_Kubernetes_Experiment/` |
| Initial high-load Kubernetes study | Stage-E configuration and frozen model locks | `03_Code/01_Confirmatory_Engine/src/run_stage_e.py` | `04_Raw_Experimental_Data/09_Initial_Kubernetes_Experiment.zip` | `05_Results_and_Analysis/07_Initial_Kubernetes_Experiment/` |
| Fresh Kubernetes RQ3 extension | Fresh-RQ3 protocol, lock, and seed registry | `03_Code/02_RQ3_Fresh_Kubernetes_Extension/` | `04_Raw_Experimental_Data/10_Fresh_Kubernetes_RQ3.zip` | `05_Results_and_Analysis/08_Fresh_Kubernetes_RQ3/` |

All ten study archives are listed in `RAW_DATA_INDEX.csv`. `09_Initial_Kubernetes_Experiment.zip` and `10_Fresh_Kubernetes_RQ3.zip` are separate studies and must not be pooled.

## Manuscript source

`01_Manuscript/Main_Manuscript.pdf` and `01_Manuscript/Supplementary_Material.pdf` are built directly from the single-file LaTeX sources and figure assets in `01_Manuscript/LaTeX_Source/`, so the PDFs and sources cannot drift apart.
