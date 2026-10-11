# Second builder result - 2026-10-11

Status: version 5 passed PUB-01 once and all three repeats without an update.
The ten-case Brief A run completed at 2/10. Payment-parser and spoken-year
follow-ups are source-only until the next build; no broader success claim is made.
Dates in this report use Europe/Istanbul. Artifact names use UTC.

## Code and checks

Code commits: `9b4764c` (`fix: keep phone decisions current and preserve test evidence`)
and `030cd23` (`fix: cover normal verification and bounded generator repairs`).
Follow-up commit `881bd1c` validates spoken identity dates and uses sparse repairs.
Commit `6482ae1` adds the pending-question request-context regression.
Commit `65ec36a` covers fresh identity dates in the general date input, with a
paired check that denies cached answers when all current speech is empty.
Commit `46b658c` verifies fresh full-text identity answers safely and generated
the tested version 5. Commit `cc9109d` adds the payment-parser follow-up.
All 79 repository tests pass, and the builder self-check passes after the bounded
GET transport-retry and spoken-date follow-ups.
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
ISO date; account and record actions remain denied. The unit fixture has 69
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

The payment follow-up adds current raw amount and trusted bank full-amount roles.
A current explicit "full amount" reference must resolve that bank amount, pass
readback and fresh approval, and bind the same amount in the real record request.
The speech decision cannot overwrite the bank fact. Empty/no events remain
denied. Currency-unit inputs pass both the current decision and shared offer
guard, which also handles confirmation corrections. Negative chains reject
non-finite, negative and zero values, plus arbitrary prose/date digit extraction.
These eleven added checks reproduce v5's payment re-ask bugs before publication.
Amounts fully written as words remain a safe request for an exact number; no
new number-word framework or dependency was added. No currency field is declared
in this Brief/OpenAPI; these probes cover the observed numeric "dollars" suffix,
not currency conversion or general multi-currency support.

Fourteen additional independent checks cover the wider batch's date failures.
Eight complete word-DOB probes use ordinal day words, grouped/cardinal word
years, optional "the/of" and hyphens through both identity and raw-text fields.
Two missing-year probes seed a cached answer, clear all other current speech,
and require a real listener without verification/account/payment actions.
Two positive payment chains send a weekday-plus-ordinal date through the current
decision and shared offer guard, then bind the original canonical date and exact
amount in the record request after fresh approval. Two wrong-weekday chains
remain denied even after a fresh yes. The generated fixture must supply a
canonical ISO proposed_date; no new metadata fields were added.
Six new repository tests include next-month resolution, ambiguous proposal
windows, malformed dates/prose, raw numeric-year mutations and cached-year
inference. Replaying v5 fails all eight word-DOB and both valid weekday probes,
while the paired missing-year/wrong-weekday negatives pass. This proves the old
parser gaps locally; it is not a new published score.

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
GET reads now retry recognized SSL EOF, timeout and connection-reset failures,
using the existing four attempts and 2/4/8-second backoff. POST, certificate,
DNS, authentication and malformed-JSON errors are not retried. Mock tests cover
recovery, exhaustion and permanent failures; the official client and scorer are
unchanged. These changes were committed as `ddd5858`.

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
| `20261010T234149659676Z` | Completed; gate passed | 640.39 s | Version 5; PUB-01 1/1 |

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

Run `20261010T234149659676Z` started from clean commit `46b658c`. Its first
candidate was rejected locally. A sparse repair corrected manifests, bank-flag
initialization, a noncanonical numeric fixture and an unsupported local regex
flag alias. The full candidate passed 99 local checks (45 independent), Freya
dry-run, version 5 publication, readback and export. The run including PUB-01
finished in 640.39 seconds, under its 30-minute limit. The official score was
1/1 in `build-the-builder/results/20261010T235144618977Z-404df3cd`, simulation
`46d61040-f487-4375-9422-73b209da2a6c`, iteration
`b24d8360-b067-45aa-8b1b-f3c72017360a`, call
`6b2beacf-4366-4d8f-8672-1de327fab99a`. Owned call evidence proves version 5.
Tools ran in the required order: two identity checks, account, one authorized
promise, then close. Current identity and confirmation strings were cleared;
no schema-write rejection, extraction failure or unmatched route was found.
This call used specialized identity fields. Replaying its exact fresh answers
with those fields blanked and only full text present reaches identical requests;
that is local replay, not direct live fallback-path evidence.

A separate run of the unchanged version 5 passed all three PUB-01 repeats in
`build-the-builder/results/20261010T235302576988Z-404df3cd` (347.70 seconds of
simulation time; 359.68 seconds wall time).
All execution, result reads and scoring completed, with owned version 5 evidence:

