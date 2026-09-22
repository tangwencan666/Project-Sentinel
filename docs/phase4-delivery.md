# Phase 4 delivery / 2026-09-22

## Delivered results

The frozen first release suite uses `deepseek-chat` and `sentinel-benchmark-v2`:
8/8 workflows completed, 7/8 root and service judgments correct, 1,461,870 workflow
tokens, 284 tool calls, 78.75 seconds mean workflow duration. Retry storm remains
incorrect. All eight Critic verdicts are PARTIALLY_VERIFIED. See
[evaluation and open findings](phase4-evaluation.md), not a production accuracy claim.

| Phase | Delivered evidence |
|---|---|
| A | Four baseline aliases, SHA256 manifest, original benchmark business archive |
| B | Typed durable state, pinned Investigator context, six budgets, read registry, bounded repair, provider journal and tool receipts |
| C | Initial 81-test gate; final exact-source gate: 189 passed |
| D | V3.1 first 1/8 completed; failures retained; separate 3.1.4 qualification 5/5 |
| E | Structured Evidence Compiler, raw detail tools, importance/diversity and measured context telemetry |
| F | V4 first 7/8 workflows, 5/8 root; two fixture confounds retained and excluded from Pareto |
| G | Four real model component candidates; contracts plus three HTTP services with PostgreSQL/Redis/Kafka |
| H | Actual SIGKILL/exit 137, same-run resume, state fingerprints; retained failed first exercise; provider/tool/patch recovery tests and actual injection probes |
| I | Live SSE, runtime diagnostics, recorded replay, candidate export, six historical cohorts and separate release panel |
| J | Static integrity, actual API/DB boundary tests, real browser checks and disclosed security limits |
| K | Eight first dispatches, frozen result, unchanged model/runtime across suite, final report and read-only healthy environment snapshot |

Passing these finite gates does not close every defect. Critic can omit root-cited
evidence, the readable generic fault helper exposes experiment plumbing, and a legacy
patch-attempt counter misses generic candidates. Their exact evidence and next-version
requirements are in `evaluation/phase4/release-failure-analysis.json`. No post-result
runtime changes or answer-selective reruns were made to disguise them.

## Reproducible evidence

- `evaluation/results/v4.1-first-controlled.json`: frozen raw first suite, SHA256
  `74b48f0cc7a3f341ca0a088a50054fa0c45209034d12aa4f5de46a4f1fa2c81a`.
- `evaluation/phase4/final-release-report.json`: metrics, outcomes, failure classes,
  provider/tool counters and comparison limits; excludes Evaluator token use.
- `evaluation/phase4/comparison.json`: six historical versions; V4.1 stays separate.
- `evaluation/phase4/v4.1-framework.zip`: code and documentation snapshot from before
  the final suite. Delivery documentation additionally includes post-suite findings.
- `evaluation/phase4/v4.1-image.json`: actual image IDs. Sentinel release image tag:
  `project-sentinel:phase4-v4.1-first`; image ID
  `sha256:94545b6e5667a9281b30f4c5d25fcf2a56f95b3f8069c64efd489397882d36e3`.
- `evaluation/phase4/reliability-tests-final.json`: 189 tests and exact tested source hashes.
- `evaluation/phase4/crash-resume-first.json` and `crash-resume-followup.json`: failure
  and successful recovery; not additional RCA benchmark scores.
- `evaluation/phase4/live-browser-first.json`: actual growing SSE event count during
  the formal run; no browser mutation/model dispatch.
- `evaluation/phase4/ui-e2e-final.json` and `release-browser-first.json`: real Edge
  browser/API checks, desktop/mobile, recorded replay and candidate review/export.
- `evaluation/phase4/release-health-first.json`: 14 services running, six HTTP health
  checks, advancing consumer, low lag, healthy HTTP window, no active faults, unlocked
  evaluation and enabled traffic. Some infrastructure containers have no Docker
  healthcheck; running state is not mislabelled as Docker health verification.

Original V1/V2/V3 failures, V3.1/V4 first suites, failed qualification attempts, test
failures and component-model failures remain available. Frozen result hashes and
read-only attributes provide integrity checks, not administrator-proof immutability.

## Delivery archive

`outputs/sentinel-phase4-source-evidence.zip` contains current source, scripts,
documentation, UI, tests and original evidence. Its per-file manifest is
`DELIVERY-MANIFEST.json`; the external archive hash and metrics are recorded in
`outputs/sentinel-phase4-delivery.json`. The archive excludes `.env`, Git internals,
bytecode, Docker images/volumes and previous delivery ZIPs. Historical source archives
under `evaluation/` remain included. Keys are checked locally without exporting their
values. The post-packaging static audit is a separate sidecar, not self-embedded.

Start on another machine with the README Compose command and separately configured
provider credentials. Docker volumes and live database state are not in this source
archive. Recorded evaluation replay uses exported evidence without paid model calls;
a new live demonstration creates fresh data and incurs actual configured-provider use.

## Demonstration entry points

Open [Dashboard](http://localhost:18082/),
[Evaluation](http://localhost:18082/evaluation.html) and
[Architecture](http://localhost:18082/architecture.html).
Use [the demonstration guide](demo-guide.md) for live investigation. For an immediate
recorded code-patch example, choose `code_exception` in the independent V4.1 panel.
Its candidate passed nine contract tests and changed the same eight failing sandbox
requests from 100% to 0% HTTP 500; PostgreSQL writes and a Kafka event were observed.
It is HIGH risk and remains review-only. Stopping a fault is operator recovery,
not an AI patch deployment.
