# Paper-II B5 Confirmatory Protocol v1.1 — Frozen 2026-10-09

## Status
This is a **pre-outcome confirmatory protocol**. The completed B4 campaign is development/diagnostic evidence only. No B4 development graph, shape, oracle identity, Kubernetes graph, or external-validation graph may be counted as B5 confirmatory evidence.

## Research questions
**RQ1 — Predictive fidelity and transfer.** Does conflict-aware contention information improve prediction of execution degradation beyond aggregate-utilization models on held-out workloads, and does that improvement persist under prespecified distribution shift?

**RQ2 — Placement decision quality.** When all methods rank the same hard-admissible placement set, does conflict-aware ranking improve selected-placement quality relative to utilization-only and existing placement baselines, as measured by executed network performance and execution-oracle regret?

**RQ3 — End-to-end operational value.** Do improvements in predictive fidelity and placement quality translate into measurable application-level benefits under multi-host execution and realistic workload conditions?

The evidence hierarchy is deliberately sequential but not inferentially substitutable:

`better prediction != better placement != better application performance`.

## B5 method
For each candidate placement and wireless state, traffic is mapped to directed shared-airtime conflict groups. Within group `g`, let normalized stream airtime shares be `p_{ig}` and define `P_g = 1 - sum_i p_{ig}^2`. Let `w_g` be that group's share of total cross-rack bits. The placement-level conflict balance is `P_C = sum_g w_g P_g`, and `U_max` is the maximum frozen group utilization. The primary conflict exposure implemented by B5 is

`E_C = U_max * P_C`.

This distinguishes placements with equal aggregate load but different concentration inside the groups where contention actually occurs.

The frozen primary predictor is

`D_hat_B5 = beta_0 + beta_1 E_C`, with `beta_1 >= 0`.

Coefficients and all decision hyperparameters are contained in `b5_lock/B5_MODEL_LOCK.json`. They were selected using historical B4 development evidence only and are immutable during confirmation.

B5 development fitting combines pointwise Huber prediction loss with pairwise decision-aware ranking loss. Pairwise ranking errors are weighted by observed execution separation so that reversing materially different candidates is penalized more strongly than reversing near-equivalent candidates.

### Decision rule
Let `D_min` be the minimum frozen B5 score in the exact hard-admissible candidate set. Candidates within the frozen development-selected near-margin `delta_D` form a near-optimal predicted set. B5 selects the member of this set with best B1 affinity objective, then lowest move count, then deterministic placement key. `B5_NOTIE` removes this safeguard and selects the strict B5 score minimum.

### Ablations
- `B5_MAE_ONLY`: same conflict-conditioned representation but prediction-only development fitting.
- `B5_GLOBAL_RANK`: global concentration analogue rather than conflict-conditioned concentration.
- `B5_NOTIE`: full B5 predictor with strict top-1 selection and no affinity stabilization.

## Identical admissible set rule
For every graph/workload instance, resource and hard wireless admission are applied exactly once to form `X_adm`. B1, B3, A1, B4, B5, and all B5 ablations rank the same `X_adm`. Candidate-set SHA-256 is recorded. No method obtains a different feasible region.

## RQ1 confirmatory prediction panel
Primary RQ1 evidence comes from `config/b5_prediction_panel.json`, not the historical B4 Stage-A holdout.

- 60 untouched ID graph identities: seeds 105001–105060.
- 60 untouched OOD identities: 15 Zipf, 15 hotspot, 15 bimodal, 15 lognormal.
- n=8 setting.
- 12 deterministic score-independent candidates sampled uniformly over the exact admissible enumeration for each graph.
- Conflict-dense ns-3 execution with three frozen packet RNG runs.
- Graph identity is the inference unit; candidate rows are nested.
- Primary contrast: B5 vs B3 graph-level MAE.
- OOD support is evaluated separately and cannot be inferred from ID support.

Legacy Stage A is executed only to calibrate/freeze B3/A1/B4 comparator coefficients and is not B5 confirmatory evidence.

## RQ2 random-graph confirmation
200 new identities: 50 each at n=8, n=12, n=16, n=24. The primary execution state is conflict-dense. Three packet RNG runs are nested within graph. Primary contrast is B5 minus B3 delivered fraction. A prespecified practical-effect threshold of 0.005 absolute delivered fraction is reported separately from statistical support.

The 200 graphs are deterministically sharded across Azure compute nodes: VM1 receives 80 (20/size), VM2 receives 120 (30/size). No dynamic reassignment creates new replicates.

## Structured confirmation
80 independent structured identities: pipeline, fan-out/fan-in, hub-and-spoke, mesh × n=8/12/16/24 × 5 seeds. This is secondary generalization evidence and is not pooled with the 200 primary random graphs.

## Execution oracle
20 untouched n=8 identities, seeds 97001–97020. Every admissible candidate is packet-executed. Report candidate-level Spearman correlation, exact-best capture, near-best capture, mean/median regret, and paired regret contrasts. This is an **ns-3 execution oracle**, not physical ground truth.

## Robustness
At ±5%, ±10%, and ±20% telemetry perturbation, the nominal `X_adm` remains frozen and is rescored. Three perturbation levels × five realizations are evaluated per graph. The hard-admission set is not recomputed under perturbation.

## RQ3 three-host Kubernetes confirmation
40 untouched graph identities, seeds 98001–98040, are distinct from all RQ2/oracle/external identities. Methods: B1, B3, B5. Three repeats are nested per graph/method/load regime.

