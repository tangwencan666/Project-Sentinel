# Phase 4 — Runtime reliability and controlled benchmark

Status: Phase 4 implementation and first release evaluation delivered. This document
preserves the work record and unsuccessful interventions. Open Critic context and
benchmark-blinding findings are documented in `phase4-evaluation.md`.

## Historical seal

`evaluation/baselines/manifest.sha256` seals Rule, V1, V2 and V3. The original V1
manifest is unchanged: `a76a705a7d14c8cc7130ddb45d3021bc88e4426ef5821e327e9e9a85f118a5a0`.
The additional aliases preserve the previously declared first-valid pool trial
selection. Original invalid-fixture attempts and all semantic failures remain.
Read-only attributes and SHA256 detect changes; this is not administrator-proof WORM.

Benchmark and ground truth are versioned under
`evaluation/benchmarks/sentinel-benchmark-v1/`. The manifest seals the scenario
registry, grader, business source, immutable pricing tests and database definition.
The Investigator has no tool to read this directory, the registry or the grader.

## V3.1 runtime intervention

The legacy V1/V2/V3 workflows remain available. Default is still V2 until measured
results justify a change. `HYBRID_V3_1` uses the separate `runtime_agent` workflow:

- A typed `InvestigationState` persists hypotheses, errors, critical evidence,
  pending actions, read registry, budgets and provider diagnostics.
- P0/P1 control state is pinned. Context rebuilding removes complete P3/P2 items
  before failing explicitly if required state itself exceeds the context ceiling.
- Tool receipts support replay after tool commit but before checkpoint commit.
  Applying a receipt restores its budget debit exactly once per checkpoint state.
- The hypothesis FSM distinguishes CREATED, UPDATED, SUPPORTED, REJECTED and
  CONFIRMED. Illegal transitions return allowed states in a persisted ToolError.
- Soft convergence preserves detail/citation/hypothesis correction capabilities.
  Submission requirements name the next tool and arguments.
- JSON/schema output has at most two repairs; exact parse/schema feedback is
  retained. Planner exhaustion produces an explicitly marked advisory fallback.
- The third identical failed tool invocation is blocked by a circuit breaker.
  Symbol alternatives come from the actual allowlisted repository AST index.
- Provider diagnostics record finish reason, request ID, actual token usage,
  latency, output length, parse/schema status and error. Only `finish_reason=length`
  establishes confirmed truncation; an output cap alone is only suspicion.

V3.1 deliberately retains the historical evidence packing algorithm to separate
runtime repair from the planned V4 compiler. Detail tool responses bypass that
packing layer. This does **not** claim the historical summaries are lossless.

The main exploration allowance remains 28 tool calls. Added, separately measured
allowances are 8 evidence-completion, 12 correction, 3 submission, 12 total schema
repairs and 10 provider retries; a single structured output has at most two repairs
and a provider request has at most two retries. The total round ceiling is 20
instead of V3's 12. The token ceiling remains 300,000 and output ceiling 2,500.
This is a multi-part runtime intervention, not a one-variable compression ablation.

## Test gate and formal runs

Before any Phase 4 paid-model evaluation, **81 tests passed**, including **32 new
runtime reliability tests**, using actual PostgreSQL, Redis and local HTTP servers.
Synthetic provider boundary fixtures test malformed output and retry protocols;
they are not model accuracy evidence. The exact command/output and tested source
hashes are in `evaluation/phase4/reliability-tests.json`.

The controlled order is pool exhaustion, N+1, cache miss, consumer lag, downstream
timeout, HTTP 500, slow query and retry storm. The operator runner checks measured
fault validity before dispatch. Scenario identifiers and fixture proofs are never
sent to the Investigator. Each scenario receives one formal run; no failed-answer
rerun or prompt tuning can overwrite it. Judge failures are explicitly ungraded.

The V3.1 source archive is `evaluation/phase4/v3.1-framework.zip`; results are written
incrementally to `evaluation/results/v3.1-first-controlled.json` and become read-only
on completion or runner failure. All eight first trials are now complete and frozen:
**workflow 1/8, root accuracy 1/8, service localization 1/8**. Seven terminated with
budget failures (three completion budgets, two message-context ceilings, two
480-second workflow deadlines). The only completed case was code exception; its
candidate passed the real pricing contracts and HTTP replay. Conditional accuracy
is 1/1, a denominator that must always accompany the percentage. Total workflow
usage was 1,122,208 tokens, excluding the evaluator. This is a failed reliability
intervention, not evidence of a successful token optimization.