| Simulation | Iteration | Call | Result |
| --- | --- | --- | --- |
| `d715636d-5454-471c-b200-ee3f53b15561` | `de024fec-de70-479c-a3d4-0285efc38438` | `21706835-8048-4a41-98d0-4652e0dd0167` | Pass |
| `29a4b1d8-7359-48de-993c-1f0e47e030f7` | `c1bc3efc-8679-4473-b925-79d8646af9f3` | `b5dae0cc-3e07-4ccf-a3ae-adcc76afcb1a` | Pass |
| `4a5b0f65-6c01-4fb2-a387-25ad017612a9` | `d9583181-3b5e-42c2-958c-94e7cf53d204` | `0c78a9cc-ca91-4e7e-8be0-7024d90f20b3` | Pass |

The first call's post-DOB empty-input fallback is normal tool-result recovery,
not another caller error. Its full-amount words did cause one unnecessary payment
re-ask. The two slower repeats had 15 and 24 payment parse re-asks; identity still
completed in two answers. Most rejected amounts were numeric with a "dollars"
suffix (34 of 39), two were full-amount references, and three were number words.
No unsafe write or persuasion use occurred. Removing only the numeric suffix in
each actual pre-guard state reaches confirmation. The source follow-up addresses
the full-amount and unit-suffix faults; it has not yet generated a new live version.

The ten-case Brief A batch on unchanged version 5 completed at 2/10 in
`build-the-builder/results/20261010T235951416344Z-404df3cd`, simulation
`6e2fb6f2-91fe-4f1b-8e8e-aebcd238a71c`, iteration
`068733b5-861b-4260-9567-a644d9673bad`. PUB-03 (identity rejection budget)
and PUB-09 (restructuring transfer) passed. All execution, result reads and
official scoring completed, with owned version 5 evidence. An SSL EOF interrupted
the initial GET poll. Read-only resume recovered the same existing simulation;
no new sessions, personas or simulation POSTs were sent.

PUB-01 extracted full-amount references, numeric amounts with a dollar suffix,
then amounts in words. The guard's direct float conversion rejected them before
date handling. PUB-02 supplied "tomorrow morning" and a correctly extracted
11:00; the date qualifier caused two false invalid-window counts. PUB-07 supplied
"the week after next", then "Monday the 26th" 66 times. The vague-date matcher
missed the first phrase; the exact date parser rejected the second before the
calendar could offer the next business day. No schema-write or extraction error
was found for these three cases. Both payment loops ended at maximum duration,
retaining provisional service-error defaults despite successful bank reads.
They are parsing failures, not evidence of a bank outage. Generator follow-ups
cover the bounded raw date forms, clarification return, and honest service-error
state. These changes are not yet live evidence.

Five failures (PUB-04/05/06/08/10) gave the DOB entirely in words: ordinal day,
optional "the/of" and a named month, followed by a grouped spoken year. Some
used hyphens. The parser accepted only numeric day/year and also demanded four
raw year digits. Replay of the actual current state reproduces `incomplete_identity`;
the same state with only its fresh answer made canonical reaches verification.
The source follow-up requires a bounded complete spoken-date grammar and paired
missing-year denial checks, not a guessed year or a charge to the bank rejection
budget. No private identity values are copied into this report.

| Case | Call | Result / cause |
| --- | --- | --- |
| PUB-01 | `d4128471-f8d8-49c8-8e56-10c18c9cfb7c` | Failed; payment parsing loop, no promise |
| PUB-02 | `18a85d5a-0633-47d3-8294-9ab271b32d09` | Failed; valid callback reply not scheduled |
| PUB-03 | `415e1514-3e2d-4e63-8515-becc3fc4ebd7` | Passed |
| PUB-04 | `278cbf5d-afdf-4cd8-8289-5d0474df4e60` | Failed; spoken DOB loop |
| PUB-05 | `862b7cba-6550-492c-8c64-8ed8ddeb7a70` | Failed; spoken DOB loop |
| PUB-06 | `1efb32df-1e8f-4630-8889-22b66100acca` | Failed; spoken DOB loop |
| PUB-07 | `f3523a2b-864a-4d4e-b92c-c5bdb9e52616` | Failed; payment/date loop, no promise |
| PUB-08 | `91badbeb-d2e3-44b1-aedc-57ed0c8c3e0e` | Failed; spoken DOB loop |
| PUB-09 | `21e7a07f-b5e6-4310-9f5c-865ec59b31b5` | Passed |
| PUB-10 | `371a03c1-2915-4cc7-acd7-0a36978ed9fe` | Failed; spoken DOB loop |

## Historical v2 Evidence

The stable slot identifies agent
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

Versions 2, 3 and 4 failed the first gate. Version 5 passed once and three repeats.
Full Brief A and correction/split-answer styles are not yet claimed as passing.
The next source follow-up must be generated and pass the same first/repeat gates
before its broader test results can replace version 5's evidence.
Generated workflow files have not been edited by hand.

Open scope: A+B and multiple products, a separate LLM controller, and aggressive
history trimming. The date fixture currently assumes a sourced date security
question, as Brief A requires. Briefs with no date question need a source-backed
conditional check before claiming support. The current example bank key is used
for this development test with the user's approval; a shared private key is still
needed for team use.
