# Deadline validation fix and one build result

11 October 2026, Europe/Istanbul. Build source: `9d376d0d7e9f89aa09e4c4cc8ca542c57bf25ec8`. Final validator: `d58cd36c6094cc8007da21002706eed1a94a4573`.

The repo was clean and matched `origin/main` (`f9ae22f`) before the change. Fetch and fast-forward checks found no newer team commits. Existing work was preserved. The required phone-agent skill, Brief A, OpenAPI, platform guides and review notes were read. `PROJECT_CONTEXT.md` and its independent-review pointer were left unchanged.

## Fix

`unmarked_correction` now separates a new readback from changed accepted offer values. A later date can be moved back to the same deadline under Brief A rule 23. Its product/amount/date fingerprint can therefore match the previous offer after a real new readback.

The probe still injects a current yes with a missing or wrong correction marker. It now also seeds stale authorization. It requires the approval guard to clear authorization and both fingerprints, carry the current value to the shared offer guard, and return to the real confirmation node. Recording must stay blocked without a new reply; a new clear yes must reach an authorized record action with bound API fields. If the accepted bank request changes, reusing the old fingerprint is still rejected. A listener or safe close cannot pretend that a readback happened.

The next calendar day is a request, not an assumed valid promise date. Tests cover an allowed different date, a weekend moved to a business day, and a later request moved back to the same deadline. Broken examples that keep old authority/fingerprints, skip offer validation or the readback node, reuse a fingerprint for changed accepted values, or record without a new yes are rejected. Production code adds no brief dates, amounts, holidays or variable mappings.

### Follow-up found during this one build

The first generated candidate binds its write fields (`approved_product`, `approved_amount`, `approved_date`) only after a clear yes. The first version of my new comparison tried to read those fields before approval. That added a false `authorized request has no bound product_id` rejection to its two date probes, even though its ordinary positive record probe passed.

Commit `d58cd36` removes this new assumption. It compares the original and corrected requests only after separate fresh authorizations, in isolated offline states. A regression covers both an interior date and the same deadline with fields bound only after yes. The unchanged previous candidate passes 168/168. The unchanged first new candidate improves from 110/162 to 112/162 in offline revalidation; all four correction-marker probes pass. Its other 50 failed checks and unsupported behavior remain failures.

The builder had already imported the validator from `9d376d0`. Its actual attempt results are evidence for that source, not `d58cd36`. No generated workflow was edited and no second builder was started. The final follow-up has local evidence only.

## Local checks

Commands used `/opt/homebrew/bin/python3` from the repo root.

| Check | Actual result |
| --- | --- |
| `-m unittest tests.test_focused_approval_retry tests.test_focused_inputs -v` | 19/19; 48.941 s; includes earlier identity and retry regressions |
| Three correction regressions before the build | 3/3; 25.641 s; covers changed fingerprints, fresh yes and the readback mutation |
| `-m unittest tests.test_builder_validation -v` | 63/63; 519.278 s |
| `-m unittest tests.test_focused_approval_retry -v`, after the binding follow-up | 11/11; 41.841 s |
| Builder self-check and `git diff --check` | Passed |
| Previous unchanged generated candidate, with final validator | 168/168 checks; source provenance passed |

**84 distinct tests passed; 96 executions include 12 repeats.** The main suite ran on the first implementation. The final source changes were checked by the full approval/retry module, self-check and unchanged generated candidates. The unchanged builder/test-helper suites were not rerun.

The previous candidate came from local ignored `build-the-builder/out/20261011T100012806452Z/candidate-attempt-3.json`. It was only revalidated offline; it was not edited or published.

## Single builder run

```bash
bash scripts/build-agent.sh build-the-builder/briefs/brief-a.md --openapi build-the-builder/tools/openapi.json --slot kaan-brief-a --budget-seconds 1800 --only PUB-01 --reps 1
```

13:53:28–14:17:24 Istanbul time; **1436.02 s (23 min 56 s)**, inside the 30-minute limit. The manifest records build source `9d376d0` and `code_dirty=false` at start. One generation and two automatic merge-patch repairs requested `gpt-6.1-sol` inside this one invocation. The command used the existing slot; no workflow update was reached.

