# Core Evaluation Evidence Pack

- Summary schema: `core-evaluation-summary.v1`
- Evaluation manifest schema: `scientific-evaluation-manifest.v1`
- Evaluation result schema: `scientific-evaluation-result.v1`
- Policy schema: `scientific-policy-evaluation.v1`
- Scope: `FULL_CAMPAIGN`
- Overall status: `CORE_EVALUATION_ACCEPTED`

## Identity and provenance

- Evaluation manifest: `sha256:ca9944139b1434640e082ca1be9d67d97833e8a9830bcdde28412a16c21ebf97`
- Evaluation result: `sha256:cc5684675c235f9fa81986fa3bc5db9b7b7bb1594815db7b727fd32eaa5ec2cd`
- Scientific identity: `sha256:7c43ab7d9b7f37fa4a8a876440f7e728fa5e68abb7350ee0a58550f17fa35a47`
- Source identity: `sha256:e8f01d6c03830f572244aab4674b9159fc79cff2cc93a26e5a10f299d3db2dfa`
- Environment identity: `sha256:347c9a7c89f436ead36e3f690f0d8dee9bb473aad294064ee1f61036353e8964`
- Runtime state: `ACCEPTED`
- Runtime lock: `sha256:c2153480af7ef58e4cd4f132831c74235d7689fe731c7be53570feedd918b4f3`
- Seed policy: `{"paired_by_seed":true,"seed_count":100,"seed_policy_id":"sha256-coordinate-seeds","seed_policy_version":"v1","seed_start":160016}`
- Seeds (paired, 100): `[160016,160017,160018,160019,160020,160021,160022,160023,160024,160025,160026,160027,160028,160029,160030,160031,160032,160033,160034,160035,160036,160037,160038,160039,160040,160041,160042,160043,160044,160045,160046,160047,160048,160049,160050,160051,160052,160053,160054,160055,160056,160057,160058,160059,160060,160061,160062,160063,160064,160065,160066,160067,160068,160069,160070,160071,160072,160073,160074,160075,160076,160077,160078,160079,160080,160081,160082,160083,160084,160085,160086,160087,160088,160089,160090,160091,160092,160093,160094,160095,160096,160097,160098,160099,160100,160101,160102,160103,160104,160105,160106,160107,160108,160109,160110,160111,160112,160113,160114,160115]`

### Source identities

- `evaluation_implementation`: `core-scientific-evaluation-harness` / `v1` — `sha256:166614b917d44b6565199aea4d634f7d15bbd132944724e8aa64dcc1bde240d8`
- `base_dgp`: `core-semi-synthetic-dgp-base` / `v1` — `sha256:0c2cda8a25eaedf01937972ad5a9057376bb4714f9b444705a28a4fd53756d22`
- `external_boundary`: `olist-validation` / `olist-validation.mapping.v1` — `sha256:aa5cc8e38cf7e38e8d995fe1b018c9f5651929a3548c6fd4ee0c24045f0cb45c`
- `external_boundary`: `scms-rejection-vignette` / `scms-rejection-vignette.mapping.v1` — `sha256:b6c3f18fb821be5e10bf48385c071669c66b0736aaef92820c2cfb84917d13c0`
- `synthetic_fixture_boundary`: `synthetic://core-decision-support/v1` / `v1` — `sha256:0cc8805bbec23c417b1fb2c008a4fbae595521122531e87a7461322e2b4d96ca`

## Integrity and claim states

