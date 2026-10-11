# Validator fixes and one build result

11 October 2026, Europe/Istanbul. Source commit: `bd2bb2958e58136f3cb9788f952d69b8914e047d`.

The repo was clean and matched `origin/main` (`e9352ae`) at the start. No newer fixes were present. Team changes were preserved. The required phone-agent skill was read; brief/API rules and trusted tool results remained the basis for generation.

## Two fixes

- **Identity overrides:** `_identity_requirements()` now uses active rules while keeping old rules for audit. Both `replaces` and `replaced_by` accept a rule ID or list. Removing a requirement needs original source text, higher input priority and an explicit numbered-rule reference. Fake source text, wrong rule/brief references, missing inputs, unknown IDs and duplicate IDs are rejected. The compiler prompt states this contract.
- **Business-failure retry:** after HTTP 200 / `data.ok=false`, the complete bound request must equal the first approved request, as on the HTTP-error path. Product, amount and date mutations are rejected. A new independent check covers success on the second attempt. Attempt limits and unknown-timeout safety remain intact.

The positive regression replaces DOB + phone-last-four with one birthplace question. It passes with both links or either link alone, retaining the old evidence. Negative override and three request-mutation cases pass their rejection checks. Production values still come from the brief/API.

## Local checks

Commands used `/opt/homebrew/bin/python3` from the repo root.

| Check | Actual result |
| --- | --- |
| `-m unittest tests.test_focused_inputs tests.test_focused_approval_retry -v` | 17/17; 27.095 s |
| Three new tests rerun after cleanup | 3/3; 5.714 s |
| `-m unittest tests.test_builder_validation tests.test_focused_conversation tests.test_build_agent -v` | 75/75; 465.399 s |
| `scripts.build_agent.self_check()` | Passed |
| `git diff --check` | Passed |

**92 distinct tests passed; 95 executions include the three rechecks.** Builder integration tests use mocks. The unchanged test-helper module was not rerun.

## Single builder run

```bash
bash scripts/build-agent.sh build-the-builder/briefs/brief-a.md --openapi build-the-builder/tools/openapi.json --slot kaan-validator-brief-a --budget-seconds 1800
```

13:00:12–13:16:49 Istanbul time; **996.41 s (16 min 36 s)**, within the 30-minute limit. The manifest records the source commit above and `code_dirty=false`. One generation and two automatic merge-patch repairs requested `gpt-6.1-sol` inside this one invocation.

| Attempt | Generated-candidate validation |
| --- | --- |
| 1 | Rejected: four-node opening/safe-stop output; core banking stages/guards missing and unsupported |
| 2 | 162/168 checks passed; six date/readback checks failed |
| 3 | 166/168 checks passed; two date-correction probes still failed |

Final status: `incomplete`, exit `2`, `Generated workflow failed validation`. No Freya dry-run, publish or test was reached.

| Requested evidence | Actual result |
| --- | --- |
| New workflow / agent / version IDs | None created |
| Builder PUB-01 | Not run; no score |
| Full Brief A | Not run; no new published version |
| Simulation / iteration / call IDs | None created by this build |
| Server export | Not created |

This is a blocked build, not `0/1` or `0/10`. There are no live failed cases or call/tool transcripts. Old v6 scores are not evidence for this source.

## Concrete block and next review

The final failed probes were `independent_approval_date_missing_correction_marker` and `independent_approval_date_wrong_correction_marker`.

The generated fixture starts on **2026-10-23**, also its deadline. The probe injects **2026-10-24**. The offer guard follows Brief A rule 23 and offers the deadline again. The validator rejects the readback because its product/amount/date fingerprint equals the old one.

Local replay assertions passed for both marker states (`""` and `"no"`): the approval guard clears authorization and both fingerprints; the offer guard reaches the actual confirmation node, offers 2026-10-23 again and asks “Do you confirm?”; only a fresh yes authorizes recording that date. No bank call was made.

The immediate block is a probe/fixture boundary mismatch. Live behavior remains untested. For review: use a correction that produces a different valid accepted date, plus a separate deadline-boundary check. Freshness cannot be inferred only from changed accepted values. This proposal was not implemented; no further build or test cycle was started.

## Platform and saved evidence

Preflight could not read `GET /api/v2/workspaces`: the original client and a bounded GET-retry sequence ended with `RemoteDisconnected`; an authenticated curl read timed out after 25 s with zero bytes. Active simulations and current v6 metadata could not be verified. These reads made no platform writes. **The build itself stopped at local validation.** There is no new simulation to resume.

Local, ignored build folder:
`/Users/hamitarslan/Desktop/Projects/freya-yc-hackathon/build-the-builder/out/20261011T100012806452Z/`

It retains `trace.jsonl`, `manifest.json`, all `raw-attempt-N.json`, `candidate-attempt-N.json`, `validation-attempt-N.json`, final unpublished `workflow.json`, and `correction-boundary-replay.json`. The workflow is a local candidate, not a server export. Check logs, source checksums and preflight error are under ignored `build-the-builder/out/validator-fix-checks/`.

Replacement evidence currently supports explicit English numbered-rule references; other memo formats need a source-backed extension. A+B, further live loops and broad history changes were skipped. Brief/OpenAPI, Freya client, phone model and official scorer stayed unchanged. `PROJECT_CONTEXT.md` and its independent-review pointer stayed unchanged. Secrets and raw artifacts remain outside Git.
