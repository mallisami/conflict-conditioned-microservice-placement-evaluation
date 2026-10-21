# Frozen sample-size and precision rationale — B5 confirmation

The unit of inference is always the prespecified independent traffic-shape or graph identity.

- **RQ1:** 60 ID + 60 OOD identities give balanced representation across four OOD families while keeping candidate execution tractable. Candidate rows and packet RNGs are nested and do not inflate N.
- **RQ2:** 200 random graphs (50 per n=8/12/16/24). Historical B4 Stage-D paired differences had SD ≈ 0.0249. For a prespecified relevant absolute delivered-fraction difference of 0.005, a conventional paired normal approximation gives about 195 units for 80% power at two-sided alpha 0.05; n=200 was therefore frozen before B5 confirmation.
- **Structured:** 80 graphs = 4 topology families × 4 sizes × 5 identities. This is a separate generalization layer, not pooled with RQ2.
- **Oracle:** 20 exhaustive n=8 identities balance full-candidate packet execution cost with paired regret estimation.
- **RQ3:** 40 graph identities with three nested repeats and three frozen load regimes. Repeats reduce measurement noise; graph identity remains the inference unit.

Power calculations are design aids, not guarantees. All final claims are based on paired effect estimates and 95% confidence intervals, with practical-effect thresholds reported separately.
