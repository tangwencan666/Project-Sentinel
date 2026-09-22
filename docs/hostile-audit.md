# Stage 2 hostile audit

The executable scanner is `scripts/audit_phase2.py`; its exact keyword locations and credential checks are saved in `phase2-audit.json`. It scans hidden repository files except `.git`, `.env`, and bytecode. Credential values and matching lines are never printed.

## Keyword classification

| Location | Why it matches | Effect on authenticity |
|---|---|---|
| `.env.example`, `sentinel/api.py` | Local demonstration comments | The network boundary is loopback; no fake results |
| `infra/init.sql` | Demo customer seed | Declared synthetic business seed; subsequent HTTP, database and queue operations are real |
| `scripts/verify_lab.py` | `sample()` / samples, statement that data is not mocked | These functions issue real HTTP requests |
| `sentinel/tool_registry.py` | `sample_seconds` | Actual one-second PostgreSQL observation interval |
| README and design/demo documents | Demonstration and sampled metrics terminology | Describes actual behavior and limitations |
| `docs/phase2-*.json` | Model prose and retained failure explanations | Raw observations and model output; never used as runtime answers |
| Audit/report scripts and this document | Search terms and descriptions | Inspection/reporting only |

No runtime mock LLM, canned AI conclusion, generated metric substitute, static AI timeline, fake trace, fake patch or invented token usage was found. RULE_BASED conclusions intentionally use explicit telemetry predicates and are labelled accordingly. The ground-truth registry is deterministic experimental metadata, not investigator input. The local protocol fault server deliberately returns timeout/429/500/invalid responses to test failure handling; it is not included as a successful real-model investigation.

## Ground-truth boundary

Investigator tools cannot read registry, evaluator, reports, configuration, `.env`, arbitrary SQL, Redis key enumeration or shell. `services/app.py` is denied because it combines fault branches with business logic. Exact allowed source paths and cross-run evidence checks are tested. The investigator capability import graph has no registry/evaluator import. Evaluator checks a terminal run before loading truth and uses a separate conversation. The evaluator never writes back into Investigator history.

No direct ground-truth leak was found in that capability boundary. This is not an adversarially proven OS boundary: API, agents and evaluator still share a process. Fault-related instrumentation and real SQL symptoms can reveal mechanisms; those are legitimate observations, not a registry answer supplied to the model. General malicious-code isolation is not claimed.

## Findings fixed and retained

- Real generated diffs without the envelope's final newline were rejected. The parser now accepts that transport omission while retaining path, context and hunk checks; failed pilots remain.
- SQL observation included its own query because the query text contained business-table names. The filter now excludes diagnostic SQL for both rule and AI callers. The contaminated run remains archived.
- A second observer issue was found: different PostgreSQL `queryid` values can share the same normalized query text. Deltas keyed only by text falsely counted historical sleeping-query calls. The observer now keys by `(userid, dbid, queryid)` and treats a new/reset counter as unknown. A dedicated collision/reset regression test and a fresh full comparison follow this fix; the interrupted V2 round is retained as invalid for accuracy comparison.
- Long histories exceeded the context ceiling. Bounded previews and same-run evidence paging were added; prior failures remain.
- Critic JSON could omit fields or exceed schema lengths. A dedicated submission schema was added, and validated root proposals persist even if a later verifier fails.
- A test migration performed during the first benchmark invalidated cached PostgreSQL plans. Those final trials are labelled experiment interference, not model failures. Subsequent frozen runs do not run migrations or restart services.
- Windows console encoding created a duplicate runner-error row for one successful investigation. Raw data remains untouched; derived historical statistics use unique incident IDs and disclose the duplicate.

These fixes do not change ground truth or supply scenario-specific answers to the AI. The baseline's decision predicates were not tuned to achieve target scores; changes only handle observer exclusion, active sessions and unknown deltas consistently.

## Remaining exposure

Source and tests are copied into bounded temporary directories, but the pricing HTTP replay is not a complete six-service sandbox. No authentication/RBAC/HA, production rollout pipeline, comprehensive prompt-injection red team or exact workflow resumption is implemented. Pricing is the only supported code patch path. These remain explicit limits rather than simulated capabilities.