A B3-only development pilot on historical seeds chooses three offered-load multipliers before any B5 RQ3 outcome exists. The primary high-load regime must place B3 mean scheduled completion in the frozen 0.85–0.95 discrimination band; otherwise RQ3 confirmation is blocked. Moderate and near-capacity regimes are secondary sensitivity conditions.

Primary endpoint: scheduled-request completion fraction at the frozen high-load regime. Secondary endpoints: timeout-augmented p95 latency, successful throughput, and shared-medium queue waiting. Failure to reject zero is never described as equivalence without a prespecified equivalence test.

Stage E is **three-host Kubernetes end-to-end emulation under the frozen shared-airtime abstraction**, not physical 60-GHz validation.

All experimental service replicas use identical frozen CPU requests **and matching CPU limits** plus identical memory reservations, so the 4/4/2-vCPU host capacities cannot create uncontrolled per-pod burst advantages.

## SNOB5G
SNOB5G supplies measured IEEE 802.11ad/mmWave rate-state sensitivity inputs only. New external graph identities use the frozen 960xx blocks. Quantile-derived states are within-graph sensitivity points and are not independent replicates. This stage does not validate physical concurrent-link contention.

## DeathStarBench and physical 60-GHz
DeathStarBench Hotel Reservation is a required secondary non-hardware validation stage in v1.1. It must pass all six real-workload inclusion gates: measured directed service bytes, same hard admission, identical `X_adm`, actual selected deployments, cross-rack application traffic traversing the shared-medium mechanism, and live co-location of each bundle-local MongoDB/Memcached companion with its owning movable service. It cannot be replaced by a synthetic surrogate.

Physical concurrent 60-GHz validation remains outside the required campaign because actual RF equipment is not available in this package. The frozen protocol and analyzer are retained for future hardware validation only. Azure Ethernet/Kubernetes emulation cannot be represented as physical 60-GHz evidence.

## Statistics
Independent units are graph or traffic-shape identities, never packet cells or nested repeats. Final bootstrap inference uses 100,000 paired resamples with frozen seeds. Secondary comparator families use Holm adjustment. Exact effects and confidence intervals are always reported. Statistical support and practical relevance are distinct.

## No outcome-dependent modification
After this freeze, do not change B5 features, coefficients, lambda, regularization, near-margin, candidate counts, graph identities, seeds, methods, load-selection rule, primary states/endpoints, SESOI thresholds, or statistical rules because of intermediate outcomes. Infrastructure failures may be retried under the frozen resumability rules. Null and unfavorable outcomes remain scientific evidence.

## v1.1 non-hardware completeness amendment — genuine real-workload confirmation
The three primary RQs, B5 model lock, confirmatory identities, primary endpoints, SESOI, and statistical decision rules are unchanged from v1.0. This amendment closes the previously gated non-hardware external-validity item **before confirmatory outcomes are opened**.

DeathStarBench Hotel Reservation is now a required secondary validation stage. The source is pinned to commit `6ecb09706140f8730b5385c08f1386c654c3c526`. Eight application bundles (`frontend`, `geo`, `profile`, `rate`, `reccomend/recommendation`, `reserve/reservation`, `search`, `user`) are movable; Consul, Jaeger, databases and caches are fixed infrastructure. A transparent TCP proxy sidecar sits behind each application Service. During calibration it observes the real gRPC/HTTP byte stream without shaping; during confirmation it subjects cross-rack bytes to the same frozen conflict-group shared-airtime scheduler used by Stage E while preserving the application protocol and payload.

The directed service-byte matrix is measured from a calibration-only neutral placement and hashed before any B1/B3/B5 ranking. A B3-only offered-load pilot selects the prespecified discriminating completion band. The final method comparison uses fresh application state per cell, randomized method order, identical resource limits, the same hard-admissible set, actual method-selected Kubernetes placements, and 12 confirmation blocks. DeathStarBench is secondary real-workload generalization and never substitutes for the 200-graph RQ2 test.

Physical concurrent 60-GHz equipment is explicitly outside the required v1.1 campaign. Its protocol and analyzer are retained only as an optional future physical-mechanism extension and are not required for campaign completeness.

## Real-workload warm-up control
Every fresh DeathStarBench cell executes a fixed 15-s method-independent warm-up (capped at 20 requests/s), then resets proxy and shared-medium metrics before the measured window. This prevents container/database startup effects from being interpreted as placement effects.


## Frozen multi-rack admissibility control

The hard-admissible set uses a method-independent maximum of **three movable application bundles per rack**. With eight movable bundles across three racks, every admissible DeathStarBench placement is necessarily multi-rack; this prevents a trivial all-colocated solution while applying the identical capacity constraint to B1, B3, and B5.
## Frozen paired workload driver

The DeathStarBench **application source is not modified**. The load generator starts from the exact pinned upstream Hotel Reservation mixed-workload blob `d4627e7b4c70528389096d131da199e620b2e2d5`. A generated Paper-II driver applies only two provenance-locked corrections before the client image is built: (1) it accepts a frozen `PAPER2_WORKLOAD_SEED` instead of seeding from wall-clock time, and (2) it defines the reservation branch's missing `lat`/`lon` variables using the same coordinate distribution already used by the upstream search/recommendation branches. The upstream request mix (0.60 search, 0.39 recommendation, 0.005 user, 0.005 reservation) is unchanged.

Confirmation uses one wrk2 thread and a single frozen request seed per block; that same block seed is reused for B1, B3, and B5 while method order is randomized. This creates a paired real-workload comparison without modifying the Hotel Reservation application behavior. The generated driver and its SHA-256 provenance are mandatory preflight gates. The client image includes the LuaSocket runtime dependency required by the pinned upstream script.

