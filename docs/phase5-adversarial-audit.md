# Phase 5 adversarial audit

Historical Phase 5 report. The [independent final audit](independent-final-audit.md) supersedes its Critic omission scope: retained telemetry shows missing root citations in all eight frozen inputs, not only the example identified here. Post-freeze guard changes and current test results are documented separately; the original findings below are preserved.

Project Sentinel — AI-Powered Production Incident Investigation & Remediation Platform.

Audit scope: portfolio presentation, actual startup, recorded artifact fidelity,
public-mode boundary and repository publication. No paid model evaluation was run.
This is an implementation audit, not an independent penetration-test certificate.

## Evidence checked

| Area | Direct check | Result |
|---|---|---|
| Startup | Copied Git candidate files into an isolated directory with no `.env`; built default Compose and queried health/config/run | Passed; no DB/model connection |
| Pages and controls | Actual Edge, nine pages, three viewport sizes, replay controls, all source filters, downloads, 56 historical buttons and the current document library | Passed; zero real-page console, unhandled or resource errors |
| Raw payload size | Initial summary under 100 KB; expanding one evidence item causes one raw request | Passed; no eager raw evidence load |
| Artifact fidelity | Original event IDs/timestamps/order; consistent run/incident IDs on tools/evidence/patch; frozen source and public-file hashes | Passed; 204 events and 19 evidence records |
| Mutation boundary | Actual POST/PUT/PATCH/DELETE attempts against fault, provider, deploy, database, tool, config, upload and secrets URLs | Every attempt returned 403 |
| Container capability | Actual non-root UID, filesystem write probe, import availability, secret environment/files and Docker socket checks | UID 10001; writes denied; provider/DB/tool capability absent |
| Local lab safety | Live UI read-only interaction and environment check | Passed; AI and fault controls disabled; no mutations |
| Cost | Remote provider ledger before and after Phase 5 | Unchanged; zero real model calls |
| Publication | Git candidates, personal paths, relative documentation links, oversized files, configured secrets, token patterns, ZIP entries and existing Git blobs | No findings in the scanned scope |

## Suspicious content review

Searches covered `fake`, `mock`, `hardcoded`, `TODO`, `FIXME`, localhost references,
personal Windows paths and the actual frontend/API boundary. Keyword hits in audit
scripts, explanatory comments and test names are not diagnosis evidence. No remaining
TODO/FIXME completion placeholders were found in the application source searched.

The protocol test server intentionally produces 429, 500, invalid JSON and timeouts.
The browser suite separately and explicitly injects loading/error/empty responses.
These are labelled test fixtures; neither contributes to benchmark scores or the
eight delivered portfolio screenshots. Rule baseline predicates, lab seed products
and the evaluator's fault registry are intentional lab components.

Recorded summaries are derived from frozen observations. They are not fresh AI
answers. The selected incident was operator-requested, not a recorded detector
alert. Its exact fault trigger timestamp was not persisted: the UI gives the first
observed active fault and does not manufacture a trigger event. Generic checkpoint
events are hidden by default for readability but can be expanded; none are removed
from the 204-event record. ERROR and RECOVERY events remain visible.

The public frontend uses same-origin URLs. Localhost defaults belong to local
launch/test tooling and optional observability links in the preserved local lab.
The future public hostname is configurable through `DEMO_ALLOWED_HOSTS` and a
reverse proxy. Personal workstation paths are absent from user-facing docs/web.

The `.env` file is deliberately local and ignored. Scanning never prints its values.
Local lab credentials in Compose/seed SQL are explicitly demo credentials, absent
from the public image. The repository currently has no Git commits, so there are
zero historical Git blobs to scan; local historical output/ZIP files were scanned.
Frozen originals were not rewritten. Public recordings are sanitized projections
with source hashes and a documented transformation policy.

## Defects corrected during Phase 5

- Global browser `top` collision: isolated the portfolio module in a closure.
- Evidence classification matching `log` inside `topology`: match actual log tools;
  a backend assertion now keeps topology in CONTROL.
- Narrow topology text: readable nodes inside a bounded horizontal inspection area.
- Missing local Live favicon: use the existing SVG resource.
- Raw Markdown-only document display: now has safe formatting, section links,
  local screenshots, original-source download and public acceptance/audit links.
- Archive-dependent trace regression: reads the included genuine recording with
  manifest hash verification; its 90 spans equal the original frozen payload.
- Test harness issues: await async modal content, select unique navigation controls,
  and poll local service readiness after recreation. Failed attempts remain retained.

Document rendering rejects unsafe URI schemes, remote images and executable HTML.
Ten renderer/security unit tests and actual browser document/anchor/download checks
passed. It is a limited reader, not a full Markdown/HTML execution environment.

## Open findings preserved

V3 and V3.1 remain FAILED EXPERIMENT / RUNTIME RELIABILITY FAILURE. V4's confounded
trials remain visible and excluded from Pareto comparisons. V4.1 remains 7/8 root
cause accuracy; retry storm is wrong and received no special-case repair rule.

Critic dropped one root-cited evidence item; all eight final Critic verdicts were
PARTIALLY_VERIFIED, not VERIFIED. Readable generic fault helpers still reveal some
experiment plumbing. A successful local test/replay does not establish a safe
production patch. The candidate is HIGH risk and NOT DEPLOYED; no Apply action is
available publicly. Shared sandbox kernel, absent multi-tenant RBAC/worker leases,
and possible duplicate billing after a lost remote response remain limits.

The scan detects literal configured secrets and common token shapes, not every
possible encoded credential. Hashes detect changes relative to this manifest, not
malicious replacement of both records and manifest. Public hosting still needs
TLS, host maintenance, rate limits and dependency reassessment. No public deployment
or GitHub upload occurred during this phase.
