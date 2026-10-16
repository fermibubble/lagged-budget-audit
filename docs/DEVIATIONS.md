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