| Actual builder attempt, using `9d376d0` | Local result |
| --- | --- |
| 1 | 110/162 checks; unsupported behavior and identity/opening/callback failures; two date probes also hit the pre-approval binding assumption |
| 2 | 50/70 checks; forbidden variable-table handling, routes bypassing offer/readback guards, and failed generated checks |
| 3 | 124/176 checks; unsupported list empty and source provenance passed, but 52 checks failed |

Final status: `incomplete`, exit `2`, `Generated workflow failed validation`. The run stopped at local validation. It did not reach Freya dry-run, save, publish, server readback/export or customer testing. Check counts vary with each generated candidate; they are local checks, not official customer scores.

| Requested live evidence | Actual result |
| --- | --- |
| New workflow / agent / version IDs | None created by this run |
| Builder PUB-01 | Not run; no score |
| Full Brief A | Not run; no new version from this run |
| Simulation / iteration / call IDs | None created by this run |
| Server export | Not created; local `workflow.json` is an unpublished candidate |

This is a blocked build, not `0/1` or `0/10`. No new live failed customers or scores exist. Old v6 scores are not evidence for these sources. No second builder or live-test cycle was started.

## Concrete remaining block

Offline revalidation of the **unchanged last candidate** with final validator `d58cd36` gives **126/176**. All four missing/wrong correction-marker probes pass; the two pre-approval binding false rejections are gone. Its other **50 checks remain failed**, including complete spoken DOB/phone answers, opening ask limits, callbacks and pre-identity human transfer.

A common exception is confirmed in the generated `decision` snippet, line 173. It calls `re.match(..., re.I)` for an unverified caller. The local restricted `re` module exposes `IGNORECASE` but not its `I` alias. The outer handler catches the resulting error and returns `route=listen`, `decision_status="error: safe repeat"`. This prevents ordinary complete identity answers from reaching `verify_identity` and affects other pre-identity branches. This is local execution evidence; the candidate was never run on Freya.

One isolated diagnostic replay kept the candidate and validator source unchanged and temporarily exposed `I=IGNORECASE` in the local module proxy. The same canonical DOB input then reached `route=verify` with the correct bound answer. That confirms this exception for that replay; it does not certify all 50 failures or create a new score. No alias-support change was added, and no generated workflow was edited. This remaining compatibility issue is left for the next review.

The authenticated preflight read the workspace, listed simulations and read workflow versions. It found no active simulation and v6 published (version ID `946ce959-11d7-4ab5-bfda-faeea22588ad`, existing agent `404df3cd-803d-4656-89ac-ac122f9d31d2`, workflow `e14dbbfa-9fd9-4bb0-9a4e-882897366f8d`). Separate reads at build start and after the build timed out after 25 seconds; current post-build platform metadata could not be checked. These GETs made no platform writes. The manifest and trace show that this builder never reached a platform write. There is no new simulation to resume.

## Evidence and scope

Ignored local check folder: `/Users/hamitarslan/Desktop/Projects/freya-yc-hackathon/build-the-builder/out/deadline-fix-checks/`. It contains `focused-tests.log`, `final-regression-tests.log`, `validation-tests.log`, `post-generation-approval-tests.log`, `previous-candidate-final-revalidation.json`, `new-attempt-1-final-revalidation.json`, `new-attempt-3-final-revalidation.json`, `regex-alias-diagnostic.json`, `preflight.json`, `build-start-readback.json` and `post-build-version-readback.json`.

Ignored build folder: `/Users/hamitarslan/Desktop/Projects/freya-yc-hackathon/build-the-builder/out/20261011T105328711505Z/`. It retains `trace.jsonl`, `manifest.json`, all three `raw-attempt-N.json`, `candidate-attempt-N.json` and `validation-attempt-N.json` files, and final unpublished `workflow.json`. No server export was produced. These artifacts stay outside Git.

Team credentials, Brief A/OpenAPI, the fixed phone model, Freya client and official scorer are unchanged. Secrets and raw artifacts stay outside Git. No A+B work, memo-parser extension, separate checker, history change or second build/live-test cycle is included.
