# Prospective audit protocol, version 1

Frozen 2026-10-16 before downloading trace outcomes or running held-out replay.
This is prospective only for this audit; the supplied manuscript and starter
were inspected beforehand. Git commit history is the timestamped protocol record.

## Inputs and status

- Source manuscript SHA256: d035220749caa192a16ccf7560abe772761935e851a61bc038f4e91efb32f6cd.
- Starter ZIP SHA256: 9980894f497a1a2a8a8e2530fe60508d43faae3129d65b4c707f10d763f7ab81.
- Public SWE-bench experiments revision: 40f164d5b8f1d249bf95a6df8b74b577fd8e519d.
- SWE-bench Verified dataset revision will be resolved once and pinned in source locks.
- Submissions: 20240620_sweagent_claude3.5sonnet, 20240728_sweagent_gpt4o,
  20240402_sweagent_gpt4, 20240402_sweagent_claude3opus,
  20250522_sweagent_claude-4-sonnet-20250514.
- This uses the paper's public archives: independent implementation, not independent data.

## Theory

Run the supplied 3,000-instance campaign at seed 20261014 unchanged, then
3,000 instances each at seeds 20261015 and 20261016. Independently solve the
delay differential equation by numerical method of steps, never by calling the
finite series. Recompute Tables 5 and 6, grid convergence at 100, 400, 1600,
4000 and 16000 units, literal and filler-corrected coarse examples, zero lag,
endpoint, monotonicity, half-delay identity, and ratios through 1e6 (larger ratios
for the half-delay asymptotic check). Validate integer DP against brute force.
Search locally around near-tight generated examples and retain reproductions
of every violation. Test refunds, zero actual costs, empty/all-refused cases,
and band assumptions. Passing numerical checks is not formal proof verification.

## Data and exclusions

Use only per-instance billed cost from explicit verified adapters; never use
cumulative cost. Hash every downloaded object. Do not execute downloaded code.
Audit missing traces, unknown official outcomes, zero costs, duplicate attempts,
and schemas. A first-file adapter smoke test is not held-out evidence. Any
incomplete archive is a labeled complete-case analysis, with exclusion counts
and pessimistic/optimistic missing-success bounds. No imputed costs or outcomes.
Preserve immutable source locks and a common 500-issue split map across agents.
Order all 500 issues by (PR-created timestamp, instance ID), ten blocks of 50.
Missing records are omitted inside their assigned block, never re-partitioned.
Blocks 0-1 are free historical calibration; blocks 2-9 are eight evaluated blocks.
No circular rotations, cross-agent outcome features, or future labels.

## Primary comparison

Primary setting: each available submission separately, reservation $6 per job,
budget $24 per block, 16 workers, paper queue, expected-cost density, fixed
60-second durations, all arrivals at zero, 600-second admission/completion
deadline, predictors frozen after warm-up. Primary endpoint: resolutions by
deadline; late admitted work is still charged. Primary contrasts: structural
lag-aware minus committed ZCL, structural lag-aware minus settled ZCL,
structural lag-aware minus expected-in-flight ZCL, and committed ZCL minus cap.
Report each submission separately; a cross-submission mean is descriptive and
not five independent datasets. Also report eventual resolutions, cost, utilization,
cost per resolution (undefined at zero), observed peak occupancy, delta, rejection
and late-completion counts, density excursions, calibration and cost error.

Reservations $6 and $12 and budgets $24 and $96 are external fixed stress-test
choices made before trace inspection; they are not fitted to held-out maxima.
If any trace exceeds a chosen reservation, mark that run invalid, preserve the
failure, and do not silently clip/drop or enlarge the reservation. These amounts
are simulation assumptions, not validated production upper bounds. The grid
crosses occupancy capacities 2, 4, 8 and 16; nominal worker caps up to 64 are
reported alongside observed concurrency. A 50-job block cannot reach 64 workers.

## Predeclared sensitivity and extensions

Single-submission factorial: reservations {6,12}, budgets {24,96}, workers
{1,4,16,64}, queues {strict,paper,defer}, feedback {frozen_warmup,admitted_only},
density {reservation,expected}; fixed 60-second duration, 600-second deadline.
Policies: cap, settled/committed/expected-in-flight ZCL, structural lag-aware,
own-previous-block lag-aware, warm-up fixed/banded, history-adaptive fixed/banded.
History-adaptive forecasts train/tune only on their own available past data
using an inner forward split; they are distinct from the paper's previous-day rule.
Initial tuning must use the same deadline and primary endpoint as evaluation.
Full-archive feedback, previous-settled-ZCL lag and previous-day price tuning
are separate privileged-information sensitivities, never called deployable.
Timing sensitivities: fixed durations with no deadline; API-call proxy at
8 seconds/call with 600 and 3600-second deadlines; timestamp-scaled arrivals
over 3600 seconds with a common 3600-second deadline. API call semantics must
be verified against the submitting SWE-agent implementation before use.

After single-submission validation, pool all five configurations using the same
forward block and common issue grouping, with budget $120, reservation $6,
workers {1,16,64}, fixed 60-second duration, 600-second deadline, and all queues.
Use frozen warm-up predictors separately per agent. Compare shared cap and
shared ZCL/lag-aware against equal private budgets and historical static
allocation proportional to warm-up resolutions per dollar (with 10% equal
allocation floor). Independent run successes are the additive primary value;
report unique resolved issues separately because agents share issues. This
modified pooling protocol does not reproduce the paper's circular rotations.

Model-switch sensitivity: all 20 ordered pairs and switch blocks {3,5,7},
budget $24, reservation $6, one worker, paper queue, fixed 60-second durations,
600-second deadline, full-archive feedback explicitly labeled. Fit on prior
blocks with a model-identity indicator and cold-start coefficient zero. Evaluate
before/switch/after blocks and retain all scenarios; no selection by test
cost-effectiveness. Do not claim replication of the original switching protocol.

LLM triage is not run: no cached features or paid-call authorization supplied.
Consequently the original 58% headline is unverified and must not be retained
as an established result in the revised manuscript.

## Estimation, uncertainty and applicability

Success logistic regression and cost ridge use only repository and log issue
length. Vocabularies, cost clipping, density percentiles and tuning use warm-up
or legitimately observed history. Warm-up labels/costs are free historical data;
report their acquisition cost, but make no learning-from-scratch claim.
Admitted-only updates occur after draining the previous block's work; blocks
are separate episodes, not continuous days with pending cross-day outcomes.
Record every training ID and decision event locally and publish compact outputs.
Primary paired differences use the same eight blocks, circular moving-block
bootstrap lengths 1,2,4 and 5000 resamples, seed 20261014. These are conditional,
descriptive intervals, not population inference, significance, or multiplicity
correction. Publish all declared cells and failures, not only winners.
The cost oracle maximizes unit successes at original cost precision; it ignores
reservation, duration and deadline constraints and is a relaxed upper bound.
No theoretical certificate applies to realized binary rewards with failures,
estimated costs and percentile bounds. Keep theorem tests in a separate track.

## Changes and completion

Record any adapter/design correction before the affected experiment in
`docs/DEVIATIONS.md`; do not call later changes preregistered. Publish code,
locked dependencies, CI, source hashes, split map, run manifests, compact results,
claim audit and revised paper. Unrun or infeasible extensions remain explicitly
unverified; no partial campaign validates the whole manuscript.
