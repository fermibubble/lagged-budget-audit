# Results

The final single-submission campaign runs **107,160 policy/block episodes** from
**2,398 usable recorded trajectories**, with zero run failures. It is recorded-trace
replay, not live agent execution. There are eight evaluated chronological blocks
per submission, one shared 500-issue benchmark, and extensive issue reuse.

## Primary endpoint: resolutions completed by the deadline

Each configuration has a $24 block budget, $6 reservation, 16 worker slots,
expected-cost density, frozen warm-up predictors, the paper queue, fixed 60-second
durations and a 600-second deadline. Actual occupancy peaks at four.

| Configuration | Cap | Settled ZCL | Committed ZCL | Expected-in-flight ZCL | Structural lag-aware |
|---|---:|---:|---:|---:|---:|
| Claude 3.5 Sonnet | 3.500 | 2.750 | 1.500 | 2.500 | 2.750 |
| GPT-4o | 1.375 | 1.750 | 2.000 | 1.750 | 2.375 |
| GPT-4 | 1.250 | 1.000 | 0.625 | 1.000 | 1.125 |
| Claude 3 Opus | 1.250 | 1.625 | 0.625 | 1.625 | 1.125 |
| Claude 4 Sonnet | 9.500 | 9.875 | 2.625 | 10.125 | 10.250 |
| Equal mean across configurations | **3.375** | **3.400** | **1.475** | **3.400** | **3.525** |

The predeclared paired differences, averaging configurations within each common
block before resampling, are:

| Contrast | Mean difference | Descriptive 95% block interval |
|---|---:|---:|
| Lag-aware minus committed ZCL | +2.050 | [+1.850, +2.250] |
| Lag-aware minus settled ZCL | +0.125 | [-0.075, +0.325] |
| Lag-aware minus expected-in-flight ZCL | +0.125 | [-0.025, +0.275] |
| Committed ZCL minus cap | -1.900 | [-2.300, -1.600] |

These use moving-block length 2 and 5,000 resamples. Lengths 1 and 4, per-submission
results, relative differences, and every sensitivity comparison are in
[paired_comparisons.csv](../results/summary/paired_comparisons.csv). They are
conditional descriptive intervals with eight dependent blocks, not multiplicity-
adjusted significance or population guarantees.

## Queue, missingness, pooling and switches

Rechecking prices after refunds raises committed ZCL from 1.475 to **3.375** at
the same primary parameters. Lag-aware stays at 3.525. Under strict room-first
rejection, all rules perform poorly. The queue substantially changes the apparent
increment from the new threshold. [Queue table](../results/summary/queue_sensitivity.csv).

On the **409 common-complete issues**, lag-aware averages **3.375**, versus **3.450**
for expected-in-flight ZCL and **3.375** for the cap. Availability sensitivity
reverses the close lag-aware/expected-in-flight ranking; it does not cure nonrandom
missingness. [Common-case table](../results/summary/common_sensitivity.csv).

Pooling: **648 episodes**, with one shared worker pool. At 16 workers and the paper
queue, shared lag-aware yields **33.250 independent successful runs** and **28.375
unique issues** per block; shared cap gives 16.125 runs and 7.500 unique issues.
Shared committed and expected-in-flight ZCL yield 25.000 and 27.875 runs. Static
private allocations and every queue/worker cell are also reported. This is a
modified forward/common-issue protocol, not the original circular rotations.
[Pooling table](../results/summary/pooling.csv).

Switching: **60 scenarios / 1,920 policy-block episodes**. On the block after the
switch, banded previous-day pricing averages **2.117**, unbanded **1.700**, and
committed ZCL **2.050**. This uses privileged full-archive feedback and overlapping
scenarios; no independent-sample inference is claimed.
[Switch table](../results/summary/switches.csv).

## Diagnostics and limits

- All **9,930,622** saved event records satisfy the budget/ledger checks. Training
  provenance matches frozen, admitted-only or full-archive semantics in every episode.
- Largest observed occupancy is **16** across the single-submission grid despite
  nominal limits through 64; it is **4** in primary. Pooling has its own diagnostics.
- No structural design-delta exceedances. **102,139** episodes have predicted-density
  excursions outside warm-up percentiles. No empirical theorem certificates apply.
- Predictions, Brier/AUC, cost error, utilization, rejection reasons and late
  completions are retained in the episode table. Late-running jobs are charged.
- No new model executions, paid triage calls, external benchmark holdout or formal
  proof verification. The original 58% triage headline is unverified and removed.

[Full final run](../results/final-campaign), [source audit](DATA_AUDIT.md),
[claim audit](CLAIM_AUDIT.md), [theory audit](THEORY_AUDIT.md), and
[execution deviations](DEVIATIONS.md) distinguish what was implemented, tested,
run on recorded traces, changed from the source protocol, and left unverified.
