# Deep Research Agent - v2 Design

Status: proposed
Scope: two phases, A (pipeline correctness) then B (research depth)

## Context

The deployed system works: ALB → FastAPI → Step Functions → SQS → ECS worker →
`deepagents` (Gemini + Tavily) → S3 + DynamoDB → EventBridge → SNS. The delivery
plumbing is solid. The research behaviour it carries is not: a single static
system prompt (`src/agent.py:31`) and one snippet-level search tool
(`tools/search.py`), invoked in one flat loop.

Two problems block progress, in this order:

1. The pipeline has correctness gaps that only stay hidden because throughput is
   one job at a time on one worker. Any attempt to make research *deeper* makes
   runs *longer*, which triggers those gaps immediately.
2. The agent uses roughly a fifth of the framework. `create_deep_agent` accepts
   `subagents`, `middleware`, `response_format`, `checkpointer`, `store` and
   `interrupt_on`; `src/agent.py:57` passes none of them.

Phase A is therefore not optional prep work. Longer runs are the direct
consequence of Phase B, and the current worker cannot survive them.

## Goals

- A job that takes 15+ minutes completes exactly once, with truthful status
  visible to the caller throughout.
- Reports are grounded in full source documents, with citations that are
  verified to exist rather than requested in a prompt.
- Failure is terminal when it should be, retried when it should be, and never
  silently expensive.

## Non-goals

- Multi-tenancy, user accounts, or a UI.
- Replacing `deepagents` with a hand-rolled graph. We configure it, not fork it.
- Region/account portability beyond removing hardcoded defaults.

---

# Phase A - Pipeline correctness

## A1. Job lease and visibility heartbeat

**Problem.** `src/worker.py:18` receives with a 300s visibility timeout and never
extends it. A multi-subagent research run will exceed five minutes, SQS
redelivers, and a second worker starts the same job. The only guard is
`src/worker.py:40`, which skips on `COMPLETED` but not on `RUNNING`, so nothing
stops the duplicate.

**Design.** Two cooperating mechanisms, because SQS visibility alone cannot
express "someone is actively working on this".

*Lease in DynamoDB.* Add `lease_owner` (worker task ID), `lease_expires_at`
(epoch seconds) and `attempt` to the job item. New functions in `helpers/jobs.py`:

```python
def acquire_lease(job_id: str, owner: str, ttl_seconds: int) -> bool
def renew_lease(job_id: str, owner: str, ttl_seconds: int) -> None
def release_lease(job_id: str, owner: str) -> None
```

`acquire_lease` is a conditional update that succeeds only when the job exists,
is not `COMPLETED`, and either has no lease, has an expired lease, or the lease
is already ours. On `ConditionalCheckFailedException` the worker logs
`job_lease_held` and returns *without deleting the message* - a live owner has
it, and the message will redeliver later if that owner dies.

*Heartbeat.* A daemon thread started before the agent invoke, ticking every
`visibility_timeout / 3` seconds, doing two things: `ChangeMessageVisibility` to
push the SQS deadline out, and `renew_lease` to push the DynamoDB deadline out.
Stopped via a `threading.Event` in a `finally` block. Add to `helpers/queue.py`:

```python
def extend_visibility(receipt_handle: str, timeout: int, *, queue_url: str | None = None) -> None
```

The heartbeat is bounded by the wall-clock budget from A4, well under the SQS
12-hour ceiling on cumulative visibility.

**Testing.** `moto` for SQS and DynamoDB. The key test races two workers against
one message and asserts the agent is invoked once. A second test kills the
heartbeat mid-run and asserts the lease expires and a second worker can claim it.

## A2. Failure classification

**Problem.** Every failure is treated identically. A missing `TAVILY_API_KEY` or
a malformed question burns three full LLM runs before reaching the DLQ
(`src/worker.py:73` never deletes the message). Separately, `src/agent.py:132`
calls `mark_failed` on attempt one, so DynamoDB reports `FAILED` while two
retries are still pending - the API lies to the caller.

**Design.** A new `helpers/errors.py` with `PermanentError` and `TransientError`,
and a `classify(exc)` function mapping known cases: missing config, validation
failures, provider content refusals and "agent produced no report" are permanent;
throttling, 5xx, and network timeouts are transient. Unknown exceptions are
treated as transient until the attempt count is exhausted.

Worker behaviour becomes:

