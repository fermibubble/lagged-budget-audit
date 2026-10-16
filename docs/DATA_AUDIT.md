# Data audit

The official archives contain 2,404 trajectories across five submissions and 500
shared SWE-bench Verified issues. Normalization retains 2,398 records: six
`no_logs` records have unknown outcomes. Ninety-six trajectories are missing;
12 missing Claude 3 Opus trajectories are officially resolved. Missing costs
are not filled with zero. All 2,398 retained actual costs are positive and below
the predeclared $6 reservation; this does not establish a production cost bound.

| Submission | Trajectories | Retained | Missing | Unknown outcome | Retained successes |
|---|---:|---:|---:|---:|---:|
| Claude 3.5 Sonnet | 500 | 497 | 0 | 3 | 168 |
| GPT-4o | 465 | 462 | 35 | 3 | 116 |
| GPT-4 | 496 | 496 | 4 | 0 | 112 |
| Claude 3 Opus | 443 | 443 | 57 | 0 | 67 |
| Claude 4 Sonnet | 500 | 500 | 0 | 0 | 333 |

The pinned source versions, object URLs, file/range hashes, exclusions, costs and
outcomes are under [results/data-audit](../results/data-audit). Public measurements
exclude issue text, patches, hints and difficulty. Issue character count is
sufficient for the permitted feature. A regression test checks exact predictive
feature equivalence with the raw text.

## Acquisition and source identity

GitHub experiments revision: `40f164d5b8f1d249bf95a6df8b74b577fd8e519d`.
Dataset revision: `c104f840cc67f8b6eec6f759ebc8b2693d585d4a`.
The four legacy archives are downloaded in full with per-file SHA256. The newer
archive's 500 trajectories total 5,288,247,907 bytes; the 1 GB guard stopped that
full download. The suffix-range adapter retrieves only complete root `info`
metadata, verifies HTTP 206, Content-Range and ETag, and records range and
extraction hashes. Its cost/call statistics match the full smoke sample exactly.
Full trajectory SHA256 is unavailable for range-only acquisition and is not
invented. A transient read timeout was preserved and resumed from verified cache.

The cost schema is `info.model_stats.instance_cost`. Cumulative `total_cost`
differs from the per-instance figure in most legacy trajectories and is never
used. API calls track per-instance model usage in the inspected legacy and 1.1.0
source versions. Legacy call counts differ from trajectory step counts by -1 to
3, as recorded in [schema_validation.json](../results/data-audit/schema_validation.json).
Exact submitting source identity is unavailable for the legacy archives, and
one embedded 2025 code hash returned 404. Thus call counts are used only as a
sensitivity proxy: eight seconds per call, with a minimum one-call time unit.
They are not measured model latency or environment runtime.

## Missingness and redistribution

The fixed split map uses all 500 issues; exclusions cannot shift split boundaries.
An additional common-complete-issue sensitivity uses availability across all five
submissions. Counts and raw success envelopes are published; these envelopes do
not bound policy effects because missing costs can change queue decisions.
Complete-case and common-case results can both be biased by nonrandom missingness.

The dataset card and archive metadata were inspected. No blanket redistribution
license for all trajectory/issue content was established. Accordingly raw source
content, the original manuscript, model patches and issue text remain local.
The repository publishes derived numerical facts, source identifiers and hashes.
No open-source license is chosen on the user's behalf.
