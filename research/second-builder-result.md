# Second builder result - 2026-10-11

Status: compiler changes and local checks are complete; the new live gate is pending.
Dates in this report use Europe/Istanbul. Artifact names use UTC.

## Code and checks

Code commit: `9b4764c` (`fix: keep phone decisions current and preserve test evidence`).
All 44 repository tests pass, and the builder self-check passes.
Follow-up checks add normal identity completion, supplementary decision tests
that cannot replace required guard tests, and three attempts within one deadline.

The compiler now requires every listening reply to pass through code, with a
fixed stage question and no semantic routing fallback or model bank tools.
Speech inputs are clearable strings. Code consumes each reply before choosing
a route and validates canonical dates against the call's `now`. The generation
rules cover completed identity recovery, exception priority during correction,
returning after an offer of help, and persistent hardship context.

The validator runs 22 independent checks over shared state. These cover valid
recording and duplicate prevention; invalid offers followed by yes; stale
readbacks; correction and fresh readback; negative/question replies; exceptions
with corrections; failed/unknown writes; retry limits; and identity recovery.
It also checks graph guard paths, unreachable actions, unconditional action
loops, secondary action guards, clearable speech fields, request bindings,
variable aliases, and real-clock aliases. Its Python checks define a supported
subset, not a general Python sandbox or proof of every business rule.

The test helper saves session, simulation, iteration and call IDs early. It
keeps execution, result reading and scoring separate, accumulates owned version
evidence, and supports read-only recovery:

```bash
bash scripts/test-agent.sh --resume build-the-builder/results/RESULT_FOLDER
```

Real Freya call metadata uses `assistantId`, `assistantEntityType: workflow`,
and `entityVersionNumber`. The helper checks these against the selected run and
agent. It rejects conflicting iteration ownership before scoring. Diagnostics
read direct errors, omit stale snapshots, and redact before truncating.
The recovered v1 call shows two schema-write error events, one failed extraction
and one unmatched route. Its ledger was not rescored.

## Build

```bash
bash scripts/build-agent.sh build-the-builder/briefs/brief-a.md \
  --openapi build-the-builder/tools/openapi.json --slot kaan-brief-a
```

Run `20261010T214447691384Z` had a clean source commit at start.
Its first candidate passed all 21 independent chains but failed the close-node
manifest, a bank-flag write restriction, and one generated question-route check.
The automatic repair fixed those failures. A supplementary decision test used
the invalid-amount category, which was restricted to an offer-guard node. The run
stopped at local validation after 870.75 seconds; it did not publish or test.
The follow-up keeps a mandatory offer-guard check and permits extra decision
checks without replacing it. A new independent normal-completion check also
catches an extra consent step when verified bank truth has stale local identity
state and cleared speech. Generation rules now cover that path explicitly.
No new version or score is claimed yet.

The earlier development run `20261010T212235494756Z` stopped at local validation
after 763.28 seconds. It exposed fixture-role and closing-hook contract issues.
Those issues were fixed in the compiler and validator. It did not publish or
start a simulation. Generated workflow files were not edited by hand.

Each builder run has a separate limit of 30 minutes, including its test. Later
development runs for repetitions and broader cases are outside that trace.

## Pending Live Evidence

The stable slot currently identifies agent
`404df3cd-803d-4656-89ac-ac122f9d31d2` and workflow
`e14dbbfa-9fd9-4bb0-9a4e-882897366f8d`. Publication, tested version, readback,
export, simulation IDs and official scores will be recorded here when known.

The gate is PUB-01 once, then three repetitions on the same published version,
then the ten Brief A cases and focused correction/split-answer styles.
String resets need actual platform evidence, not only dictionary checks.

Open scope: A+B and multiple products, a separate LLM controller, and aggressive
history trimming. The current example bank key is used for this development
test with the user's approval; a shared private key is still needed for team use.
