# Project Sentinel · Final portfolio status

**AI-Powered Production Incident Investigation & Remediation Platform.**

**Independent audit follow-up (2026-09-23):** [Final audit](docs/independent-final-audit.md) and [Claims Matrix](CLAIMS_MATRIX.md). The historical Phase 5 results below are retained. Current local regression gate is 287 backend + 17 frontend tests, 37 browser checks and 42 Public HTTP checks. Benchmark performed on frozen V4.1 build; post-freeze safety fixes have not been rebenchmarked. All eight frozen Critic inputs omitted some root-cited evidence; current required-citation checks fail explicitly if the mandatory bundle exceeds budget.

## What works

Six local commerce microservices with PostgreSQL, Redis, Kafka-compatible Redpanda
and OpenTelemetry; eight reproducible fault scenarios; constrained agent tool calling,
evidence-backed diagnosis, durable runtime and bounded candidate validation. The
portfolio presents the actual recorded workflow, evidence, code, tests and failures.

## What is recorded

Default demo: V4.1 run `759044e6-c016-489b-a459-137ca4846462`, recorded 2026-09-22 UTC,
deepseek-chat. Its 204 ordered events, 19 evidence records, pricing candidate and tests
belong to one Run. Playback does not execute tools again. Exact fault-trigger time is
unknown; first observed active fault and operator-requested incident creation are shown.

## What requires an API key

Only explicitly enabled local Live AI investigation requires provider configuration
and may spend money. Use `compose.live.yaml`, port 18083 and `LIVE_AI_ENABLED=true`
only when intentionally running real investigations. Default false disables dispatch.

## What is disabled in public demo

Fault injection, patch apply, live model calls, shell tools, database writes, config
changes, uploads and secret management. A separate minimal server rejects mutations;
its image contains no live provider/tool/DB modules or credentials.

## Benchmark results

| Version | Workflow completion | Root cause |
|---|---|---|
| Rule | 8/8 | 7/8 (87.5%) |
| V1 | 8/8 | 5/8 (62.5%) |
| V2 | 8/8 | 6/8 (75.0%) |
| V3 | 2/8 | 1/8 (12.5%); FAILED EXPERIMENT |
| V3.1 first controlled | 1/8 | 1/8 (12.5%); FAILED EXPERIMENT |
| V4 first controlled | 7/8 | 5/8 (62.5%); two confounded trials retained |
| V4.1 | 8/8 | 7/8 (87.5%) |

V4.1 service localization 7/8; 1,461,870 workflow tokens; 78.75 seconds mean. All eight
Critic verdicts PARTIALLY_VERIFIED. Eight controlled cases do not estimate production
accuracy. Retry storm remains incorrect. No paid benchmark was rerun for this delivery.

## Tests

V4.1 benchmark-time gate: **189 passed**. Archived Phase 5 release gate: **267 backend +
17 frontend passed**. Public browser suite: **37 checks**; public security audit:
**42 HTTP checks** plus container assertions. These counts are different kinds of
verification, not additive benchmark samples. One third-party test deprecation warning
is retained. Latest execution evidence and audit scope: [delivery audit](docs/final-portfolio-audit.md).

## Known limitations

Small authored benchmark, single-model coverage, high input token cost, Critic evidence
handoff defect, visible experiment helper, limited patch profiles, shared sandbox
kernel, incomplete Live production auth/leases/approval. Candidate is NOT DEPLOYED.
See [limitations](docs/limitations.md). Source repository:
[tangwencan666/Project-Sentinel](https://github.com/tangwencan666/Project-Sentinel).
The Recorded Demo runs locally; no publicly hosted application is claimed.

## How to start

```sh
docker compose up -d --build
```

Open http://localhost:18082. No `.env` or model key is required. Docker and first-build
dependency downloads must be available. **Offline runtime is supported after image
preparation; the source ZIP does not include that image.** On the prepared machine,
use `docker compose up -d --no-build --pull never` to avoid build/pull requests.

## How to demo

[30 seconds](docs/pitch-30s.md) → [3 minutes](docs/pitch-3min.md) →
[5-minute click-through](docs/demo-5min.md) → [10-minute technical demo](docs/demo-10min.md).
Use Recorded Demo only. [Interview depth map](docs/interview-depth-map.md),
[49 Q&A](docs/interview-qa.md), [24 hard questions](docs/interview-hard-questions.md),
[resume](docs/resume.md) and [future work, not implemented](docs/future-work.md).

Final archives: `outputs/sentinel-portfolio-final.zip` and
`outputs/sentinel-interview-pack.zip`; separate SHA256/file manifests accompany them.
Previous delivery archives and all frozen experiments remain retained.
