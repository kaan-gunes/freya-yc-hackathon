# Second builder result - 2026-10-11

Status: versions 2, 3 and 4 failed PUB-01 for different identity-input bugs.
Follow-up compiler fixes and checks are in progress; no stable live pass is claimed.
Dates in this report use Europe/Istanbul. Artifact names use UTC.

## Code and checks

Code commits: `9b4764c` (`fix: keep phone decisions current and preserve test evidence`)
and `030cd23` (`fix: cover normal verification and bounded generator repairs`).
Follow-up commit `881bd1c` validates spoken identity dates and uses sparse repairs.
Commit `6482ae1` adds the pending-question request-context regression.
Commit `65ec36a` covers fresh identity dates in the general date input, with a
paired check that denies cached answers when all current speech is empty.
All 64 repository tests pass, and the builder self-check passes.
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
ISO date; account and record actions remain denied. The unit fixture has 44
independent checks; the total depends on the candidate's secondary actions.
A follow-up also checks the resolved request's sourced pending-question context,
so a canonical date cannot be sent under a different security question. Its
regression covers renamed API fields and operands. This change was made after
the next run started; that run uses the validator snapshot from `881bd1c`.

The latest fix consumes fresh full text when specialized identity inputs are
empty. It allows bounded punctuation and a simple pending-question answer prefix,
preserves numeric leading zeros, and requires a current suitable answer event.
Thirteen additional independent checks resolve the real verification request
for raw-text-only dates and codes, deny blank/cached phone answers, and block
empty/unknown/question events and third-party phone answers. Each date-format
probe clears every other current speech field, so a second canonical field
cannot hide a broken parser. The numeric fixture requires a leading zero but
has no global fixed length; a renamed six-digit question regression passes.

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

Run `20261010T224719208056Z` started from clean commit `881bd1c`. Its first
candidate passed 75 local checks (30 independent), Freya dry-run, publication of
version 3, readback and export. PUB-01 finished 0/1 in
`build-the-builder/results/20261010T225426517285Z-404df3cd`, simulation
`30c95712-c3ea-4a06-b9d6-330386d64d2d`, iteration
`d85bb021-a614-4dd5-ae33-2f8dd79c2a48`, call
`031fbd17-8345-4cba-b2e2-eda6cfef30d4`. All result reads and scoring completed.
The request-context check in `6482ae1` was added after this run started. Its
generated runtime was separately replayed in memory: the word birth date reaches
the date question with ISO formatting, and phone last-four reaches its own
question without date conversion. Those local fixtures put the answer in the
identity field. The live extractor instead put all 79 DOB replies in the general
date field, with the identity field empty. Decision code ignored that fresh date
and repeated the question. Replaying the actual first pre-decision state exactly
reproduced the failure; moving only its fresh date into the identity input reached
the correct verification request. No verification or promise API ran live.
The helper recorded 157 fallback-state route events (including listener routes
that still held the last decision status); replay found 79 failed decisions.
The next fix accepts that current date inside the guarded pending-date identity
path and tests the exact alternate-field shape, not only the normal fixture.
Its paired negative blanks all current speech and seeds the old canonical answer:
the real decision must still return to a listener without a verification action.

| Run | Result | Time | Published / live test |
| --- | --- | --- | --- |
| `20261010T212235494756Z` | Local validation stopped | 763.28 s | Neither |
| `20261010T214447691384Z` | Local validation stopped | 870.75 s | Neither |
| `20261010T220403404639Z` | Budget ended during test | 1800.01 s | Version 2; recovered PUB-01 0/1 |
| `20261010T224719208056Z` | Completed; gate failed | 664.02 s | Version 3; PUB-01 0/1 |
| `20261010T230434314580Z` | Completed; gate failed | 1359.46 s | Version 4; PUB-01 0/1 |

Run `20261010T230434314580Z` started from clean commit `65ec36a`. The first
candidate had four local errors. Its sparse repair changed only the failing
bank-flag initialization, close/confirmation manifests and a generated holiday
expectation. The full repaired candidate passed 76 local checks (32 independent),
Freya dry-run, version 4 publication, readback and export. PUB-01 completed 0/1
in `build-the-builder/results/20261010T231706550643Z-404df3cd`, simulation
`e50c8590-1ef3-4e3b-ab01-d75f8e6d1584`, iteration
`c36c054f-2d98-4e25-926c-5cd000b51c39`, call
`12d3ecc8-7f10-4540-bc7b-9ed35ed98d74`. Owned call metadata proves version 4.

All 79 DOB answers were extracted only as the current event and full speech text;
the identity-answer and general date fields were empty. The generated decision
consumed full text but never used it for identity. It repeated the question and
never called verification or recorded a promise. Exact local replay matches this
failure. The actual answers end with `.` (78 replies) or `._` (one reply); bounded
punctuation cleanup and guarded fresh-text fallback reach the correct request.
Synthetic phone probes show the same risk for a punctuated or prefixed last-four
answer. These are local probes, not live phone-stage evidence. Follow-up compiler
checks cover both raw-text-only paths and the blank/cached-answer boundary.
The helper reports 157 fallback-state route events, not 157 distinct decisions.
No schema-write rejection, extraction error or unmatched route was found.

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

Versions 2, 3 and 4 failed the first gate, so no three-repeat or full Brief A claim is made.
The next version must pass PUB-01 once, then three repetitions on the same
published version, then all ten Brief A cases and correction/split-answer styles.
Generated workflow files have not been edited by hand.

Open scope: A+B and multiple products, a separate LLM controller, and aggressive
history trimming. The date fixture currently assumes a sourced date security
question, as Brief A requires. Briefs with no date question need a source-backed
conditional check before claiming support. The current example bank key is used
for this development test with the user's approval; a shared private key is still
needed for team use.
