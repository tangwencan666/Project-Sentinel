# Issues found in the frozen V3.1 first controlled suite

This file records findings for work **after** the first eight scenarios finish.
No frozen runtime source or model prompt was changed during the suite.

1. **Convergence does not enforce progress.** Pool exhaustion stored a supported
   causal hypothesis but never called the submission tool, then exhausted the
   evidence-completion budget. N+1 also had a hypothesis and no submission attempt
   before the 480-second deadline. Cache miss exhausted completion without creating
   a hypothesis. Error pinning alone does not guarantee stage transitions.
   The next runtime revision needs an explicit evidence/hypothesis/submission
   controller with reserved, still-accessible citation/schema correction paths.
   Increasing the tool ceiling is not the proposed fix.

2. **Redaction repeatedly reads the mounted configuration file.** An actual N+1
   checkpoint traverses the `settings()` getter 3,423 times during one serialization.
   `settings()` reads `provider.env` each time. A separate read-only diagnostic
   process measured 31 ms for the same traversal with one in-memory configuration
   snapshot. This is evidence of repeated work, not yet a measured production
   speedup. Preserve immediate configuration reload between requests; take one
   redaction-key snapshot per serialization traversal. Add a scaling regression.
   Evidence: `evaluation/phase4/checkpoint-serialization-probe.json`.

3. **Audit the read registry at the actual model-input boundary.** Current tool
   success records a read before context assembly, while the context ceiling can
   drop P2 entries. A dropped detail response must not count as actually shown.
   Test the composed `model_result -> rebuild -> provider` path, not just the detail
   adapter. This is a code-review finding; no measured RCA failure is attributed to
   it without further evidence.

4. **Keep provider parse state synchronized.** `mark_parse` updates the database,
   but the checkpoint's cached provider diagnostics can still say `pending`.
   Tests must compare both persisted representations after repair/resume.
   Also link each pending tool batch to its original provider call: a repaired
   argument belongs to a new repair response and must not overwrite the original
   response's invalid parse result. Successful sibling tool arguments must not
   erase an earlier malformed argument in the same model response. Operational
   tool failures are not JSON parse failures.

5. **Measure the final nested JSON message envelope.** The first downstream-timeout
   investigation failed with `CONTEXT_BUDGET_EXCEEDED` after round 3. The 78k context
   object guard does not imply that the full `messages` envelope stays below the
   provider's 90k guard: embedding serialized context in a message adds escaping.
   Budget using the exact serialization checked by the provider, with whole-object
   P3/P2 eviction and explicit failure if pinned state itself cannot fit.

Qualification runs for a subsequent runtime revision must use new, clearly named
artifacts and be excluded from the frozen first-trial comparison. V4 may begin only
after the reliability gate passes. If V4 includes additional runtime fixes, disclose
that the V3.1-to-V4 comparison is not a pure compression ablation.

## First 3.1.1 qualification findings

The pool trial completed, including recovery from an illegal hypothesis transition.
The N+1 trial reached root submission, then its original response and both allowed
repairs were cut off. All three provider receipts explicitly record
`finish_reason=length` and 2,500 output tokens. This is confirmed output truncation,
not inferred from the cap. Its raw argument repeated long causal explanations and
invented descriptive signal IDs instead of copying the supplied S-number IDs.

The initial root contract allowed several long strings and unbounded signal
assessments. Repeating that malformed prefix under the same output ceiling did not
repair it. A follow-up output-contract candidate is being prepared with concise
field bounds, exact triage IDs and explicit shorter-object repair instructions.
No higher token ceiling is proposed. This is a runtime protocol intervention, not
an evidence compiler, and it will need a new qualification artifact.

Two pre-model operator interruptions are retained separately: a Jaeger read timeout
and a healthy-window assertion. The continued qualification preserves the prior
trial prefix exactly and only dispatches scenarios without an existing model run.
Neither interruption is counted as an AI diagnosis or silently changed to success.

## 3.1.2 accounting regression found in the first pool qualification

The bounded response avoided truncation. A first root response failed the new
450-character reasoning-summary constraint; two later proposals contained
contradicting evidence, and a subsequent proposal had no such conflict but still
exceeded two field lengths. Offline validation established that its final budget
error masked the original schema failure; it was not yet a valid compact submission.
The run nevertheless failed because the schema-invalid response had consumed a
submission-retry slot. Parse/schema errors need correction accounting; only an
actual locally validated submission should use the submission allowance. The
existing numeric ceiling of three stays unchanged.

The compact schema also accidentally replaced the original field descriptions for
supporting/contradicting evidence. These descriptions distinguish unresolved
counterevidence from ruled-out alternatives. Restoring that semantic contract is a
necessary fix; it must not auto-delete contradictory citations or fabricate a final
diagnosis. The 3.1.2 first qualification remains unchanged while its batch runs.
