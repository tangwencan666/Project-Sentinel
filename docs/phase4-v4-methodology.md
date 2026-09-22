# V4 evidence compiler and controlled experiment

V4 started only after the separately registered 3.1.4 runtime qualification
completed all five workflows, including a real pricing candidate passing tests
and HTTP fault replay. That qualification is **not** an accuracy result. The
immutable V3.1 first controlled result remains workflow 1/8 and root accuracy 1/8.

## Implementation and limits

`sentinel/evidence_compiler.py` compiles measured evidence into JSON objects.
Logs are grouped by service, severity, path, status and normalized message, with
sample counts, first/last timestamps and an actual representative. Counts refer
to returned samples, not the entire incident. Metrics have measured windows,
baseline/current/peak/delta/trend and a relative-change score; an unavailable or
nonfinite baseline is unknown. A pre-incident baseline is not necessarily healthy.

Trace summaries retain a longest nested span-chain approximation, error and slow
spans, service edges and repeated client calls. SQL fanout counts only actual
client spans carrying `db.statement`; enclosing internal spans are excluded.
Critical-path durations overlap and must not be summed. Code previews contain
complete numbered lines with actual ranges, symbols and locally observed calls.
Call relationships are limited to the parsed source slice.

Importance combines directness, anomaly markers, suspected-service overlap,
source uniqueness, cross-source service overlap and recency. These are explicit
selection heuristics, **not** probabilities or a causal classifier. Cross-source
overlap does not prove causality. The selection pass admits one observation per
available family before duplicates, within the character budget. At least two
families are retained when complete objects fit. Collection entries may be omitted
as whole objects with omission counts and raw-evidence references. Atomic strings,
SQL and JSON are never cut. An oversized atomic object may be omitted from the
summary or fail detail retrieval explicitly; this remains a documented limitation.

Critical evidence remains in pinned P1, and unresolved errors remain in P0.
The Investigator pack avoids duplicating P1 evidence. Planner and Critic receive
their own evidence selection. Detail requests bypass the compiler: trace detail
returns raw span pages; V4 `read_evidence` returns complete raw JSON records with
field/index paths and object offsets. Code detail returns the requested actual
lines. The read registry records only the ranges delivered to the model.

V4 infrastructure probes use real read-only SQL, Redis INFO/TTL/PING and Kafka
offsets. Counter rates have measured start/end/elapsed windows. Redis counts are
global and include Sentinel control traffic, so they are **not** a catalog cache
hit ratio. Missing/reset offsets have unknown rates. PostgreSQL reports sampled
connections, locks, active slow queries and query IDs alongside measured call
deltas. Connection-pool counters are obtained separately from service health.

## Telemetry

Every compiled pack records raw payload characters, compiled item characters,
compiled/raw ratio, retained and dropped IDs/reasons, and source families.
Investigator raw-payload size excludes observations already supplied in pinned P1;
`pinned_context_size` is recorded separately. Provider-envelope characters include
the actual nested message JSON. Actual input tokens and provider call ID are
attached after a successful response. Character/4 estimates are labeled separately
and never used as measured provider usage. Failed requests can have unknown usage.

## Qualification and first-run protocol

The final V4 source passed **138 tests** before paid evaluation. Seven additional
read-only probe assertions passed against live PostgreSQL, Redis and Kafka.
Synthetic protocol fixtures are labeled as tests; they are not benchmark incidents.
Offline compression profiles reuse retained qualification payloads and measure
only representation size, not model accuracy or token savings.

The first controlled order is pool exhaustion, N+1, cache miss, consumer lag,
downstream timeout, code exception, slow query and retry storm. Each receives one
formal model dispatch after an operator-only fault-validity check. Neither that
check nor scenario labels are sent to the Investigator. The unchanged evaluator
receives ground truth only after the workflow terminates. No failed answer is
replaced by a retry. The framework ZIP and Docker tag `phase4-v4-first` are frozen.

The runtime retains the 3.1.4 numerical budgets, 2500 provider output tokens,
300000 workflow tokens and at most two repairs per structured output. V4 also
inherits the runtime corrections, so V3.1-to-V4 is **not** an isolated compression
ablation. Jaeger now has bounded retention after a documented capacity incident.
Docker Desktop and the existing containers were restarted before V4 on 2026-09-22;
order-service was restarted after dependency startup failed. Business images and
benchmark/scenario/scoring source remained unchanged. Warmup and infrastructure
changes limit direct latency comparisons.

The first-run artifact is complete: workflow 7/8, overall root cause and service
localization 5/8, conditional root accuracy 5/7. Workflow usage is 1,296,540 tokens
(1,257,854 input, 38,686 output), 88 model calls and 248 tool calls; 188 tools are
useful under the shared heuristic (75.81%). Average recorded workflow duration is
70.19 seconds. The one pricing candidate passed actual unit tests and HTTP replay.
Cache failed bounded field repair; N+1 and retry storm completed but were graded
incorrect. The early provider record cannot distinguish wrong replacement type
from excessive replacement length in the cache repair error; later journaling
improves diagnostics without inventing missing historical information.

Two trials have the fixture confound described below. The unconfounded six-case
subset has root accuracy 4/6 and workflow completion 5/6; it is not an eight-scenario
estimate. V4 is excluded from Pareto ranking. Critic reviewed seven runs and marked
zero VERIFIED, so false accepts are zero with an undefined acceptance-conditioned
rate. Costs remain unknown without configured prices. One trial per scenario
supports no statistical generalization claim.

## First-run fixture confound, retained without reruns

After the N+1 trial, a real unrelated consumer failure was discovered. The Docker
restart started notification-service before Kafka DNS was available; its consumer
task failed bootstrap while its HTTP liveness continued to pass. Kafka offset
77113 stayed committed while the end offset grew to 78360 (lag 1247). N+1's agent
diagnosed that real stalled consumer instead of the injected database pattern.
The original scorer returned incorrect for the target scenario. Both the pool and
N+1 dispatches are therefore marked **confounded**, including the pool's correct
score, rather than selecting exclusions according to which answer was wrong.

The experiment runner was stopped before a cache model dispatch. Original bytes
and their hash were saved in `v4-before-consumer-intervention.json`; runtime code,
prompts, budgets and model were unchanged. Restarting the existing consumer after
dependencies were ready drained the backlog. Three real snapshots then showed
lag zero and committed offsets 78360 → 78375 → 78390. The remaining six previously
unstarted scenarios completed in their original order, with consumer progress and
low lag added to the operator preflight. No paid trial is repeated or overwritten.

The original eight first dispatches remain the primary historical artifact. Their
aggregate must be labeled as containing two confounded fixtures and is excluded
from Pareto ranking. The clean six-case subset is separately descriptive and is
not a substitute eight-scenario accuracy. A later separately named benchmark may
test the finished system; it cannot replace these first results.
