# Generic candidate repair

The engine chooses a profile from a cited source path, never a scenario ID. Supported
business modules are pricing (`total`), payment (`normalize_amount`), order
(`choose_item`) and inventory (`normalize_product`). Transport, database writes,
cache policy and the fault controller remain outside candidate code. This is a
generic capability for a deliberately bounded set of pure business functions,
not arbitrary repository repair.

The final proposal format asks DeepSeek for complete replacement source. The
controller computes a unified diff against the immutable actual base without
changing the model's logic. Static validation checks the exact path, signature,
defaults, annotations, AST constructs and callable allowlist. One proposal may
change one file, with at most two patch attempts. Imports, attributes, loops,
private names, nested functions and arbitrary calls are forbidden. Tests, secrets,
benchmark data, scoring, fault scenarios and infrastructure files are protected.

Patch eligibility explicitly distinguishes CODE_PATCH, CONFIG_CHANGE,
INFRA_REMEDIATION and NO_AUTOMATIC_REMEDIATION. An unsupported or uncited file fails
closed. Configuration and infrastructure recommendations remain manual. Risk
records changed lines, files, API compatibility, database, concurrency, security
and infrastructure impact. Financial edits are HIGH risk. All generic candidates
have automatic apply disabled and cannot use the legacy live pricing overlay.

## Real candidate environment

Each baseline and candidate replay starts three HTTP processes for order, inventory
and payment. Trusted wrappers execute real parameterized PostgreSQL statements,
Redis GET/SET/TTL and Kafka produce/consume. Every replay gets its own PostgreSQL
schema, Redis namespace and Kafka topic. The controller cleans up only these
generated names. Workers have CPU, memory and file-size limits and run as the
container's non-root user. They receive dependency credentials, but no LLM key;
the AST-constrained functions have no capability to inspect the environment or I/O.

Workers share the Sentinel container/kernel. This is not a VM boundary for arbitrary
hostile Python. Profiles, selected candidate source, dependency options and request
count are configurable within the trusted controller. No real payment processor or
external production service is contacted.

Actual acceptance contracts cover the existing null-discount crash, invalid payment
amounts, empty catalogs and invalid catalog records. The latter three are additional
component checks, not replacements for the eight Fault Lab scenarios. Rejecting an
invalid amount or catalog may increase 4xx/503 responses; the report separately
measures business-contract violations and HTTP 5xx rather than presenting rejection
as a latency/error-rate improvement. A healthy checkout must also succeed, write
order/payment rows and publish an observed Kafka event.

## Retained measurements

The first diff-format real DeepSeek probe passed 2/4 components. Pricing and order
passed. Payment failed malformed diff syntax and unsupported `Try`; inventory
failed hunk counts and the single-file rule. Failed model proposals were recovered
from their durable structured-output checkpoints and saved separately. These are
real failures, not overwritten results.

After 165 passing tests, the source-format follow-up passed 4/4 using 10,393 actual
provider tokens. Pricing/payment/order passed their first proposal; inventory's
first proposal used unsupported `Try`, and its second passed. Every success
includes real immutable contracts plus baseline/candidate HTTP replay with scoped
PostgreSQL, Redis and Kafka dependencies. Artifacts:

- `evaluation/phase4/generic-patch-provider-probe.json`
- `evaluation/phase4/generic-patch-failure-details.json`
- `evaluation/phase4/generic-patch-provider-probe-source.json`

These are **patch component verification**, not end-to-end RCA accuracy. The manually
written candidate in the protocol test suite is explicitly `TEST_FIXTURE`; actual
provider probes are `AI_GENERATED`. No candidate has been applied to business source.

The frozen evaluator's `patch_generation_attempts` field counts legacy patch-tool
invocations. It can be zero for a real generic candidate. Generic attempts must be
read from PatchGenerator provider calls, runtime attempt state and persisted patch
artifacts, not inferred from that legacy counter. The scorer is not silently changed
to repair a historical reporting field.

## Version boundary

Business-function extraction happened after the immutable V4 first controlled
experiment. The previous business source is preserved byte-for-byte in the V1
benchmark's `business-source.zip`. Only `services/app.py` changed among its eight
protected files at this stage; scenario, truth, evaluator, pricing contract and SQL
definition remain unchanged. The final release is sealed in
`evaluation/benchmarks/sentinel-benchmark-v2/manifest.json`, with 14 protected files,
the same ground-truth version and six byte-identical scenario/grading/contract files.
It does not claim byte-for-byte reproduction of the old business image.