The first result SHA256 is
`f8c2818edec2c1c521571a09c0193c4e1f50dfc96a5ea724057df09749c768cf`.
Two operator fixture predicates were corrected **before** dispatching their
scenario's first model run. Original failed proofs, interrupted suites and unchanged
trial prefixes remain available; see `preflight-corrections.json`.

## Follow-up runtime qualification

`HYBRID_V3_1_1` is a separately named follow-up, never a replacement first trial.
It adds a Supervisor progress controller, model-input read accounting, exact
message-envelope sizing, complete-span trace detail pages and linked parse
diagnostics. Redaction takes one fresh configuration snapshot per traversal.
The original V3.1 image and source archive remain available for reproduction;
new V3.1 starts and resumes are rejected on the newer runtime to avoid mixing code.

The first follow-up source passed **97 tests** before qualification. A measured
paired checkpoint-redaction profile produced identical redacted data, with median
serialization time 8.78 seconds versus 25 milliseconds and configuration reads
3,425 versus one. This is not a full-workflow speedup claim.

Five qualification scenarios were preregistered in
`evaluation/phase4/runtime-followup-preregistration.json`. They are excluded from
RCA accuracy comparisons and must all complete, including the code-patch regression,
before V4 begins. The retained follow-up history is:

| Runtime revision | Completed workflows | Outcome |
|---|---:|---|
| 3.1.1 | 1 of 2 dispatched, 5 planned | N+1 output and both repairs confirmed truncated; remaining three not dispatched after telemetry failures |
| 3.1.2 | 0/5 | Compact schema avoided truncation, but exposed submission-budget accounting and field-description regressions |
| 3.1.3 | 4/5 | Pool/cache/timeout/code completed, including verified code candidate; N+1 still exceeded a text-field length after both repairs |
| 3.1.4 | 5/5 | Qualified; schema-directed field repair, same budgets and field limits; 117 tests passed before starting; real code candidate tests/replay passed |

These are protocol qualification results, **not** additional scored RCA trials.
`runtime-qualification-report.json` retains every source artifact and interruption.
No numerical budget was raised. A schema-invalid or locally unread submission uses
correction allowance; actual semantic submissions retain a ceiling of three.

The new field-repair module asks the model to replace only the exact overlong string
paths, then validates and merges them with the unchanged original object. It never
truncates a string or rewrites unrelated citations, service or category. A separate
real DeepSeek probe repaired five retained failed outputs on the first attempt,
using 3,120 actual provider tokens in total; this tests protocol repair, not causal
correctness. The initial probe failed at Python import before any model call and is
also retained. See `field-repair-provider-probe-2.json` for real responses and lengths.

## Observability capacity intervention

During the 3.1.1 follow-up, Jaeger used 6.135 GiB of a 7.437 GiB Docker VM and its
search repeatedly exceeded the adapter's 8-second timeout. Its CLI documented that
default in-memory trace retention was unbounded. Load was paused and Jaeger was
recreated with 10,000-trace retention, 640 MiB Go soft memory limit and a 768 MiB
container ceiling. Business service images, scenarios and grading did not change.
Volatile Jaeger history was cleared; PostgreSQL evidence and frozen run artifacts
were preserved. This environment change must accompany later latency comparisons.

Twenty-eight read-only observations during 3.1.2 had zero trace-query failures,
maximum query latency 0.662 seconds and final Jaeger memory 584.8 MiB. This is a
bounded observation window, not a long-duration load/SLO guarantee.

Test and qualification runners now verify application/test/dependency file hashes
inside the test image or running container against the host source before dispatch.

## Final release

V4 compiler/first evaluation, generic multi-service patching, actual crash recovery,
adversarial boundary exercises, diagnostics UX and audits are complete. The independent
V4.1 first release evaluation completed 8/8 workflows, with 7/8 root/service accuracy,
1,461,870 workflow tokens and 78.75-second mean duration on benchmark v2. The final
test gate passed 189 tests; actual browser and live-event checks passed. Retry storm
remains wrong. Critic omitted a root-cited evidence object in that case; this separate
handoff defect remains open, so full end-to-end context reliability is not claimed.
Historical V3 remains 2/8 workflow completion and 1/8 root
accuracy; its token reduction must not be advertised as a successful optimization.