- Runtime: `{"expected":{"doubleml":"0.11.3","dowhy":"0.14","evaluation_runtime":"stdlib-deterministic-v1","numpy":"2.2.6","python":"3.12.13","scikit_learn":"1.6.1","scipy":"1.15.3"},"observed":{"doubleml":"0.11.3","dowhy":"0.14","evaluation_runtime":"stdlib-deterministic-v1","numpy":"2.2.6","python":"3.12.13","scikit_learn":"1.6.1","scipy":"1.15.3","thread_policy":"single_process_single_threaded_evaluator"},"reason_code":"EVALUATION_RUNTIME_MATCHED","runtime_lock_hash":"sha256:c2153480af7ef58e4cd4f132831c74235d7689fe731c7be53570feedd918b4f3","state":"ACCEPTED"}`
- Integrity: `{"invalid_seed_count":0,"manifest_hash":"sha256:ca9944139b1434640e082ca1be9d67d97833e8a9830bcdde28412a16c21ebf97","reason_code":"EVALUATION_ARTIFACTS_INTEGRITY_VERIFIED","state":"ACCEPTED"}`
- Reproducibility: `{"method":"deterministic_public_projection_replay","mismatches":[],"projection_hash":"sha256:2f331db5dd514e1d668fd194a9bc5af6a4a1fa8853230224b2877a4d731ec9c0","reason_code":"EVALUATION_REPLAY_MATCHED","replayed_projection_hash":"sha256:2f331db5dd514e1d668fd194a9bc5af6a4a1fa8853230224b2877a4d731ec9c0","state":"ACCEPTED"}`
- Claim-state counts: ACCEPTED=20; REJECTED=0; UNAVAILABLE=5; INVALID=0

