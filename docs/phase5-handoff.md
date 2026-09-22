# Phase 5 continuation record

Final interview delivery supersedes the polish archive as the current handoff:
[FINAL_STATUS](../FINAL_STATUS.md) and [final delivery audit](final-portfolio-audit.md).
Use `outputs/sentinel-portfolio-final.zip` and `outputs/sentinel-interview-pack.zip`.
The earlier polish stage below is retained as a development milestone.

GitHub publication destination: [tangwencan666/Project-Sentinel](https://github.com/tangwencan666/Project-Sentinel).
The source repository includes the recorded data; delivery ZIPs remain local artifacts.
The next-work list below records the handoff before the publication task.

Status: the portfolio polish stage is complete and recoverable. No new DeepSeek
benchmark or remote LLM request was made. Do not re-run V4.1 to refresh the demo.

## Current entry points

- Recorded portfolio: `docker compose up -d --build`, http://localhost:18082.
- Full local lab: `compose.live.yaml`, port 18083; keep `LIVE_AI_ENABLED=false`
  unless the user explicitly opts into real fault/model operations.
- Latest source package: `outputs/sentinel-phase5-portfolio-polish.zip`, with
  `outputs/sentinel-phase5-delivery-polish.json` hashes. Original release retained.
- Published verification summary: `portfolio/verification.json`.
- Original reports, including failures: `artifacts/phase5/`, intentionally Git-ignored.

## Completed follow-up

The documentation page now renders safe headings, tables, lists, screenshots and
section anchors. It downloads original Markdown and links to current acceptance and
audit records. Raw HTML is escaped, unsafe URL schemes stay inert, and external
images are blocked. Ten local tests cover rendering and security.

The historical trace pagination regression now reads the public, genuine V3.1
recording with manifest verification. Its 90 spans match the frozen original;
the test no longer depends on an ignored internal archive.

Current gates: 267 backend tests, 17 frontend tests and 37 public browser checks.
The public container security gate remains 42 actual HTTP checks plus capability
assertions. All run without a real model call. The first failing document-test
attempt counted a shell-code comment as a heading; browser harness fixes handled
multiple headings and Windows line endings. Failed attempts remain recorded.

## Reproduce a check without erasing evidence

Use a new output filename each time:

```sh
python scripts/test_phase5.py --output backend-next.json
npm ci
npm test
npm run test:e2e -- browser-next.json
python scripts/audit_public_demo.py --output public-next.json
python scripts/audit_portfolio.py --output repository-next.json
python scripts/test_clean_start.py --release next
python scripts/package_portfolio.py --release next
```

Backend tests need local PostgreSQL/Redis/Kafka. Browser tests need a running public
demo and the browser installation described in README. Clean-start uses isolated
port 18084 and its own Compose project. Packaging requires Git candidate files.
Do not invoke historical evaluation scripts for UI work.

## Optional next work, outside this completed stage

1. Publish to the user's chosen GitHub repository when a destination is provided;
   no remote repository or public deployment currently exists.
2. For public hosting, follow the minimal read-only deployment guide and configure
   the actual hostname/TLS at that time. Do not expose the full lab.
3. Keep retry-storm error, Critic citation omission and experiment-helper visibility
   explicit. Any future core research belongs to a separately authorized stage;
   it must not replace frozen first-run results.

No partially applied implementation or pending paid evaluation is left by this stage.
