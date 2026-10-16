# Claim-by-claim audit

Statuses refer to the tested settings. Modified protocols do not exactly replicate
or refute the original empirical protocol. All links lead to executed evidence.

| Claim or question | Status | Evidence and limit |
|---|---|---|
| Instance/reservation bounds, known values and valid density bounds | Supported in tested setting | [11,500 instances](THEORY_AUDIT.md); no numerical violations. Not a proof. |
| Tables 5–6 analytic threshold values | Supported in tested setting | [Independent DDE and tables](../results/theory-extended-002); 45 independent numerical comparisons. |
| Literal size-0.1 coarse construction yields 12.98 | Weakened; construction corrected | [Coarse grid](../results/theory-coarse-grid): literal ratio 5.667; explicit filler yields 12.982. |
| Reshaping helps by a universal constant factor | Contradicted as a general asymptotic statement | [Half-delay identity](../results/theory-extended-002/half_delay.csv) and derivation in revised paper. Finite-range 2.04 wording remains appropriate. |
| Blind-worker universal lower bound / threshold optimality proof | Not tested as a formal proof | Numerical checks do not establish these universal mathematical statements. |
| Exact budget enforcement in simulation | Supported in tested setting | [9,930,622 event checks](../results/ledger_validation.json); actual costs all below fixed reservations. Not a distributed enforcement test. |
| Novel threshold adds value beyond existing rules | Mixed / weakened | [Primary comparisons](../results/summary/paired_comparisons.csv): +2.050 vs committed ZCL, but +0.125 vs expected-in-flight ZCL with interval including zero. Common-case lag-aware is 0.075 below expected-in-flight. |
| Committed pricing's collapse is entirely a price-formula effect | Weakened | [Queue sensitivity](../results/summary/queue_sensitivity.csv): price rechecking raises its mean from 1.475 to 3.375 at the same primary parameters. |
| High nominal worker counts demonstrate high actual occupancy | Weakened | [Episode records](../results/final-campaign): worker limit 64; actual peak at most 16 in single-submission grid, four in primary. |
| Pooling improves value-aware allocation | Supported in tested setting | [Pooling](../results/summary/pooling.csv): at paper queue/16 workers, shared lag 33.250 independent successes vs shared cap 16.125; unique issues 28.375 vs 7.500. Different workload from original rotations. |
| Original pooling doubles unique resolved issues / exact Table 2 values | Inconclusive as replication | Modified common-issue forward protocol; independent successes and unique issues separately reported. No exact reproduction claimed. |
| Band protects a previous-day price after a model switch | Supported narrowly | [60 scenarios](../results/summary/switches.csv): next-block band 2.117 vs fixed 1.700 and committed ZCL 2.050. Full-archive feedback is privileged; scenario reuse limits inference. |
| Difficulty-free prediction | Supported for this implementation | Both predictors allow only repository/issue length, plus known model identity in switch experiments. [Tests](../tests/test_campaign.py). Original authors' implementation was not supplied. |
| Rejected outcomes never enter admitted-only learning | Supported for this implementation | [Ledger validation](../results/ledger_validation.json) checks exact available training IDs for every episode; future-label mutation tests pass. |
| Warm-up and past outcomes are free in deployment | Not claimed | Free historical archive explicitly assumed; acquisition costs in [data audit](../results/data-audit/summary.csv). |
| 58% net-budget benefit from LLM triage | Not tested | No cached triage data or paid calls. Headline removed, not presented as a new result. |
| Empirical outcomes inherit the competitive guarantee | Not applicable | Zero-valued failures, predicted costs/values, percentile bounds and queue changes violate premises. All empirical certificate flags are false. |
| Same archives form independent data | Not claimed | One benchmark, same issues as source manuscript. Independent implementation only. |
