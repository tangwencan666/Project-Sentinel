# Claims vs Reality — independent audit

Audit date: 2026-09-23. Initial revision: `0d3cc795f2bd127f03c54287927af0d46e5a9613` (clean worktree). Verdicts concern the scope stated in each row. Historical results are not results for the post-audit runtime. No real model request was made.

Source below means where the claim appeared; implementation and actual checks were inspected separately. See the [independent report](docs/independent-final-audit.md) and [machine-readable evidence summary](docs/independent-audit-evidence.json).

| Claim | Source | Implementation evidence | Runtime / retained evidence | Verdict |
|---|---|---|---|---|
| Six commerce microservices | README / architecture | `compose.live.yaml`, `services/app.py`, `SERVICE_NAME` selects handlers | Six running, healthy service processes; real HTTP logs and trace processes | VERIFIED; shared codebase and database, not six independently owned domains |
| PostgreSQL is used | README | `services/runtime.py`, `infra/init.sql` | Real business rows, request logs, pool statistics and query observations | VERIFIED |
| Redis is used | README | Catalog TTL/cache, fault flags, notification offset | Actual TTL and hit/miss counters | VERIFIED |
| Kafka is used | README | Redpanda + aiokafka producer/manual-commit consumer | Real orders topic offsets/commits and sandbox event checks | VERIFIED; Kafka-compatible Redpanda |
| Distributed traces | README | OTel FastAPI/httpx/psycopg/Redis instrumentation; Kafka context propagation | Jaeger traces returned with service processes and child spans | VERIFIED |
| Eight real fault mechanisms | Fault Lab | `sentinel/scenarios.py`, `services/app.py`, Redis-controlled fault flags | Eight frozen cases with observations; code and existing integration tests inspected | VERIFIED as lab mechanisms; full eight-scenario reinjection was not repeated in this audit |
| Fault controls can stop/recover | Fault Lab | Explicit flag clear / TTL / bounded handlers | Retained recovery observations and tests | PARTIALLY_VERIFIED; no new eight-fault campaign |
| Agent invokes real tools | README | 25 registered capabilities; 18 current Investigator tools | Persisted tool arguments, tool results, evidence and trace/code reads | VERIFIED |
| Agent runtime has state/checkpoint/resume | README | `runtime_state.py`, `runtime_agent.py`, `runtime_tools.py`, `checkpoints.py` | Actual DB receipt/checkpoint/error tests pass; historical process-kill artifacts retained | VERIFIED within one worker; no distributed exactly-once guarantee |
| Errors/JSON repair/budgets are bounded | Runtime Reliability | `structured_output.py`, `convergence.py`, six budget buckets | Local HTTP 429/500/timeout, bad JSON/schema, failure streak and resume regressions executed | VERIFIED for tested protocol paths |
| Root citations are read and in-run | Agent design | Citation registry, run-scoped evidence query, diagnosis guards | Unread/cross-run and correction regressions pass | VERIFIED structurally; citation relevance is not proved by an ID |
| Critic received complete root-cited evidence in frozen V4.1 | Earlier “one case” limitation | Original compiler could drop citations by diversity/cap/size | Missing root IDs in all eight retained Critic inputs | FALSE; corrected disclosure, original results retained |
| Current Critic cannot silently drop required citations | Independent fix | Mandatory IDs before ranking; cite only delivered IDs | New regressions pass; offline historical repack: six fit, two explicitly overflow | VERIFIED boundary; current full workflow accuracy UNVERIFIED |
| Ground truth is hidden from Investigator | Fault Lab / security | Registry/scorer absent from allowed source; fixed observation APIs; no arbitrary HTTP/SQL | No answer-level truth markers in retained observational evidence; denied-path tests pass | VERIFIED within inspected capabilities, not a universal leakage proof |
| No experimental clue is visible | Stronger interpretation of isolation | `services/runtime.py:fault` is readable | Generic `fault:` helper appears in retained evidence | FALSE if interpreted this strongly; experiment plumbing remains visible |
| Model produced featured patch | AI Patch | FixAgent source proposal → validated deterministic unified diff | Same-run model response source equals patch; call `a61b69d5-965e-4d40-8bed-acd38c028220`, 1,226 measured tokens | VERIFIED from internal ledger, not provider-signed attestation |
| Arbitrary repository auto-repair | Possible reading of “remediation platform” | Four allowlisted pure-function profiles only | Pricing/payment/order/inventory contracts | FALSE at this scope; README describes constrained candidates |
| Safe candidate paths / immutable tests | Security | Exact paths, AST allowlist, controller-selected contracts | Protected paths, import/attribute/call/loop rejection tests pass | VERIFIED within the supported Python subset |
| Secure production sandbox | Possible interpretation | Subprocesses, scoped DB schema/Redis namespace/Kafka topic; shared kernel/DB privilege | Actual three-service HTTP replay; no microVM/container per candidate | FALSE; bounded local test environment only |
| Featured candidate passed nine tests | AI Patch | Immutable pricing contracts | Same-run raw pytest output: nine passed; baseline two failed | VERIFIED historical result |
| HTTP 500 improved 100% → 0% | AI Patch | Identical eight invalid-discount replay inputs | Eight measured HTTP outcomes before and after, same artifact | VERIFIED for this sandbox workload; P95 increased |
| Patch deployed to production | Explicitly denied in UI | Generic automatic apply false; public mutation gate | UI disabled Apply, HTTP 403; artifact `production_applied=false` | FALSE; candidate NOT DEPLOYED |
| Frozen V4.1 workflow 8/8, root/service 7/8 | README / Evaluation | Unchanged scorer and registry | Recounted eight rows; public projection agrees; retry storm incorrect | VERIFIED for frozen build and controlled cohort |
| 87.5% production accuracy | Explicitly denied in README | Eight cases, one cohort, model judge | No repeated trials, confidence study or external incidents | FALSE |
| V3 is a successful token optimization | Explicitly denied in UI | Retained original failures | V3 workflow 2/8, root 1/8; V3.1 workflow 1/8, root 1/8 | FALSE; UI truthfully marks failures |
| All versions are identical first-attempt ablations | Possible comparison inference | V2/V3 first-valid pool replacements; V4.1 changed readable-source cohort | Replacement policy and original invalid trials retained | FALSE; disclose selection/cohort differences |
| V4.1 used 1,461,870 workflow tokens | README | Provider usage ledger, not character estimator | Sum of 106 non-Evaluator calls; Evaluator adds 131,110 | VERIFIED; combined total 1,592,980; dollar price unknown |
| Recorded Demo is one genuine run | README | `export_portfolio.py`, `portfolio/data/manifest.json` | 204 events + 19 evidence + patch/tests match sanitized same-run originals | VERIFIED from available internal provenance |
| Playback is live AI | Explicitly denied in UI | Local timestamp cursor and immutable JSON API | All nine pages say RECORDED DEMO; browser sent no mutations | FALSE |
| Public Demo is read-only | Security | Separate public server/image, no provider/tool/DB code or credentials | 42 direct HTTP checks plus container isolation; new Range/Host checks pass | VERIFIED for tested deployment |
| Public Demo works offline | Recorded Demo | Packaged local assets and data | Prepared image ran with `--network none`: 37 checks | VERIFIED after image preparation; first build needs downloads |
| Default quick start works without a key | Quick Start | Minimal `compose.yaml`, optional `.env` | Isolated copied candidate tree without `.env`, own port/project, real build/start | VERIFIED; see clean-start evidence summary |
| 267 backend / 17 frontend / 37 browser / 42 HTTP checks | Prior completion claims | Inspected suites, no skip/xfail substitution | Baseline 267; post-fix 287 backend, 17 frontend, 37 browser, 42 HTTP checks executed | VERIFIED; different suites, not one coverage percentage |
| No disclosed secrets in Git / data | Security | Git ignore, exporter redaction, minimized image | Exact configured-key and token-pattern scan, nested ZIPs and all Git blobs | VERIFIED within scan scope; not a guarantee against every encoding |
| Production-ready commerce or multi-tenant SRE SaaS | Explicitly denied in README | Shared DB, local credentials, no RBAC/leases/outbox/saga | Local controlled deployment only | FALSE; portfolio is the supported scope |
| Repository is permissively licensed open source | No license claim exists | No LICENSE file | Git candidate scan | UNVERIFIED; public visibility does not establish a license |

The audit did not regrade root causes using a new model or modify any frozen result. Source-level fixes are explicitly post-freeze.
