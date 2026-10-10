# Second builder result - 2026-10-11

Status: version 2 passed publication checks but failed PUB-01. Follow-up compiler
changes pass local checks; a new generation and live gate are next.
Dates in this report use Europe/Istanbul. Artifact names use UTC.

## Code and checks

Code commits: `9b4764c` (`fix: keep phone decisions current and preserve test evidence`)
and `030cd23` (`fix: cover normal verification and bounded generator repairs`).
Follow-up commit `881bd1c` validates spoken identity dates and uses sparse repairs.
All 56 repository tests pass, and the builder self-check passes.
Follow-up checks add normal identity completion, supplementary decision tests
that cannot replace required guard tests, and three attempts within one deadline.

The compiler now requires every listening reply to pass through code, with a
fixed stage question and no semantic routing fallback or model bank tools.
Speech inputs are clearable strings. Code consumes each reply before choosing
a route and validates canonical dates against the call's `now`. The generation
rules cover completed identity recovery, exception priority during correction,
returning after an offer of help, and persistent hardship context.

Version 2 passed 22 independent checks over shared state. These cover valid
recording and duplicate prevention; invalid offers followed by yes; stale
readbacks; correction and fresh readback; negative/question replies; exceptions
with corrections; failed/unknown writes; retry limits; and identity recovery.
It also checks graph guard paths, unreachable actions, unconditional action
loops, secondary action guards, clearable speech fields, request bindings,
variable aliases, and real-clock aliases. Its Python checks define a supported
subset, not a general Python sandbox or proof of every business rule.

Follow-up checks reject silent extraction consuming persuasion, and a relative's
identity answer after earlier first-party confirmation. Six new spoken-date
checks send month-name, ordinal, comma and case variants through the actual
decision and verification request. The resolved answer must be the same valid
ISO date; account and record actions remain denied. The unit fixture has 29
independent checks; the total depends on the candidate's secondary actions.
A follow-up also checks the resolved request's sourced pending-question context,
so a canonical date cannot be sent under a different security question. Its
regression covers renamed API fields and operands. This change was made after
the next run started; that run uses the validator snapshot from `881bd1c`.

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
That run produced no new version or score.

The earlier development run `20261010T212235494756Z` stopped at local validation
after 763.28 seconds. It exposed fixture-role and closing-hook contract issues.
Those issues were fixed in the compiler and validator. It did not publish or
start a simulation. Generated workflow files were not edited by hand.

Each builder run has a separate limit of 30 minutes, including its test. Later
development runs for repetitions and broader cases are outside that trace.
Up to three generation attempts share that deadline; failed candidates are not
published. Each repair keeps the same complete input files and validator errors.
Follow-up repairs return a sparse JSON merge patch. The assembled full candidate
still passes the same checks; raw patches and complete attempts are saved apart.

Run `20261010T220403404639Z`, from clean commit `030cd23`, passed 95 local
checks and Freya dry-run on its third candidate. It published version 2, verified
readback with no changes and exported the workflow. The test started late in the
run and its 30-minute budget ended before results arrived. A separate read-only
resume recovered the official score without starting another simulation. That
recovery does not make the original build complete within its deadline.

| Run | Result | Time | Published / live test |
| --- | --- | --- | --- |
| `20261010T212235494756Z` | Local validation stopped | 763.28 s | Neither |
| `20261010T214447691384Z` | Local validation stopped | 870.75 s | Neither |
| `20261010T220403404639Z` | Budget ended during test | 1800.01 s | Version 2; recovered PUB-01 0/1 |

## Live Evidence

The stable slot currently identifies agent
`404df3cd-803d-4656-89ac-ac122f9d31d2` and workflow
`e14dbbfa-9fd9-4bb0-9a4e-882897366f8d`. Owned call metadata proves tested
version 2. Its simulation is `593e7c3c-b38d-45a1-8d1d-bf42372a45db`, iteration
`9af1e2e6-d6f3-4e02-abd9-4ed36eeed55a`, and call
`4acedbfa-c26e-4559-9d8d-d3b1f837566a`.

Results are in `build-the-builder/results/20261010T223110315886Z-404df3cd`.
Trace and export are in `build-the-builder/out/20261010T220403404639Z`.
The completed summary is 0 of 1 passing. Execution, result reads and official
scoring finished. Only close_call reached the bank; no promise was recorded.
The caller answered the birth-date question 79 times. Extraction produced fresh
`D Month YYYY` strings, but the shared parser rejected that format and repeated
the question. Local replay of the actual pre-decision state reproduced it.
The fix requires parsing raw month-name dates in code, not trusting extraction
to normalize plain strings. Follow-up diagnostics expose direct current decision
fallbacks without copying raw identity speech into excerpts.

The call shows plain-string speech resets worked: no schema-write rejection,
failed extraction or unmatched route was found. Payment confirmation resets were
not reached, so that part still needs live evidence. A wrapper path fix allows
the documented repository-relative resume command; its regression covers resume
and custom case paths.

Version 2 failed the first gate, so no three-repeat or full Brief A claim is made.
The next version must pass PUB-01 once, then three repetitions on the same
published version, then all ten Brief A cases and correction/split-answer styles.
Generated workflow files have not been edited by hand.

Open scope: A+B and multiple products, a separate LLM controller, and aggressive
history trimming. The date fixture currently assumes a sourced date security
question, as Brief A requires. Briefs with no date question need a source-backed
conditional check before claiming support. The current example bank key is used for this development
test with the user's approval; a shared private key is still needed for team use.
