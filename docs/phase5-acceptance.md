# Phase 5 acceptance record

Project Sentinel — AI-Powered Production Incident Investigation & Remediation Platform.

Phase 5 turns the existing system into a GitHub-ready, recorded portfolio demo.
No new benchmark or live LLM evaluation is requested. V4.1 remains 8/8 workflow,
7/8 RCA/service, 1,461,870 tokens, 78.75 seconds mean; 189 tests is the Phase 4 freeze.

## Current verification

- Backend final gate: **267 passed** (189 existing + 78 public/portfolio cases),
  49.87 seconds, one dependency deprecation warning. Earlier 267-pass runs are retained.
- Frontend unit tests: **17 passed** (seven replay + ten document-rendering/security).
- Browser verified nine pages at 1366×768, 1920×1080 and 390×844; **37 checks passed**,
  no real-page console errors, unhandled errors, resource 404s or mutation requests.
- All 56 historical outcome buttons load retained recorded records. A separate,
  labelled frontend response fixture tests loading/error/empty states.
- Actual public HTTP/container audit: 42 checks passed; writes rejected, no provider,
  DB clients, credentials or Docker socket; UID 10001 and read-only filesystem.
- Recorded export: 204 original ordered events, 19 evidence items, one same-run AI
  candidate. IDs/times and SHA256 provenance retained. Exact trigger time is unknown,
  so only the actual first fault observation is shown.
- Local Live workspace: six read-only browser checks passed; no console errors,
  resource errors or mutations. AI and fault controls remain disabled.
- Clean startup: copied Git publication tree, no `.env`, no model credentials;
  default Compose built and served the correct run on an isolated port. Only that
  temporary Compose project was stopped afterward.
- Recorded and Live environment checks passed; provider configuration was checked
  for presence only. No provider request was made.
- Model-call ledger stayed unchanged: **zero new remote LLM calls**. No benchmark
  was rerun. Frozen baseline, V3.1, V4 and V4.1 hashes still match.

Raw development test reports remain in local `artifacts/phase5/`, including failed
attempts. A [sanitized verification summary](../portfolio/verification.json) carries
report hashes and measured results without private paths or raw container logs.
The [adversarial audit](phase5-adversarial-audit.md) explains the tested boundaries.
No test count includes browser checks or historical benchmark trials as unit tests.

## Final delivery checklist

| # | Deliverable | Final status |
|---|---|---|
| 1 | Positioning | AI-Powered Production Incident Investigation & Remediation Platform; production-oriented portfolio, not a production-readiness claim. |
| 2 | Dashboard | Clear recorded mode, six services, real topology provenance, observed error/latency window, incident and V4.1 result context. |
| 3 | Recorded Demo | Real HTTP 500 run, original event order, play/pause/restart, 1×/2×/4× and skip to root cause. Errors and repairs retained. |
| 4 | Live Mode | Existing full local lab preserved in `compose.live.yaml`, port 18083; AI/fault/automatic investigation disabled by default. |
| 5 | Public Demo Mode | Default minimal Compose, read-only server, no provider/DB/tool runtime or credentials. All mutations denied. |
| 6 | README | Rewritten positioning, screenshots, results, architecture, quick start, failures, security and limits. |
| 7 | Five-minute demo | [Timed narration](demo-5min.md), ready to read during an interview. |
| 8 | Ten-minute demo | [Technical narration](demo-10min.md), runtime, context, evaluation and boundaries. |
| 9 | Interview Q&A | [49 questions](interview-qa.md), including Rule vs AI, V3 failure, cost, Critic and deployment limits. |
| 10 | Chinese resume | [Four factual bullets](resume.md), no invented users or production deployment. |
| 11 | English resume | [Four factual bullets](resume.md), consistent with the same frozen results. |
| 12 | GitHub hygiene | Git candidate tree excludes credentials, internal experiment archives, outputs, caches, dependencies and IDE files. No hosted GitHub repository is claimed. |
| 13 | Secret audit | Current repository, historical local outputs, nested ZIPs and available Git history scanned; no configured-key matches or suspicious token patterns detected in scope. |
| 14 | UI audit | Nine pages at 1366×768, 1920×1080 and 390×844; no page overflow; desktop and narrow screenshots reviewed. |
| 15 | Browser E2E | 37 public checks plus six retained local Live read-only checks passed; console/unhandled/resource errors and mutations were zero on successful runs. |
| 16 | Public security | 42 real HTTP checks plus actual container isolation assertions passed; 48 API mutation cases also passed in backend gate. These overlap in purpose and are not added to unit-test totals. |
| 17 | Recorded integrity | Incident/run IDs cross-checked for tools, evidence and patch; all 204 original events preserved. Per-file SHA256 checked at server startup. |
| 18 | Test result | 267 backend tests + 17 frontend unit tests passed. The historical trace regression now verifies the included, genuine 90-span recording and no longer skips for absent internal archives. |
| 19 | Screenshots | Eight actual recorded UI captures, listed below; no synthetic screenshot data. |
| 20 | Future public hosting | [Minimal deployment guide](deployment-public-demo.md): frontend + read-only API + recordings behind TLS; no full lab or paid model. Not deployed to the internet. |
| 21 | Remaining limitations | Retry-storm RCA remains incorrect; Critic omission, experiment-helper visibility and sandbox/runtime limits remain documented below. |

