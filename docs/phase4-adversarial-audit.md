# Phase 4 adversarial audit

The audit attempts to falsify capability, provenance and recovery claims. It is not
penetration-test certification or a production security guarantee.

## Actual checks

- `static-audit-final.json`: 36 baseline/archive/current-business integrity checks;
  scenario/scorer/pricing-contract hashes unchanged; no Investigator imports of truth
  modules; no configured key in scanned sources, records or archive entries.
- `adversarial-audit-final.json`: actual cross-origin mutation 403, untrusted Host 400,
  frozen-runtime dispatch 409, generic live deployment 409. The investigator DB role
  cannot SELECT evaluation, checkpoint or provider-call tables. Actual-key scans across
  12 tables and Sentinel logs found zero matches; evidence had no truth-field markers.
- `reliability-tests-final.json`: 189 passing tests, including actual dispatcher
  attacks with traversal, secret paths, arbitrary shell/HTTP/SQL, oversized arguments,
  role escalation and malformed calls. AST rejects protected patch paths, imports,
  attributes, arbitrary calls and executable module expressions.
- `prompt-injection-first.json`: four real DeepSeek calls with malicious log, source
  comment, incident and trace data all chose safe capabilities. These are explicitly
  attacker-input fixtures, not invented production observations or RCA successes.
- `ui-e2e-final.json`: actual browser/API workflow; recorded replay made no model
  request, generic candidates offered no live Apply, and recovery diagnostics matched
  the persisted run. Screenshots were visually inspected.

## Findings and resolutions

The first crash exercise restored exact state but failed semantic submissions. Bounded
contradiction correction and a readable checkout business module were added. An attempted
read allowlist expansion to `services/app.py` failed two pre-existing security tests;
the change was rejected. Checkout was extracted while experiment wiring remained hidden.
Original failed tests and crash results remain available.

Public provider responses now commit with usage and diagnostics before checkpointing.
The cached request digest rejects changed envelopes. Tool receipts are also bound to
the original tool and arguments: the same call ID cannot be reused for a different
capability. Patch feedback and attempt counts survive resume. Candidate validation
reuses completed artifacts and never writes production source.

Six earlier synthetic patch-boundary records inherited the generic validator's
`AI_GENERATED` label despite belonging to `RELIABILITY_TEST` runs. They are retained,
identified in the runtime audit and excluded from all RCA/component-model scores.
New such records carry `TEST_FIXTURE` explicitly. The original database label is not
silently rewritten. Real component-model probes remain separately identified by their
actual provider calls. The label migration's first SQL attempt failed the test gate
(40 failed / 147 passed); fixing literal-percent handling produced 187 passing tests,
then the receipt-identity checks brought the final gate to 189.

## Limits that remain

Final-suite inspection adds **open**, unpatched findings in the frozen V4.1 release
(`evaluation/phase4/release-failure-analysis.json`). In the wrong retry-storm run,
Investigator read and cited `E-38d10b8ede804ec3` (runtime.py:40–41), but Critic's
separate compiler packet dropped it for space. The Critic therefore claimed that
source was not supplied. The persistent evidence and Investigator read registry did
not lose it; root-citation coverage is not guaranteed at the Critic handoff, and Critic
has no detail-tool recovery loop. A later version needs mandatory cited-evidence
delivery with measured provider-visible coverage. All eight verdicts are only
PARTIALLY_VERIFIED; zero false accepts has zero VERIFIED denominator.

That source contains the generic fault-key helper. Registry/ground truth/scorer access
is denied, but injection implementation is not completely hidden. The model inferred
an unobserved payment fault key and blamed fast 503s instead of order's five immediate
retries. This is a retained reasoning failure plus a benchmark-blinding limitation,
not proof of a truth-table read. No inferred DEL/KEYS recommendation was executed.

The legacy `patch_generation_attempts` counter does not include generic validation;
the real candidate is proven by PatchGenerator calls and the artifact. These findings
do not alter the first result, evaluator, source or score. Passing boundary audits does
not close semantic/context findings.

The API is bound to localhost with Host/origin checks, not authenticated multi-tenant
RBAC. Workers use a single-process ownership assumption, not distributed execution
leases. Database and control/evaluation processes share infrastructure; capability
restrictions do not defend against host administrators or arbitrary server RCE.

Candidates are restricted pure functions, run as non-root with resource ceilings.
Trusted wrappers own I/O, but processes share a kernel and dependency servers. A hard
container kill during replay can leave dedicated temporary namespaces; this is not
transactional production deployment isolation. Generic candidates remain review-only.

Response persistence reduces duplicate work but cannot recover a response lost before
commit or guarantee exactly-once provider billing. Secrets scans detect the literal
configured key and known markers, not every transformed/semantic exfiltration channel.
Four injection samples do not prove universal model compliance. Investigator, Critic
and Evaluator still use the same model and can have correlated errors.

Frozen results use exclusive files, hashes and read-only flags rather than WORM
storage. One run per scenario is descriptive. V4's two fixture confounds and V3/V3.1
failures remain in the UI; qualification and final-release results use separate cohorts.
