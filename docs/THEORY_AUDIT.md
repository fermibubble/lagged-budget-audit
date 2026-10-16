# Theory audit

No numerical violations were found in 9,000 randomized instances and 2,500
adaptive local-search instances. This is finite falsification-oriented evidence,
not a proof or universal verification. Random seeds and complete nearest/violating
instances are saved; the violation lists are empty.

- 45 independent method-of-steps/root checks: maximum relative beta error
  `8.563055632344696e-11` against the finite-series implementation.
- Tables 5 and 6: analytic values reproduced to the reported three decimals.
  The two Table-6 integration grids differ by at most `3.366455239017796e-06`.
- 120 endpoint convergence cases at 100, 400, 1600, 4000 and 16000 units.
  Finite sizes include the admitted job in delta; the target is asymptotic.
- 500 additional exact DP versus brute-force oracle comparisons.
- 108 band checks inside the stated band-width conditions; zero violations.
- Empty, all-refused, zero-actual-cost and deadline/refund edge cases are unit
  tests. Finite gamma is explicitly unavailable at zero actual cost.

## Coarse-item correction

Nine size-0.1 low-density jobs leave exactly 0.1 room. One high-density job fits,
producing ratio **5.666996845** at L=1, U=100. Add an explicit size-0.001 filler
at its admission threshold and the ratio becomes **12.981749433**, above the
small-item comparator 9.817892025 but below the valid instance certificate
16.813164423. The original literal construction does not specify this filler.
The corrected construction exceeds that comparator in all nine declared
ratio/size settings; both literal and corrected results are preserved.

## Asymptotic wording

At delta=1/2 and R=U/L>2, the endpoint equation is `(beta+2)^2/8=R`, hence
`beta=sqrt(8R)-2`. ZCL has `B(1/2) ~ alpha*sqrt(eR)`, so its improvement ratio
against the lag-optimal threshold grows like `alpha*sqrt(e/8)`. Therefore a
uniform constant-factor claim is false as R grows. The roughly 2.04 factor on
the paper's finite R<=1000, delta<=0.3 range remains a finite-range observation.
This does not refute the separate lower-bound inequality in Proposition 3.7.

## Evidence

[Initial campaign](../results/theory-initial),
[independent solver and extended campaigns](../results/theory-extended-002),
[adaptive search and band checks](../results/theory-search), and
[coarse grid](../results/theory-coarse-grid).
The initial independent DDE run failed from an excessive root bracket; its log
is retained in [the failed attempt](../results/theory-extended/FAILED.txt).
Universal threshold optimality and the blind-worker lower bound are not proved
by these experiments. No empirical replay receives a realized-value certificate.
