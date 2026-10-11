# V7 conversation fixes in the builder

11 October 2026, Europe/Istanbul. This is a developer report, not a new independent review.

Generation source: [`8a95ace`](https://github.com/kaan-gunes/freya-yc-hackathon/commit/8a95acea3615f921445ec033254098b70c481f3f).
Final local closing check: [`cc09a5f`](https://github.com/kaan-gunes/freya-yc-hackathon/commit/cc09a5f936cd224ebdbd21edd59dc3b27c896b74).
**Status: the source changes are delivered, but no complete valid candidate is ready.**
The one allowed offline repair stopped at validation: **203/207** checks passed.

Starting HEAD was `fb91544`; `origin/main` matched before work. The last independent
review remains HEAD `650dcbe`, application source `eb7fc1e`. `PROJECT_CONTEXT.md`
and that review marker were not changed.

## Four causes and changes

| Cause | Builder contract/check change | Local evidence |
| --- | --- | --- |
| The payment parser required digit days, even though the DOB parser accepted words. | The generation contract reuses the bounded cardinal/ordinal day grammar in payment month and weekday forms. Call `now` resolves month/year. The same deadline and business-day guard still runs. DOB still needs a year. | New independent raw-date probes go through both current speech and the shared offer guard, then inspect the real canonical promise request. Synthetic dates vary the month, day, year boundary and weekday. Impossible days, wrong weekdays and extra prose are rejected. A digit-only parser mutant fails. |
| One event label lost support decline, a plan request or an AI question in a mixed reply. | The contract requires stage-specific extraction of current full speech, support decline and restructuring before ordinary question/offer branches, clear negation handling, and an AI answer that keeps the current offer. | The same fresh text is checked with question, wrong and empty events. Tests reject a shadowed support decline, a lost plan request, false plan transfers and a lost AI answer. Pre-identity cases cannot reach bank actions. Existing hardship/voluntary-offer checks remain. |
| Question answers appended the old minimum/support offer. | The contract requires a bank-floor answer without another offer. Missing text must ask for the question without guessing or spending an offer. It keeps the once-only floor rule and the allowed second persuasion exception. | Tests inspect actual TTS and unchanged bank/offer/persuasion state. A follow-up with no current text cannot reuse the earlier minimum question. A repeated-offer mutant fails. |
| A blank terminal prefix or a timeout before setup left speech variables unresolved. | Normal farewells are literal. Special source text and successful-record/SMS speech remain. Code fallback edges reach a literal retry listener with no tools, then the guarded decision. The helper reports code-execution timeouts. | Tests reject unset/blank spoken placeholders and a variable-based timeout listener. The timeout test does not execute the snippet. A delayed farewell is also checked after the successful-record listener. The saved timeout produces `code_execution_failure`, without raw speech in diagnostics. |

The edits are in the builder prompt, independent validator checks, build runner
and test helper. The old generated workflow was not edited. No new dependency,
model, separate LLM controller, cache framework or A+B work was added. Existing
bank verification, approval, action guards and write-retry checks remain.

## Local checks

- Affected checks: `python3 -m unittest tests.test_v7_conversation tests.test_build_agent tests.test_test_agent tests.test_focused_conversation tests.test_focused_approval_retry -q`: **56/56**, **87.012 seconds**.
- After the final delayed-farewell check, `python3 -m unittest tests.test_v7_conversation -q`: **5/5**, **18.928 seconds**. These overlap the earlier tests; they are not 61 distinct tests.
- Builder `self_check()` and `git diff --check`: passed.
- Runner mocks prove one model call, complete merge-patch validation, no remote calls, unchanged seed bytes, one deadline and a failed-candidate stop. Changed brief/API/platform sources and unchanged-resume with a changed prompt are rejected.

The original complete seed fails all six new word-day probes. A separate local
replay adds only synthetic policy input declarations in memory; its workflow code
stays unchanged. It also fails the minimum-answer, mixed-intent and literal-retry
checks, including the final empty farewell after a successful record. The archived
real `code_exec` timeout also produces exactly one helper diagnostic. This is
negative evidence, not a patched delivery candidate. The original seed SHA256 remains `e7f55259dd18f20518e67886267c2e4aaefeb533dcc50081008b7b3aaa4af6fd`.

## One offline model repair

```bash
python3 scripts/build_agent.py build-the-builder/briefs/brief-a.md \
  --openapi build-the-builder/tools/openapi.json --slot kaan-brief-a \
  --offline --repair-build build-the-builder/out/20261011T105328711505Z \
  --budget-seconds 1800
```

Run: `build-the-builder/out/20261011T140530260392Z/`.
Time: **17:05:30–17:13:02**, **451.70 seconds**, within the 1800-second budget.
This is builder execution time, not an estimate of the user's total work time.
The model was the existing default `gpt-6.1-sol`; the phone model was not changed.
The manifest records source `8a95ace`, `code_dirty=false`, `offline=true`,
`live_test.status=not_run`, exactly one merge-patch generation attempt and final
status `incomplete`. The trace records seed-for-model-repair and model begin/end;
it has no unchanged-reuse, Freya validation, save, publish or test events.

The old draft was only the starting point for automatic model repair. The ordered
brief/API/platform sources and slot still matched exactly. The current compiler
prompt was the allowed changed input. Its SHA256 is
`6a88b1f450e16975630df637e92d0bcfb0f6abb05c1add543bd35ba07c376850`.
The original seed file stayed unchanged.

The model returned a full assembled candidate after its merge patch, at
`candidate-attempt-1.json`. SHA256:
`5f2691d3699c456c2dac20ccd1e980c981697b9a0d165af73da860b36705e77b`.
Provenance passed **47/47** source rules. Validation passed **203/207** and stopped
before any remote action. A separate final read-only validation with source
`cc09a5f` gave the same four failures in **4.962 seconds**; the added delayed
farewell/SMS check passed. The candidate bytes did not change.

The real blockers are:

1. `unknown_opening_first_answer`: fresh `Hello?` with an empty event is changed
   into a generic question by a broad question-mark check. The generated check
   expects only the party question; code adds an unasked information reply.
2. `independent_minimum_answer_wrong`: current "What is the minimum payment?"
   with event `no` still takes the refusal/persuasion path. Raw-question recovery
   and the bank-floor answer remain limited to selected event labels.
3. `independent_support_decline_polite_question`: "No, thanks. Is there a discount?"
   at pending support is not recognized as a decline. The generated decline
   regex requires an explicit transfer/support phrase; the question shadows it.
4. `independent_ai_with_current_offer_offer`: a current yes/offer with an AI
   question keeps the amount/date but loses the AI answer. The generated code
   only forwards the answer prefix when its normalized event is exactly `offer`;
   this yes path reaches readback without that answer.

The current model output therefore does not fully fix the mixed-intent and
question-answer groups. The gates correctly reject it. It was not hand-patched,
reused as a valid candidate or sent to Freya. No second generation/repair loop was
started.

The generated word-day parser passed all six new independent raw-date probes.
Seven additional checks against this exact generated offer guard passed: four
complete raw word dates across March, September and a year boundary; an impossible
word day, a wrong weekday and trailing prose. They used raw inputs, not canonical
inputs presented as parser evidence. First-code timeout, resolved normal farewell,
source-required SMS, hardship and permitted-retry checks also passed locally.
These successes do not make the full rejected candidate ready.

## Live boundary and remaining scope

No Freya dry-run, publish, chat turn, bank session or simulation was started.
The unpublished v8 dashboard draft was not read or changed. There is no new live
score. The reviewed v7 score remains **4/10**; it is not evidence for this change.
PUB-10's official FAIL is unchanged. The scorer and mandatory call-recording
opening are unchanged; the allowed retry and one successful promise are still
covered by the existing local checks.

Raw candidates, model output, call evidence, hashes and logs remain under ignored
`build-the-builder/out/` and `build-the-builder/results/`. Keys and raw speech are
not committed. Portable test code and this readable report are the Git delivery.
New live validation is a separate next stage. General new/hidden brief reliability,
A+B, split identity answers and extra conversation styles were not checked here.
