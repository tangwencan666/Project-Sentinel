# Runtime recovery and trust boundaries

Phase H extends the qualified runtime without replacing any formal RCA results.
The first 183-test gate is recorded in `evaluation/phase4/reliability-tests-h-attempt-2.json`.
The earlier 169-test response-journal gate is retained separately.

## Durable boundaries

Each provider request has a logical run/stage/attempt key and a digest of the exact
redacted messages, offered tools and tool choice. Received public content, tool calls,
usage and diagnostics are committed together. A restored checkpoint reuses that
response; a mismatching envelope fails closed. Provider `reasoning_content` is not
stored. Investigator request envelopes and the context actually sent are durable,
so resume cannot retrospectively mark unseen evidence as read.

Schema repair charges are recorded per attempt. Tool receipts reconcile each budget
debit once. Patch validation retains actual failed tests and stores its attempt key
with the artifact. Resuming after a completed attempt reuses its durable result and
continues with the same bounded candidate count and failure feedback. A crash before
a sandbox result is committed can repeat that isolated validation. This is not an
exactly-once claim about all physical work or provider billing: a response lost before
the database commit can require another HTTP request, with unknown first-request cost.

The recovery test controller injects one *real absent-symbol tool call* only after the
real DeepSeek investigator has established an active hypothesis and critical evidence.
It is labelled `RecoveryTestController`, not attributed to model reasoning. The host
then SIGKILLs its own named Compose one-off container, checks exit 137, starts another
worker and compares complete hypothesis/error/evidence/action/budget snapshots before
resuming the same run ID. Results, including failures, are retained in
`evaluation/phase4/crash-resume-first.json`. This is a recovery exercise, not an RCA
accuracy trial.

The first run restored the exact snapshot after exit 137, then **failed** after
three semantic submissions retained unresolved contradictory evidence (191,054
provider tokens). It is not a successful end-to-end recovery. Investigation showed
two separate issues: the checkout caller was outside the readable source set, and
the generic rejection forced another submission instead of permitting bounded
contradiction reads. A follow-up revision extracts actual checkout orchestration into
`services/checkout.py`, which has no experiment controls and becomes readable alongside
background worker source. The app wiring, scenario registry, scorer and active fault
state remain inaccessible. It emits `UNRESOLVED_CONTRADICTION` with detail/code correction capabilities.
It preserves the three-submission and two-schema-repair ceilings. Follow-up evidence
uses a new filename; the first failure remains immutable. The extra readable source
is an explicit final-release capability change, not a pure compression improvement.
The intermediate test gate (`reliability-tests-h-attempt-3.json`) correctly rejected
an attempt to expose the mixed business/experiment app file: 183 passed, two boundary
tests failed. Those tests were preserved and the design changed to the extracted
business module. This failure is retained as security review evidence.

The corrected gate passed 185 tests. `crash-resume-followup.json` then completed the
same-run recovery with an exactly matching state fingerprint, one resume, 12 actual
DeepSeek calls and 136,881 tokens. It generated a pricing candidate and passed the
real three-service sandbox; Critic remained `PARTIALLY_VERIFIED`. Nothing was deployed.
The follow-up is additional recovery evidence, not a replacement or an RCA score.
`h-business-release.json` verifies the six running business services against the new
14-file `sentinel-benchmark-v2` manifest. Scenario, ground truth, scorer, original
pricing contract and fault implementation semantics remain unchanged.

429 and 500 responses use a real local HTTP server and real PostgreSQL checkpoints.
The invalid-JSON exercise stops after the repair response is persisted and then reloads
the checkpoint, proving no duplicate repair request or budget debit. The timeout test
uses a real slow HTTP endpoint with an accelerated 20 ms boundary; the production tool
deadline remains 25 seconds. The patch failure test executes immutable pytest contracts,
reloads the failed outcome, checks receipt reuse, and validates a corrected fixture in
the real three-service PostgreSQL/Redis/Kafka sandbox. These deterministic fixtures are
explicitly excluded from model performance statistics.

## Adversarial evidence

Path traversal, secret paths, shell payloads, SQL injection, oversized arguments,
unknown outbound HTTP tools and TestAgent escalation are executed against the actual
runtime dispatcher with database ledgers. The patch tests additionally reject imports,
attributes, dynamic evaluation, nested functions, loops, protected paths and signature
changes. The SQL adapter uses fixed statements and parameter binding; the Investigator
has no arbitrary SQL, shell, HTTP or environment-reading capability.

`evaluation/phase4/prompt-injection-first.json` records four real DeepSeek probes:
log content, source comments, incident text and trace attributes. All four selected
safe tools in this first probe (17,183 provider tokens total). The malicious content
is an attacker-input fixture supplied to the actual model, not a fabricated production
observation. Each returned tool call was executed through the real capability boundary.
This small probe cannot prove immunity to all prompt injection; policy restrictions
remain necessary even when the model follows the trust boundary.

Candidate subprocesses run as the non-root container user with CPU, address-space and
file-size limits. They receive no LLM credential. Pure candidate functions cannot perform
I/O; trusted wrappers own dependency access. PostgreSQL schemas, Redis keys and Kafka
topics are unique per replay. They share the container/kernel and infrastructure servers:
this is a constrained function sandbox, not a hostile Python VM or production tenancy
isolation. All generic patches remain candidates; live application is disabled.

## Dependency readiness

The notification consumer is supervised with bounded reconnect backoff. Bootstrap or
stream failure makes HTTP health return 503, with the exception type and restart count;
a dead task cannot report healthy. The intentional consumer-lag fault keeps the task
alive and is measured separately through broker offsets. An actual failed Kafka TCP
bootstrap followed by a live broker connection is covered by the test gate.
Startup waits for database pool readiness. Archived runtime revisions are excluded
from automatic resume by the current API.

The original business source is retained as
`evaluation/benchmarks/sentinel-benchmark-v1/business-source.zip`; later business
extractions and readiness changes require a separately versioned final benchmark.