| Claim ID | State | Reason | Evidence refs | Observed | Threshold |
| --- | --- | --- | --- | --- | --- |
| TRUE_EFFECT_ESTIMATION_QUALITY | ACCEPTED | TRUE_EFFECT_BIAS_GATE_PASSED | sha256:3deb24ab896ae158ab70f72c89e5f7a49349c8c06c4f79628fe87d0568384def | {"relative_bias":0.0180368203} | {"relative_bias_max":0.1} |
| TRUE_EFFECT_INTERVAL_COVERAGE | ACCEPTED | TRUE_EFFECT_COVERAGE_GATE_PASSED | sha256:3deb24ab896ae158ab70f72c89e5f7a49349c8c06c4f79628fe87d0568384def | {"interval_coverage":0.98} | {"maximum":0.99,"minimum":0.9} |
| TRUE_EFFECT_PREDICTION_ONLY_DECISION_VALUE | ACCEPTED | COPILOT_SUPERIORITY_GATE_PASSED | sha256:3deb24ab896ae158ab70f72c89e5f7a49349c8c06c4f79628fe87d0568384def | {"mean_regret_reduction":3007.03,"one_sided_lower_bound":3005.60145} | {"lower_bound_strictly_positive":true,"minimum_regret_reduction":411.1189152356} |
| TRUE_EFFECT_CORRELATION_ONLY_DECISION_VALUE | ACCEPTED | COPILOT_SUPERIORITY_GATE_PASSED | sha256:3deb24ab896ae158ab70f72c89e5f7a49349c8c06c4f79628fe87d0568384def | {"mean_regret_reduction":577.587,"one_sided_lower_bound":577.166} | {"lower_bound_strictly_positive":true,"minimum_regret_reduction":411.1189152356} |
| TRUE_EFFECT_ALWAYS_EXPEDITE_DECISION_VALUE | ACCEPTED | COPILOT_SUPERIORITY_GATE_PASSED | sha256:3deb24ab896ae158ab70f72c89e5f7a49349c8c06c4f79628fe87d0568384def | {"mean_regret_reduction":5990.487,"one_sided_lower_bound":5990.0762} | {"lower_bound_strictly_positive":true,"minimum_regret_reduction":411.1189152356} |
| TRUE_EFFECT_STATIC_LOAD_RULE_DECISION_VALUE | ACCEPTED | COPILOT_SUPERIORITY_GATE_PASSED | sha256:3deb24ab896ae158ab70f72c89e5f7a49349c8c06c4f79628fe87d0568384def | {"mean_regret_reduction":3725.0076654061,"one_sided_lower_bound":3720.8596545285} | {"lower_bound_strictly_positive":true,"minimum_regret_reduction":411.1189152356} |
| NULL_EFFECT_NO_SUPPORTED_DRIVER | ACCEPTED | NULL_EFFECT_REJECTION_GATE_PASSED | sha256:48b558f7c0e58ea6a893ad2d617ee3916ab4a6b09aebd2886e24f29cfafb84f7 | {"driver_recommendation_rate":0.0,"supported_rate":0.02} | {"driver_recommendation_rate_max":0.0,"supported_rate_max":0.05} |
| PLANTED_CORRELATE_REJECTION | ACCEPTED | PLANTED_CORRELATE_REJECTION_GATE_PASSED | sha256:63e94ff23a5d603536a9756ce3bcddd32db0dbf74e0ab3917af7eda026092b98 | {"copilot_driver_recommendation_rate":0.0,"correlation_only_action_rate":1.0} | {"copilot_driver_recommendation_rate_max":0.0,"correlation_only_action_rate_min":0.9} |
| PLANTED_CORRELATE_PREDICTION_ONLY_DECISION_VALUE | ACCEPTED | COPILOT_SUPERIORITY_GATE_PASSED | sha256:63e94ff23a5d603536a9756ce3bcddd32db0dbf74e0ab3917af7eda026092b98 | {"mean_regret_reduction":3905.3865,"one_sided_lower_bound":3903.772125} | {"lower_bound_strictly_positive":true,"minimum_regret_reduction":0.0} |
| PLANTED_CORRELATE_CORRELATION_ONLY_DECISION_VALUE | ACCEPTED | COPILOT_SUPERIORITY_GATE_PASSED | sha256:63e94ff23a5d603536a9756ce3bcddd32db0dbf74e0ab3917af7eda026092b98 | {"mean_regret_reduction":7030.1,"one_sided_lower_bound":7030.1} | {"lower_bound_strictly_positive":true,"minimum_regret_reduction":0.0} |
| PLANTED_CORRELATE_ALWAYS_EXPEDITE_DECISION_VALUE | ACCEPTED | COPILOT_SUPERIORITY_GATE_PASSED | sha256:63e94ff23a5d603536a9756ce3bcddd32db0dbf74e0ab3917af7eda026092b98 | {"mean_regret_reduction":7030.1,"one_sided_lower_bound":7030.1} | {"lower_bound_strictly_positive":true,"minimum_regret_reduction":0.0} |
| HIDDEN_CONFOUNDING_REJECTION | ACCEPTED | HIDDEN_CONFOUNDING_REJECTION_GATE_PASSED | sha256:7af28382ab10155780007a7813dc5e61e946ee7b09a2084ce3eaed938ac19fbf | {"driver_recommendation_rate":0.0,"supported_rate":0.0,"weak_association_only_rate":1.0} | {"driver_recommendation_rate_max":0.0,"supported_rate_max":0.0,"weak_association_only_rate_min":0.95} |
| POOR_OVERLAP_ABSTENTION | ACCEPTED | POOR_OVERLAP_ABSTENTION_GATE_PASSED | sha256:e3d987851b963649be599bb372dba0c050d9c6d1c3af44486884bf88e2e730aa | {"abstention_precision":1.0} | {"abstention_precision_min":0.95} |
| OLIST_ADAPTER_TRANSPORT_TIMING_VALIDATION | ACCEPTED | OLIST_TRANSPORT_TIMING_BOUNDARY_VERIFIED | sha256:ccd9eb87387990abd90d13ea967dc62dc801c842835bf2cd2699c43e9e05fdb7 | {"adapter_id":"olist-public-validation-adapter","adapter_version":"1.0.0","claim_scope":"adapter_transport_timing_validation","construction_causal_claim_permitted":false,"dataset_key":"olist-validation","decision_support_evaluation_permitted":false,"intended_role":"out_of_domain_validation","mapping_manifest_id":"olist-validation.mapping.v1","source_kind":"olist","transport_timing":{"assumed_timezone":"America/Sao_Paulo","committed":"order_purchase_timestamp","promise_known_at":"committed","promised":"shipping_limit_date","reached":"order_delivered_carrier_date"}} | {"claim_scope":"adapter_transport_timing_validation","construction_causal_claim_permitted":false,"decision_support_evaluation_permitted":false,"intended_role":"out_of_domain_validation"} |
| SCMS_REJECTION_ABSTENTION | ACCEPTED | SCMS_REJECTION_ABSTENTION_BOUNDARY_VERIFIED | sha256:e9cfeda6fa099f28fae85eabf6375fc0f927982625e70321289e87686f11e4f8 | {"adapter_id":"scms-rejection-vignette-adapter","adapter_version":"1.0.0","claim_scope":"rejection_abstention","construction_causal_claim_permitted":false,"dataset_key":"scms-rejection-vignette","decision_support_evaluation_permitted":false,"intended_role":"rejection_vignette","mapping_manifest_id":"scms-rejection-vignette.mapping.v1","rejection_mapping":{"delivered_to_client":"Delivered to Client Date","delivery_recorded":"Delivery Recorded Date","missingness_tokens":{"Date Not Captured":"unknown","N/A - From RDC":"not_applicable"},"po_sent_to_vendor":"PO Sent to Vendor Date","promise_known_at":"unknown","scheduled_delivery":"Scheduled Delivery Date"},"source_kind":"scms"} | {"claim_scope":"rejection_abstention","construction_causal_claim_permitted":false,"decision_support_evaluation_permitted":false,"intended_role":"rejection_vignette"} |
| SYNTHETIC_APPROVAL_FIXTURE_BOUNDARY | ACCEPTED | SYNTHETIC_APPROVAL_FIXTURES_EXCLUDED | sha256:ca9944139b1434640e082ca1be9d67d97833e8a9830bcdde28412a16c21ebf97 | {"approval_scope":"SYNTHETIC_CONFORMANCE_ONLY","domain_validation_claim":false,"external_evaluation_claim":false,"id_prefix":"synthetic:core-decision-support-v1:","intended_role":"synthetic_conformance","labels":["SYNTHETIC","TEST_ONLY","NO_PRACTITIONER_VALIDATION","NOT_SHIPPED"],"namespace":"synthetic://core-decision-support/v1","shipped_demo_claim":false,"source_kind":"synthetic_conformance","state":"TEST_ONLY_NOT_SHIPPED"} | {"domain_validation_claim":false,"shipped_demo_claim":false,"state":"TEST_ONLY_NOT_SHIPPED"} |
| EVALUATION_RUNTIME_COMPATIBILITY | ACCEPTED | EVALUATION_RUNTIME_MATCHED | sha256:ca9944139b1434640e082ca1be9d67d97833e8a9830bcdde28412a16c21ebf97 | {"observed":{"doubleml":"0.11.3","dowhy":"0.14","evaluation_runtime":"stdlib-deterministic-v1","numpy":"2.2.6","python":"3.12.13","scikit_learn":"1.6.1","scipy":"1.15.3","thread_policy":"single_process_single_threaded_evaluator"}} | {"runtime_lock_hash":"sha256:c2153480af7ef58e4cd4f132831c74235d7689fe731c7be53570feedd918b4f3"} |
| EVALUATION_INTEGRITY | ACCEPTED | EVALUATION_ARTIFACTS_INTEGRITY_VERIFIED | sha256:ca9944139b1434640e082ca1be9d67d97833e8a9830bcdde28412a16c21ebf97 | {"invalid_seed_count":0} | {"invalid_seed_count":0} |
| EVALUATION_REPRODUCIBILITY | ACCEPTED | EVALUATION_REPLAY_MATCHED | sha256:ca9944139b1434640e082ca1be9d67d97833e8a9830bcdde28412a16c21ebf97 | {"mismatches":0,"projection_hash":"sha256:2f331db5dd514e1d668fd194a9bc5af6a4a1fa8853230224b2877a4d731ec9c0"} | {"mismatches":0} |
| EVALUATION_SCOPE_COMPLETENESS | ACCEPTED | FULL_CAMPAIGN_SCOPE_VERIFIED | sha256:ca9944139b1434640e082ca1be9d67d97833e8a9830bcdde28412a16c21ebf97 | {"scenario_count":5,"seed_count":100} | {"scenario_count":5,"seed_count":100} |
| HUMAN_TRUST_AND_COMPREHENSION | UNAVAILABLE | HUMAN_VALIDATION_OUT_OF_SCOPE | none | null | null |
| CONSTRUCTION_CAUSAL_MAGNITUDE | UNAVAILABLE | CONSTRUCTION_MAGNITUDE_VALIDATION_UNAVAILABLE | none | null | null |
| ACTION_REALISM | UNAVAILABLE | ACTION_REALISM_VALIDATION_UNAVAILABLE | none | null | null |
| MANAGER_COMPREHENSION | UNAVAILABLE | MANAGER_COMPREHENSION_VALIDATION_UNAVAILABLE | none | null | null |
| PRACTITIONER_DOMAIN_VALIDATION | UNAVAILABLE | PRACTITIONER_DOMAIN_VALIDATION_UNAVAILABLE | none | null | null |

