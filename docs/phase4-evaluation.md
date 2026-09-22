# Phase 4 evaluation

Original Rule/V1/V2/V3 files and first V3.1/V4 results remain immutable. The UI reads
`evaluation/phase4/comparison.json`, without rewriting the phase-three comparison.

| Version | Workflow | Root / service | Conditional root | Workflow tokens | Mean seconds |
|---|---:|---:|---:|---:|---:|
| Rule | 8/8 | 7/8 · 8/8 | 7/8 | 0 | 11.62 |
| V1 | 8/8 | 5/8 · 5/8 | 5/8 | 1,261,196 | 68.14 |
| V2 | 8/8 | 6/8 · 6/8 | 6/8 | 1,531,642 | 123.47 |
| V3 | 2/8 | 1/8 · 1/8 | 1/2 | 896,380 | 87.31 |
| V3.1 first | 1/8 | 1/8 · 1/8 | 1/1 | 1,122,208 | 248.98 |
| V4 first | 7/8 | 5/8 · 5/8 | 5/7 | 1,296,540 | 70.19 |

Conditional accuracy uses completed workflows. V3.1's 100% conditional accuracy has
denominator **one**, not eight. V3's low use includes six failed workflows. Rule uses
benchmark-domain predicates; zero LLM tokens do not establish general intelligence.
Useful tool rate is a shared duplicate-query heuristic, not human semantic annotation.

V4's pool and N+1 trials were both confounded by an unrelated failed notification
consumer after Docker restart. Pool was graded correct; N+1 diagnosed the unrelated
consumer failure and was incorrect for the injected target. Both original scores and
confound labels are retained. V4 is excluded from Pareto ranking. Its unconfounded
six-case subset is 4/6 root and 5/6 workflow, not a replacement eight-case benchmark.

Eligible historical versions put Rule on the four-coordinate frontier (accuracy,
tokens, latency, workflow). AI-only includes V1/V2/V3, but V3 benefits numerically from
early failure. Requiring eight completed workflows leaves V1/V2. This is descriptive,
not a statistical significance or production reliability claim.

## Qualification is separate

V3.1 first failed seven workflows under context/tool/time ceilings. Follow-up failures
remain in `evaluation/phase4/`: 3.1.1 exposed truncation and observability capacity;
3.1.2 exposed schema/submission budget coupling; 3.1.3 completed 4/5; 3.1.4 completed
5/5 after bounded field repair. Qualification gated V4, but never replaces first 1/8.

The H recovery exercise also preserves its failed first workflow and successful
same-run follow-up separately. Four component patches and four injection probes are
component/security exercises, never additional RCA successes.

## Final Runtime V4.1 / sentinel-benchmark-v2

The first eight formal release dispatches completed: **workflow 8/8, root 7/8,
service 7/8**, conditional root 7/8. No wrong answer was rerun. The first result is
`evaluation/results/v4.1-first-controlled.json`; its SHA256 is
`74b48f0cc7a3f341ca0a088a50054fa0c45209034d12aa4f5de46a4f1fa2c81a`.

| Scenario | Workflow | Root / service | Tokens | Seconds |
|---|---:|---:|---:|---:|
| Pool exhaustion | Completed | Correct / correct | 164,052 | 74.81 |
| N+1 | Completed | Correct / correct | 169,266 | 87.14 |
| Cache miss | Completed | Correct / correct | 206,391 | 84.11 |
| Consumer lag | Completed | Correct / correct | 160,136 | 79.57 |
| Downstream timeout | Completed | Correct / correct | 222,508 | 88.47 |
| Code exception | Completed | Correct / correct | 185,668 | 53.67 |
| Slow query | Completed | Correct / correct | 206,971 | 85.34 |
| Retry storm | Completed | **Incorrect / incorrect** | 146,878 | 76.87 |

Actual workflow use: **106 model calls, 284 tool calls, 1,422,496 input + 39,374
output = 1,461,870 tokens**, mean 78.75 seconds. Including Evaluator: 1,592,980
tokens. Prices remain unknown. Useful tools by the existing heuristic: 207/284
(72.89%); redundant 47, failed 30. The failed tools comprise 11 symbol misses,
13 overlong fields, five unresolved contradictions and one invalid state transition.

Diagnostic counts: invalid JSON 0, schema failures 15 (including structured-output
diagnostics), protocol failures 0, budget failures 0, identical repeated failed calls
0, tool-not-offered 0, unread citations 0. Schema/tool errors are events within
completed workflows, not 15 failed workflows. All 106 provider finish reasons were
`stop` or `tool_calls`; no confirmed output truncation occurred in this suite.

All eight Critic verdicts were **PARTIALLY_VERIFIED**. VERIFIED count is zero;
false accepts are zero but the rate conditional on VERIFIED is undefined. This
does not demonstrate eight fully verified causal explanations or repairs.

The pricing candidate passed nine immutable tests (baseline: two failed/seven
passed). Eight fault-input requests across actual order/payment/inventory processes
changed from 100% HTTP 500/business-contract violations to 0%, with healthy control,
database rows and Kafka event verified. One eligible patch, one successful candidate;
HIGH financial risk, no production deployment. Its P95 increased from 55.83 to
98.68 ms because successful work includes database/payment operations; do not market
that as a latency improvement. Other recovery windows are operator fault removal.

## Retained release failure and open findings

Retry storm is a **reasoning failure**, not a workflow/budget/JSON failure. The model
observed approximately 4.9x payment calls but selected payment fast-fail 503s as the
origin and treated order retries as secondary. It inferred a Redis fault flag without
reading that key. The benchmark target is five immediate order-service retries
without backoff. Root and service scores both remain incorrect.

Post-run inspection also confirmed a Critic context defect: root-cited code evidence
`E-38d10b8ede804ec3` was actually read by Investigator but dropped from the independent
Critic packet with `whole_object_exceeds_remaining_budget`. Consequently Critic
reported that source as unsupplied. Investigator state/read registry remained intact;
this is a separate Critic handoff omission, still open in the frozen release. A future
version needs guaranteed root-citation delivery and explicit detail/overflow handling.

The same evidence exposes the generic `runtime.fault()` helper, though the scenario
registry, truth and evaluator remain inaccessible. Thus the benchmark is not fully
blind to experiment implementation. Separating that plumbing requires a new version,
not retroactive changes to this result. See `release-failure-analysis.json` and the
adversarial audit. No current claim of complete context reliability is made.

This cohort retains ground truth and scorer but changes business extraction, readiness,
public-response replay, semantic correction, readable code and the generic sandbox.
It is neither a pure compression ablation nor a statistically paired improvement over
earlier deployment. Runtime, model, budgets and business hashes stay frozen across the
eight dispatches. Duration covers full workflow work; provider totals exclude Evaluator.
Missing prices stay unknown. The final cohort is not added to the historical Pareto
frontier. Its observed improvement in completion is not a controlled single-variable
claim about compression, prompt changes, or token efficiency.

Original hashes: V3.1 `f8c2818edec2c1c521571a09c0193c4e1f50dfc96a5ea724057df09749c768cf`;
V4 `454f2181cdb6a26111bc1b3c49e2259da5c76a1910dc1dc342a935d330658faa`.
