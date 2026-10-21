# Common hard-admissible candidate-set invariants — B5 confirmation

For every confirmatory placement graph:

1. Enumerate every placement reachable within the frozen move neighborhood in deterministic order.
2. Apply inherited cluster constraints and hard wireless availability/shared-airtime admission once.
3. Canonically serialize each admissible placement as sorted `(replica,node)` pairs and stream them into one SHA-256 digest.
4. Store the common candidate count and `X_adm_sha256` once per graph.
5. B0/B1/B2/B3/A1/B4/B5 and B5 ablations are scored in the same enumeration pass. No method gets a different feasible region.
6. B5's near-margin and B1 tie-break operate only after the same X_adm has been formed; they do not modify feasibility.
7. Every selected placement is independently re-evaluated for hard admissibility before packet execution.
8. Any digest/evaluator inconsistency is an implementation failure that blocks downstream execution; no graph is dropped to improve a comparison.
9. The inherited enumerator must pass the implementation reproduction gate before new confirmatory graphs execute; reproduction-gate outputs never enter effect estimation.