## Unavailable rationales

- `HUMAN_TRUST_AND_COMPREHENSION`: `HUMAN_VALIDATION_OUT_OF_SCOPE`
- `CONSTRUCTION_CAUSAL_MAGNITUDE`: `CONSTRUCTION_MAGNITUDE_VALIDATION_UNAVAILABLE`
- `ACTION_REALISM`: `ACTION_REALISM_VALIDATION_UNAVAILABLE`
- `MANAGER_COMPREHENSION`: `MANAGER_COMPREHENSION_VALIDATION_UNAVAILABLE`
- `PRACTITIONER_DOMAIN_VALIDATION`: `PRACTITIONER_DOMAIN_VALIDATION_UNAVAILABLE`

## Scenario aggregates

| Scenario | Valid seeds | Invalid seeds | Mean ATTE days | Supported rate | Abstention precision |
| --- | ---: | ---: | ---: | ---: | ---: |
| TRUE_EFFECT | 100 | 0 | 1.4729447695 | 1.0 | UNAVAILABLE |
| NULL_EFFECT | 100 | 0 | -0.0204567074 | 0.02 | UNAVAILABLE |
| PLANTED_CORRELATE | 100 | 0 | 0.0060433396 | 0.0 | UNAVAILABLE |
| HIDDEN_CONFOUNDING | 100 | 0 | 6.4984699372 | 0.0 | UNAVAILABLE |
| POOR_OVERLAP | 100 | 0 | 1.4970163668 | 1.0 | 1.0 |

