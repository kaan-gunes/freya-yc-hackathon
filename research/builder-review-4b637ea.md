# Deadline fix and blocked build review — 11 October 2026

What this change does: The validator now allows a corrected payment date to return to the same deadline after a fresh readback. It still requires old approval to be cleared and a new clear yes before recording.

Reviewed HEAD: `4b637ea`; application source: `d58cd36`; comparison base: `414e19b`. The saved build used `9d376d0`, before the final approval-binding follow-up. Review scope is the two validator commits, their callers and tests, and the actual saved build candidates. Expected use is one builder run and one shared-workspace simulation at a time.

**Verdict: fix 1 and 2 first.** The deadline fix passes the focused tests and the previous unchanged candidate. The latest build completed its invocation but stopped at local validation. It created no new published agent or live customer score.

## Must fix

### 1. [P1] Generated `re.I` fails in the local regex module

- **What this is:** [`SAFE_MODULES`](../builder/validation.py#L24) creates a restricted copy of Python's regex module. Generated code uses `re.I`, the standard alias for `re.IGNORECASE`.
- **Problem:** The copy exposes `IGNORECASE` but omits `I`. The saved last candidate reads `re.I` in `decision` snippet line 173 for ordinary unverified callers, and line 288 for phone answers. Its broad error handler returns `listen` and `error: safe repeat`. Valid identity answers, opening replies, callbacks and human requests therefore fail local checks.
- **Fix:** Align the local module and the supported generated-code contract. A small alias-support change with a regression is sufficient for this local mismatch. Check the platform contract too; do not assume that this review proves the live Freya runtime accepts every regex member. Keep other import and security limits.
- **If we skip it:** Valid generated behavior remains blocked before publishing, and repair prompts try to fix dozens of symptoms from one local exception.

Independent evidence: the unchanged candidate passes **126/176** with the production validator. Temporarily exposing only `I` in the review process clears **all 50 original failed checks**. The result is **173/176**, because three different privacy probes then become visible. Candidate code and production validator files were not changed. This is an offline diagnostic, not a fixed builder or live score.

### 2. [P1] Privacy probes compare different caller states and reject safe relative handling

- **What this is:** [`pre_identity_exception`](../builder/validation.py#L1150) copies the third-party fixture for `paid`, `dispute` and `plan`. It clears all speech for the comparison state, but changes only the event for the tested state. It then requires identical close outcome/reason at [line 1175](../builder/validation.py#L1175).
- **Problem:** The actual fixture still says “I am his sister” and contains a complete offered identity answer. The tested state correctly detects a relative, clears first-party confirmation and asks for a callback. Its safe close fallback is `not_reached/unclear`. The cleared comparison state remains in identity with `not_verified/declined`. Both are safe, but their difference fails all three probes. Brief A rules 5 and 10 require the relative path.
- **Fix:** Build each privacy probe from consistent current speech and caller state. Keep first-party account claims and relative interruptions as separate cases, or use a comparison state with the same trusted caller status. Retain checks for forbidden speech, bank access, and account outcomes before identity. Do not just remove the close-body check or force the generator to ignore a relative.
- **If we skip it:** Correct relative handling is rejected, or repairs may remove a useful safeguard to satisfy an inconsistent test.

Independent evidence: eight replays exercised blank/paid/dispute/plan events with and without the relative text. They reached a listener without record authority and selected only the two safe pre-identity close fallbacks above. With the regex alias exposed, changing only the diagnostic fixture text to `14 March 1988.` makes the same candidate pass **176/176**. The fixture still contains a complete identity answer and its `third_party` event; third-party checks remain present. Three deliberately broken variants that set `paid`, `no_promise/dispute`, or `transferred/restructuring` before verification are still rejected by their corresponding privacy probes.

These temporary fixture changes demonstrate the bad comparison. They are not a proposed manual edit to the generated production workflow, and no fixture change was saved back to the candidate.

## Tests and build evidence

| Check | Independent result |
| --- | --- |
| Focused approval/retry and inputs modules | **21/21**, 59.022 s |
| Focused conversation module | **6/6**, 3.276 s |
| Builder `self_check()` and initial `git diff --check` | Passed |
| Previous unchanged candidate with final validator and source provenance | **168/168**, valid |
| Latest unchanged candidate with final validator and source provenance | **126/176**, invalid; provenance passed |
| Latest candidate, diagnostic regex alias only | **173/176**; all 50 original failures cleared, three different privacy failures exposed |
| Latest candidate, diagnostic alias and consistent fixture text | **176/176**, valid locally |
| Unsafe account-close variants | **3/3 rejected** |

The 27 unit tests are independent review executions. The complete unit suite and unchanged builder/test-helper modules were not rerun. The deadline tests cover interior dates, weekend adjustment, the same deadline, stale authority/fingerprints, missing fresh yes, skipped readback and fields bound only after fresh yes.

The manifest and trace confirm one generation plus two repairs in **1436.02 seconds**, source `9d376d0`, `code_dirty=false` at start, and final `status=incomplete`. The trace contains model and local-validation events, then `end`; no Freya validation, publish or customer-test event. The real last attempt was **124/176** with that earlier validator; final-source offline replay removes two approval-binding false rejections and gives **126/176**. These numbers are local checks, not official customer scores.

A separate authenticated read-only GET for the existing workflow's versions timed out after 25 seconds. Current platform version metadata was not confirmed. This read did not create a workflow, simulation or bank session; it is separate from the local errors that stopped the build.

## Evidence files and next step

Actual saved build: `build-the-builder/out/20261011T105328711505Z/`. Previous candidate: `build-the-builder/out/20261011T100012806452Z/candidate-attempt-3.json`. Both are available in this checkout.

Ignored independent evidence: `build-the-builder/out/review-4b637ea/`. It contains `revalidate.py`, three revalidation JSON files, `privacy-fixture-repro.py/json`, and a line-number-addressable extracted `candidate3-decision.py`. The scripts use assert-based checks and make no model or bank calls.

Production validator SHA256: `ad24a3e24b19da617945eca1db1ba06a9f23c520e83bab8ce5f0fdd1397474d4`. Saved latest candidate SHA256: `e7f55259dd18f20518e67886267c2e4aaefeb533dcc50081008b7b3aaa4af6fd`. The replay checks that the saved candidate stays unchanged.

Next narrow task: fix the two validator mismatches, retain negative safety tests, then make one builder run. If it publishes, test PUB-01 and one full A run on that same version. Do not expand to A+B or start a repeated build/test loop. Production code, generated candidates, phone model, team credentials and official scorer were not changed by this review.

Kodlama chatine verilecek görev: [VALIDATOR_COMPAT_FIX_PROMPT.md](../VALIDATOR_COMPAT_FIX_PROMPT.md).

Not checked: live behavior of the unpublished candidate, complete A/B policy coverage, and all platform regex members. Passing the diagnostic local checks does not establish live success.
