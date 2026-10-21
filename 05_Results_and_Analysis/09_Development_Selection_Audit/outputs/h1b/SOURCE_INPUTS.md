# H1-B source inputs and integrity

The diagnostic reads existing source archives directly and does not modify them.

- `PAPER2_EXISTING_DATA_POSTCONFIRMATORY_REPRO_20261016.zip` SHA-256: `686c81b1fc7897fa7224029f64b964a76beec662ed259e766f3ab155a4962511`
- `PAPER2_B5_RESULTS_PART1_STAGES_A_TO_D.zip` SHA-256: `9be9ac59ad1bbab112591b8d7af3281fc3bf7fa562f182e2d3cc1fab1bf070c1`
- `fit_b5_development.py` member SHA-256: `ef94df40d31f0c83159b58d8896dea978fa2220bc7b7ac66f869f9569892e7c1`
- `B5_DEVELOPMENT_CV_AUDIT.json` member SHA-256: `270b67cd6fa92ab63d5a531535b97d29aaea7b9f860517b1d871485bcfaa9152`
- `B5_MODEL_LOCK.json` member SHA-256: `67ed2d21f92bfe0a2df6dde94d8eb52d586c5d3730932ca9750261c7029c5aec`
- CV audit JSON identical across both archives: `True`
- Model lock identical across both archives: `True`

Embedded development CSV hashes:
- `PAPER2_EXISTING_DATA_POSTCONFIRMATORY_REPRO_20261016/01_mechanism_control/source/campaign_code/development_reference/B4_ORACLE_CANDIDATES.csv` SHA-256: `2689e7271a6a0ad26edc69d0519d52e43358ef97992f8a1cb6bd475cca1d1810`
- `PAPER2_EXISTING_DATA_POSTCONFIRMATORY_REPRO_20261016/01_mechanism_control/source/campaign_code/development_reference/B4_RANDOM_GRAPH_SELECTIONS.csv` SHA-256: `259334d23415bd45d59f1a344a12e458627494393f74b8c9764ac5ee4390f7b9`
- `PAPER2_EXISTING_DATA_POSTCONFIRMATORY_REPRO_20261016/01_mechanism_control/source/campaign_code/development_reference/B4_STAGE_D_GRAPH_METHOD_STATE.csv` SHA-256: `03784c84d3230d1a55b3531e6fe4169c6d89def3704105ec5ac41cec7a6999ce`
- `PAPER2_EXISTING_DATA_POSTCONFIRMATORY_REPRO_20261016/01_mechanism_control/source/campaign_code/development_reference/B4_STRUCTURED_GRAPH_METHOD.csv` SHA-256: `b80de334c3ce2793ae20e5828727de9f195043bac3f68b84f83f0061887319ed`

Frozen model-lock input-hash matches:
- `B4_ORACLE_CANDIDATES.csv` matches `B5_MODEL_LOCK.json`: `True`
- `B4_RANDOM_GRAPH_SELECTIONS.csv` matches `B5_MODEL_LOCK.json`: `True`
- `B4_STAGE_D_GRAPH_METHOD_STATE.csv` matches `B5_MODEL_LOCK.json`: `True`
- `B4_STRUCTURED_GRAPH_METHOD.csv` matches `B5_MODEL_LOCK.json`: `True`