| Case | DynamoDB | SQS |
|---|---|---|
| Permanent | terminal `FAILED` | delete |
| Transient, attempt < max | `QUEUED`, record `last_error` + `attempt` | `ChangeMessageVisibility` to a backoff delay |
| Transient, attempt == max | terminal `FAILED` | leave; next receive redrives to DLQ |

Setting visibility explicitly on transient failure replaces the current
"wait out the full 300s" behaviour with real exponential backoff.

**Also.** Remove the `mark_failed` call from `run()` in `src/agent.py`. Job state
transitions belong to the caller that owns the retry policy, not to the agent.
`run()` raises; the worker decides what that means. The CLI path gets its own
small handler so behaviour there is unchanged.

## A3. DLQ reconciliation

**Problem.** Nothing consumes the DLQ. A job that exhausts its retries sits at
`QUEUED` or `RUNNING` forever from the caller's point of view.

**Design.** A Lambda with the DLQ as an event source: mark the job terminally
`FAILED` with `dlq: true`, emit a `ResearchDeadLettered` event, delete the
message. Plus a CloudWatch alarm on DLQ `ApproximateNumberOfMessagesVisible > 0`
into the existing SNS topic.

A2 already marks the record `FAILED` before the redrive, so this is a
belt-and-braces reconciler for the cases A2 misses (worker OOM, task eviction).

## A4. Budget and timeout guards

**Problem.** Nothing bounds a job. No wall-clock limit, no tool-call cap, no
token or cost ceiling. A runaway loop is discovered on the bill.

**Design.** Three independent limits, each with a metric:

- Wall clock: `MAX_JOB_SECONDS` (default 900), enforced by a watchdog around the
  agent invoke, raising `PermanentError` on breach.
- Graph depth: pass `recursion_limit` in the invoke config.
- Tool calls: a counter in the tool wrapper, raising once `MAX_TOOL_CALLS` is hit
  so the agent is forced to synthesise from what it has.

Token and cost accounting is captured per run and written to the job record, so
cost per job becomes queryable rather than inferred.

## A5. Job-scoped staging (prerequisite for concurrency)

**Problem.** This one is easy to miss and blocks everything after it.
`helpers/reports.py:13` defines a single global staging path,
`reports/report.md`. `src/agent.py:96` calls `clear_staging()` at the start of
every run, and `src/agent.py:61` roots `FilesystemBackend` at the shared
`REPORTS_DIR`. Two jobs in one process delete each other's work in flight. The
system is single-threaded by accident, not by design.

**Design.** `run()` takes a `workdir: Path | None`. The worker passes a per-job
directory; the `FilesystemBackend` is rooted there; `finalize_local_report` reads
from it; a `finally` block removes it. `clear_staging()` goes away, since there
is nothing global left to clear.

This is a prerequisite for concurrent workers *and* for B3, where subagents each
write intermediate files.

## A6. Config hygiene and autoscaling

**Config.** `helpers/config.py:23-32` hardcodes bucket names, queue URLs and ARNs
containing account `139675292967` as silent fallbacks. A misconfigured deploy
targets the wrong account instead of failing. Replace with a `Settings` object
resolved once at startup, where infrastructure identifiers are required and
missing ones raise immediately. Pin dependencies in `pyproject.toml` while here -
builds are currently not reproducible.

**Autoscaling.** Both services are pinned at one task. Add target tracking on
backlog per task (SQS `ApproximateNumberOfMessagesVisible` divided by running
task count), target around 2, min 0, max N. Safe only after A1 and A5, which is
why it sits at the end of Phase A.

## Phase A exit criteria

- A deliberately slow 15-minute job completes exactly once, no redelivery.
- Two workers racing one message invoke the agent once.
- A missing API key fails terminally on attempt one, with no LLM call.
- No job can remain in a non-terminal state after the DLQ reconciler runs.
- Scaling to three workers processes three jobs concurrently without collision.

---

# Phase B - Research depth

## B0. Minimum measurement (small, but do it first)

Phase B changes output quality, which is invisible to the current metrics. The
thin slice needed to avoid flying blind: enable LangSmith tracing (`deepagents`
is LangGraph underneath, so this is env-var configuration) and write ~20 golden
questions with a scoring script covering citation validity, coverage and
factuality. Not a full eval platform - just enough that each step below can be
shown to help rather than assumed to.

## B1. Full-text reading

