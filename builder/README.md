# First builder

This builder reads the supplied brief files and OpenAPI. It uses the local Codex
CLI login with GPT-6.1-Sol to create a fresh policy, portable Freya workflow, and guard checks.
It uses Python's standard library. The phone model stays as `freya.AGENT_LLM`.

The first target is Brief A and PUB-01. Multi-product support is the next stage.
The source rules and any missing support are listed in each generated policy.
Local guard checks are not a live test score.

## Run

Install Python 3.10 or newer and the Codex CLI, then run `codex login`.
The local CLI must support `exec --ignore-user-config`.

From the repository root:

```bash
# Generate and check locally. No Freya key is needed.
bash scripts/build-agent.sh build-the-builder/briefs/brief-a.md \
  --openapi build-the-builder/tools/openapi.json --offline

# Generate, validate, publish, read back, export, and test PUB-01 once.
# build-the-builder/.env (or env.sh) must contain both team keys.
bash scripts/build-agent.sh build-the-builder/briefs/brief-a.md \
  --openapi build-the-builder/tools/openapi.json --slot kaan-brief-a
```

Each run has a real wall-clock limit, at most 30 minutes, including model work
and tests. Use the same slot to update the same workflow. The baseline is kept.
Up to two automatic repairs are allowed after local or Freya check failures,
within the same deadline. No failed candidate is published.
All call code and policy are inside the workflow; no local server is needed.

After the first real test passes, run three repeats against that same published
agent. This is a separate development test, so it does not extend a build's limit:

```bash
bash scripts/test-agent.sh AGENT_ID --only PUB-01 --reps 3
```

Only one simulation may run in the shared workspace. Tell the teammate before
publishing or testing. The local builder lock stops two local builds; it cannot
lock another computer or the dashboard. Do not update an agent during a test.

## Outputs and checks

`build-the-builder/out/<run>/` holds the input record, `policy.json`,
`workflow.json`, `checks.json`, `validation.json`, trace and run metadata.
Online runs also keep the server export and published workflow/agent/version IDs.
The trace records the builder model, purpose, timing, source hashes and test state.
The code revision includes whether the worktree has changes. Full model reasoning
is not stored. Generated artifacts are local and ignored by Git.

The local validator checks stage boundaries, API fields, Python syntax, and
executes generated guard examples with restricted Python. It also runs its own
expected checks on shared state across offer, readback, approval and record.
These cover valid recording, rejected offers followed by yes, changed offers,
corrections, mixed exceptions, duplicate writes, failed/unknown writes, retry
limits and returning from completed identity. Synthetic fixture inputs and
variable roles come from the candidate; expected safety rules come from code.

The graph checks require offer/readback guards on record paths, reachable actions
and terminals, and reject unconditional action loops. Callback, transfer and
note actions need code guards and trusted request fields. Python checks allow
direct variable reads and literal-key writes, block variable-table aliases and
real-clock aliases, and forbid request changes in pre-hooks. Only the final
close hook may replace its outcome/reason body fields. These are supported-code
checks, not a general Python sandbox or proof of every business rule. Time and
calendar behavior still needs source checks and live cases.

Listening nodes route every reply through code. They have no model tools or
semantic routing fallback. Code consumes and clears plain string speech fields,
handles exceptions, and selects the exact stage question. This local schema
check does not prove the platform accepted each reset. Freya dry-run, readback,
export and live call diagnostics provide separate evidence.

Failures stop the run with a visible report. A missing key or an unfinished test
is reported as not run or incomplete, with no invented score. Never copy secrets
into prompts, reports or Git. `.env` and `env.sh` stay local.

The test helper saves session, simulation, iteration and call identities as soon
as they arrive. Its summary separates call execution, result reads and scoring.
Each successful metadata source adds version evidence. Call versions use
`entityVersionNumber` only for calls matched to this simulation and agent;
dashboard versions are not test evidence. Call diagnostics expose rejected
state writes, extraction errors and unmatched/fallback routes.

If a read fails after a simulation was created, resume the saved run:

```bash
bash scripts/test-agent.sh --resume build-the-builder/results/RESULT_FOLDER
```

Resume uses saved bank sessions and only reads the known simulation. It does not
repeat writes. An unknown create result without a simulation ID cannot be
resumed automatically. Incomplete ledger reads have no invented score.

## Next checks

First verify PUB-01 once and three times. Then test all Brief A cases, correction
and split-answer styles, and modified synthetic brief inputs. Complete A+B rules
before claiming multi-product support. Keep official scoring expectations unchanged.
