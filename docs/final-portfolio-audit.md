# Final portfolio / interview delivery audit

Scope: communication, navigation, interview materials, reproducibility and release
auditing. No Sentinel core capability, new model benchmark or frozen result change.

## First-time reader assessment

| Time available | Entry | What a reader can learn |
|---|---|---|
| 30 seconds | README first screen / Overview / 30-second pitch | Checkout incidents → actual tools → evidence → root cause → sandbox-tested candidate. Recorded mode and 7/8 small sample are explicit. |
| 3 minutes | Three-minute pitch + Architecture + Root cause | What the six services do, how Hybrid/Tool Calling uses evidence, why a candidate remains review-only. |
| 5 minutes | Timed click-through script | One real investigation, retained errors/recovery, code evidence, tests, and unsuccessful benchmark outcomes. |
| 10 minutes | Technical demo + depth map | Runtime, context, budget, checkpoint, Ground Truth boundaries, Critic defects and costs. |

The initial README put the key results below a large screenshot; compact results
and the distinction between 189 benchmark-time tests and current 267 + 17 regression
tests now precede the image. Evaluation now places a numerator/denominator beside
every displayed root/service accuracy percentage. Its underlying records are untouched.

Documentation offers three initial paths and an expandable full library, avoiding
a wall of equally weighted links. Recruiter and developer paths are explicit in
README. Fifty-six historical outcomes and V3/V3.1 failure labels remain visible.

## Interview materials

Separate 30-second, one-minute and three-minute scripts; a five-minute guide with
click/observation/narration at every step; ten-minute technical walkthrough; four
interviewer depth levels; 49 core Q&A and 24 hard questions; Chinese/English resumes
with four bullets each and a separate three-bullet version; actual stack, architecture
cheat sheet, STAR failure story, limitations and future work marked unimplemented.

## Acceptance evidence

Machine-readable final execution results are retained under `artifacts/phase5/`:
`backend-interview.json`, `frontend-interview.json`, `browser-interview-final.json`,
`demo-dry-run.json`, `offline-runtime.json`, `public-security-interview.json`,
`clean-start-interview.json` and repository release audit. Each report records its
own result; earlier failed attempts and original releases remain retained.

The final run passed **267 backend tests** (49.87 seconds, one dependency warning),
**17 frontend tests**, **37 browser checks** and **42 actual public HTTP checks** plus
container assertions. A separate eight-step dry run follows the actual
five-minute document, including a complete 4× replay. Its browser action duration
does not measure a human's spoken narration; the five minutes are the script budget.
The complete replay took about 14 seconds at 4×; all scripted browser actions took
about 17 seconds, with zero external requests, writes, console or resource errors.
An initial browser assertion matched two valid README demo links; selecting the first
resolved that harness ambiguity. Its failed report is retained, not overwritten.

Offline has a precise scope: prepared Docker image + local browser/assets; no model
key or external network API. First image/dependency download still requires preparation.
The final source ZIP does not bundle Docker itself or its images. An actual
`--network none` container without `.env` or API key served 18 page/API/asset paths
and all 19 evidence records. A separate isolated clean-clone Compose build/start
also passed; the main lab was not removed or reset.

## Publication boundary

Source and interview ZIPs have separate SHA256/file manifests. They exclude `.env`,
private original archives, local test outputs, caches and installed dependencies.
Public records are genuine sanitized projections with source hashes. Scanner scope
is configured secret values, common token forms, local outputs/ZIPs and available Git
history, plus visible personal paths and relative links; it is not universal secret
detection. The repository has no historical commits to inspect at this stage.

## Limits that remain visible

Eight authored scenarios, one cloud model, high input-token use, wrong retry-storm
root cause, same-model Critic with evidence omission, visible experiment helper,
four constrained patch profiles and a shared sandbox kernel. All final Critic
verdicts are PARTIALLY_VERIFIED. No generic candidate was deployed. No public domain
or GitHub repository has been published by this task.

Noncritical future improvements are listed in [Future Work](future-work.md), not
implemented. [Final status](../FINAL_STATUS.md) gives the startup and presentation path.