**Problem.** `tools/search.py:15` defaults `include_raw_content=False`, so the
model reasons over one-paragraph Tavily snippets. This is the hard ceiling on
report quality, and no prompt change moves it.

**Design.** A `read_url(url, offset=0)` tool alongside search: Tavily Extract
with a `trafilatura` fallback, returning cleaned text in token-budgeted pages so
the agent can continue through long documents deliberately. Responses cached in
S3 under `cache/pages/<sha256>.json` with a TTL - this cuts cost, and it makes a
run reproducible, which B0 needs.

Search itself gains date-range and domain include/exclude parameters.

## B2. Source registry and structural citations

**Problem.** Citations are a prompt request (`src/agent.py:40`), so the model can
and does emit plausible URLs it never visited.

**Design.** A per-job source registry in `helpers/sources.py` assigning stable
IDs (`S1`, `S2`, ...) to every retrieved result, storing URL, title, retrieval
timestamp and content hash. Tools return IDs; the prompt requires `[S3]`-style
citations.

A validator then runs before the report is accepted: every cited ID exists in
the registry, every findings subsection carries at least one citation, and no
bare URL appears that is not registry-backed. On failure the agent gets one
repair turn. The registry is persisted to S3 next to the report.

This is what makes the output trustworthy enough to show anyone, and it is the
precondition for B5.

## B3. Planner, parallel researchers, synthesizer

**Problem.** One flat loop over one question is what makes this a research agent
rather than a deep research agent. Coverage is shallow and a single context
window absorbs every search result.

**Design.** Use the `subagents` parameter. The top-level agent plans - decomposing
into four to six sub-questions - then dispatches a `researcher` subagent per
sub-question, each with search and read tools and its own isolated context, then
synthesises. Subagent count and per-subagent tool budget are capped under the A4
limits.

Each subagent completion is a natural progress event, which feeds B6.

## B4. Structured output

**Design.** A Pydantic `Report` model via `response_format`: title, summary,
`findings[{claim, confidence, source_ids}]`, open questions, sources. Both
`report.md` and `report.json` land in S3.

Markdown is for humans. The JSON is what lets the API return real data, lets two
runs of the same question be diffed, and lets B0 score quality automatically.

## B5. Verification pass

**Design.** A critic pass over the assembled report using a cheaper model: for
each finding, check entailment against the cached source text for its cited IDs
(available because B1 caches and B2 maps IDs to content). Unsupported claims are
struck or downgraded in confidence, then one repair pass runs.
`RubricMiddleware` from `deepagents` is the natural home for this.

## B6. Progress and retrieval

**Design.** Persist LangGraph step events to the job record so
`GET /research/{job_id}` returns a phase and current activity instead of a bare
`RUNNING`. Return a presigned URL rather than the raw `s3://` URI, which clients
cannot fetch today. Add an idempotency key to `POST /research` so the same
question is not researched twice.

---

# Sequencing

```
A5 ─┬─> A1 ──> A2 ──> A3 ──> A6        (Phase A)
    │
    └─> B1 ──> B2 ─┬─> B3 ──> B4 ──> B6   (Phase B)
                   └─> B5
        B0 alongside, before B1 lands
```

Dependencies worth stating explicitly:

- **A5 before everything.** Shared staging state makes concurrency impossible, so
  it gates both the rest of Phase A and the subagents in B3.
- **A1 before A6.** Autoscaling without leases turns one duplicate-processing bug
  into N.
- **B1 before B3.** Parallel researchers are only worth their cost if each can
  read deeply; fanning out over snippets multiplies a weakness.
- **B2 before B5.** Verification needs a mapping from claim to cached source text.
- **B0 before B1.** Otherwise every subsequent step is a vibe check.

Phase A is mostly mechanical and independently testable with `moto`. Phase B
changes behaviour and needs B0's eval set to evaluate honestly.

# Risks

- **`deepagents` churn.** The subagent and middleware APIs are young. Pin the
  version (A6 covers this) and keep our wrapper thin enough to re-target.
- **Provider rate limits.** Parallel subagents multiply concurrent Gemini calls.
  Needs a shared limiter and retry budget, not just per-call retries.
- **Cost growth.** Full-text reading plus subagents plus a verification pass is
  several times the current per-job cost. A4's accounting must land before B3, or
  the increase is invisible until billing.
- **Tavily quota.** Same shape; the B1 cache is the main mitigation.