## Paired policy comparisons

| Scenario | Challenger | Paired seeds | State | Mean regret reduction | One-sided lower bound |
| --- | --- | ---: | --- | ---: | ---: |
| TRUE_EFFECT | PREDICTION_ONLY | 100 | ACCEPTED | 3007.03 | 3005.60145 |
| TRUE_EFFECT | CORRELATION_ONLY | 100 | ACCEPTED | 577.587 | 577.166 |
| TRUE_EFFECT | ALWAYS_EXPEDITE | 100 | ACCEPTED | 5990.487 | 5990.0762 |
| TRUE_EFFECT | STATIC_LOAD_RULE | 100 | ACCEPTED | 3725.0076654061 | 3720.8596545285 |
| TRUE_EFFECT | ORACLE | 100 | REJECTED | 0.0 | 0.0 |
| NULL_EFFECT | PREDICTION_ONLY | 100 | ACCEPTED | 4161.443 | 4160.00855 |
| NULL_EFFECT | CORRELATION_ONLY | 100 | ACCEPTED | 1732.0 | 1732.0 |
| NULL_EFFECT | ALWAYS_EXPEDITE | 100 | ACCEPTED | 7144.9 | 7144.9 |
| NULL_EFFECT | STATIC_LOAD_RULE | 100 | ACCEPTED | 2652.326 | 2649.82075 |
| NULL_EFFECT | ORACLE | 100 | REJECTED | 0.0 | 0.0 |
| PLANTED_CORRELATE | PREDICTION_ONLY | 100 | ACCEPTED | 3905.3865 | 3903.772125 |
| PLANTED_CORRELATE | CORRELATION_ONLY | 100 | ACCEPTED | 7030.1 | 7030.1 |
| PLANTED_CORRELATE | ALWAYS_EXPEDITE | 100 | ACCEPTED | 7030.1 | 7030.1 |
| PLANTED_CORRELATE | STATIC_LOAD_RULE | 100 | ACCEPTED | 2610.004 | 2607.258875 |
| PLANTED_CORRELATE | ORACLE | 100 | REJECTED | 0.0 | 0.0 |
| HIDDEN_CONFOUNDING | PREDICTION_ONLY | 100 | ACCEPTED | 4161.443 | 4160.05935 |
| HIDDEN_CONFOUNDING | CORRELATION_ONLY | 100 | ACCEPTED | 1732.0 | 1732.0 |
| HIDDEN_CONFOUNDING | ALWAYS_EXPEDITE | 100 | ACCEPTED | 7144.9 | 7144.9 |
| HIDDEN_CONFOUNDING | STATIC_LOAD_RULE | 100 | ACCEPTED | 2652.326 | 2649.56965 |
| HIDDEN_CONFOUNDING | ORACLE | 100 | REJECTED | 0.0 | 0.0 |
| POOR_OVERLAP | PREDICTION_ONLY | 100 | ACCEPTED | 3007.03 | 3005.61805 |
| POOR_OVERLAP | CORRELATION_ONLY | 100 | ACCEPTED | 577.587 | 577.15365 |
| POOR_OVERLAP | ALWAYS_EXPEDITE | 100 | ACCEPTED | 5990.487 | 5990.04755 |
| POOR_OVERLAP | STATIC_LOAD_RULE | 100 | ACCEPTED | 3725.0076654061 | 3720.7089834635 |
| POOR_OVERLAP | ORACLE | 100 | REJECTED | 0.0 | 0.0 |

