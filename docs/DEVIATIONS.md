# Execution changes and failures

- The user explicitly requested a public repository, superseding the handout's
  private-repository instruction. The original paper and raw archives stay local.
- 2026-10-16: the initial method-of-steps cross-check failed while bracketing a
  root at an unnecessarily huge beta; the ODE solver overflowed. This is an
  implementation failure, not a theory counterexample. Preserve the failed log
  in `results/theory-extended/FAILED.txt`. Bracketing now starts at alpha and
  doubles. No empirical outcomes informed this correction.
- Public archive acquisition uses paginated unsigned HTTPS and eight concurrent
  downloads, preserving the starter's normalization and explicit cost parser.
  Only `.traj` objects are required in these five archives. Pinned Parquet is read
  directly rather than through the datasets cache. The one-billion-byte guard
  applies separately to each archive's selected trajectory objects.
- Frozen primary protocol includes a 600-second deadline; tuning is corrected to
  use that same deadline and resolutions-by-deadline, instead of eventual value.
- A new split-map regression test initially assumed numeric instance-ID tie order;
  the implementation correctly uses lexicographic tie order as declared. The test
  now checks unchanged group membership. Its failed JUnit report is retained.
- The exact 2025 SWE-agent hash embedded in a trajectory returned HTTP 404.
  API-call proxy semantics were checked against the declared v1.1.0 release
  (commit 0f3acafacabc0def8cc76b4e48acb4b6cf302cb9) and legacy v0.7.0
  (dc18a740faabd2fc625a9b018184dfc4a81cbc78). Both reset per-instance counters.
  This supports a sensitivity proxy, not measured latency or exact source identity.
- In addition to exclusion counts, a common-complete-issue sensitivity retains
  only issue IDs with known costs/outcomes in every archive. Selection uses
  availability, not performance. It is secondary to the original per-submission
  complete-case analysis and cannot correct nonrandom missingness.
- Early Sonnet, GPT-4o and GPT-4 runs test the pipeline. The final all-submission
  run uses a clean committed implementation; repeated results are not independent
  replications. The optional model-identity feature added during early GPT-4
  execution defaults off in single-model runs and changes only switch experiments.
- The Claude 4 archive contains 5,288,247,907 bytes of `.traj` files. The full
  download stopped at the original 1 GB guard; its failure is preserved. Instead,
  a tested adapter reads bounded HTTP suffix ranges (256 KiB, escalating only
  if needed), checks HTTP 206/Content-Range/ETag, structurally parses the complete
  root `info` object, and records range SHA256 plus extraction SHA256. The parser
  matches the complete smoke trajectory's model statistics exactly. Full-object
  SHA256 is explicitly unavailable for these range-acquired objects. This is a
  metadata acquisition change, not outcome imputation or a raised byte limit.
- Published per-record numerical measurements include issue character counts.
  Feature-equivalence tests confirm these produce exactly the same predictions
  as raw issue text. The final campaign runs from this text-free representation
  so it is reproducible offline without redistributing benchmark issue text.
- The app's first PDF-preview compilation timed out while downloading TeX support
  files. The same standalone source compiled successfully with Tectonic 0.17.0.
  The exported 10-page PDF was rendered and visually checked; a long source hash
  line was repaired before release. The original PDF is preserved unchanged.