## Delivery artifacts and reproduction

The latest local delivery archive is `outputs/sentinel-portfolio-final.zip`;
its separate SHA256 and per-file manifest is `outputs/sentinel-portfolio-final.manifest.json`.
The original `sentinel-phase5-portfolio.zip` release is preserved. These files are
excluded from Git to avoid publishing nested copies. The archive contains source,
sanitized genuine records, tests, documentation and screenshots, not `.env` or
original internal experiment archives. Those original archives remain untouched.

Run `docker compose up -d --build` from the extracted tree; open
http://localhost:18082. It needs Docker and first-build dependency downloads, not
a model key. See README for optional local backend and browser test dependencies.
Packaging does not create a remote repository or publish a deployment.

## Retained development findings

The initial browser run caught a global `top` naming conflict; the UI module was
isolated in a closure. A second browser check lacked an asynchronous wait for the
provenance modal; corrected the test to wait for the actual response. Both attempts
remain local audit evidence. Subsequent real-page checks passed.

The local Live page had a missing favicon resource; it now references the existing
SVG. Its first smoke test also used an ambiguous navigation selector, and a retry
ran before the recreated service was ready. Selectors and bounded readiness polling
were corrected; all failed reports are retained alongside the successful result.

Visual review found narrow topology labels too small; the graph now has a contained
horizontal inspection area. An evidence-group classifier incorrectly matched the
letters `log` inside `topology`; classification now uses actual log-tool names and
has a regression assertion. These are presentation changes, not benchmark changes.

The backend emits one third-party Starlette TestClient / AnyIO deprecation warning.
It is a local test dependency warning, not a browser console error.

The follow-up polish replaces raw Markdown display with a safe document reader,
section navigation, readable tables, local screenshots and original-source download.
Public links to acceptance and audit documents are now present. HTML is escaped;
unsafe protocols and external image loads are rejected. Ten local tests cover these
boundaries. Browser assertions now distinguish page and article headings and normalize
Windows line endings when comparing downloaded Markdown. Earlier failed harness
reports remain retained. The provider-ledger comparison normalizes equivalent UTC
timestamp representations; remote counts and times are unchanged.

## Screenshots

- [Dashboard](screenshots/dashboard.png)
- [Service Topology](screenshots/service-topology.png)
- [Investigation Replay](screenshots/investigation-replay.png)
- [Evidence](screenshots/evidence.png)
- [Root Cause](screenshots/root-cause.png)
- [AI Patch](screenshots/ai-patch.png)
- [Evaluation](screenshots/evaluation.png)
- [Architecture](screenshots/architecture.png)

All screenshots come from actual recorded UI with real data. No UI fixture is used
for a portfolio screenshot.

## Remaining limits

The existing retry-storm error, Critic citation omission and generic fault-helper
visibility remain open. Generic patches are not deployed. Single-cohort results do
not establish general incident intelligence. The public demo is read-only history,
not a live commerce system. No public domain, server or repository has been published.
Local Live mode still lacks production multi-tenant security and worker leases.