## Boundaries and retention

- Synthetic fixture boundary: `{"approval_scope":"SYNTHETIC_CONFORMANCE_ONLY","domain_validation_claim":false,"external_evaluation_claim":false,"id_prefix":"synthetic:core-decision-support-v1:","intended_role":"synthetic_conformance","labels":["SYNTHETIC","TEST_ONLY","NO_PRACTITIONER_VALIDATION","NOT_SHIPPED"],"namespace":"synthetic://core-decision-support/v1","shipped_demo_claim":false,"source_kind":"synthetic_conformance","state":"TEST_ONLY_NOT_SHIPPED"}`
- Audit reference: `core-evaluation-evidence:sha256:cc5684675c235f9fa81986fa3bc5db9b7b7bb1594815db7b727fd32eaa5ec2cd`
- Audit subject hash: `sha256:45455f3e63a5e2a4e54ec1b9376b4a6375dd3306c620e2e45a6c6946cfb8dacd`
- Retention pin: `core-evaluation-retention:sha256:cc5684675c235f9fa81986fa3bc5db9b7b7bb1594815db7b727fd32eaa5ec2cd`
- Retention state: `PINNED`

This summary is a deterministic projection of the machine-readable manifest and result. Claim state, reason, evidence references, observed facts, thresholds, unavailable rationales, and integrity outcomes are shown as recorded; no state is inferred from narrative copy.
