# First builder result — 2026-10-10

The first target is Brief A and the real PUB-01 call. Generation is being rebuilt
after local checks and review found errors. No live score is claimed yet.

## Short plan and choices

1. Read all briefs, OpenAPI and platform documents. Extract fresh rules with source lines.
2. Generate a portable workflow and guard checks. Separate speech, bank facts, offers, confirmation and saved promises.
3. Validate locally and on Freya, publish to one stable slot, read back and export.
4. Test PUB-01 once, then three times on the same published version. Save the full local evidence.

The builder uses the existing local Codex CLI login and GPT-6.1-Sol. Python's
standard library handles validation, the deadline and the existing Freya client.
The phone model stays as `freya.AGENT_LLM`. No local runtime service is needed.
The run has at most 30 minutes, including its test, and one automatic repair.
Freya schema errors enter that repair before any workflow save.

## Evidence so far

- All 19 repository tests pass. These include bank access and approval gates,
  API fields, failed writes, malformed output, test version evidence and schema repair before publishing.
- The previous candidate had 14 stages, source links for all 47 Brief A rules,
  and 24 passing generated guard checks. Freya rejected a missing lifecycle tool
  description before publishing. That format check is now enforced locally.
- Earlier development runs found a JSON escaping problem. The builder now asks
  for direct JSON objects and uses strict parsing; generated files were not patched by hand.

## Latest development run

Runtime source commit: `476fead`.
Local output: `/Users/hamitarslan/Desktop/Projects/freya-yc-hackathon/build-the-builder/out/20261010T192309782796Z`.
The output records input hashes, generated policy/workflow/checks, validation,
model metadata, trace, server export and live test evidence as each step completes.

This generation was stopped before publishing. Review found missing `next` and
`format` support in the local harness, plus exact-text checks that rejected clear
positive sentences. The harness and compiler guidance are now fixed. Generated
files were not edited. Agent, workflow, published version and live results will
be recorded after the next run ends.

## Limits

The full Brief A suite and A+B multi-product behavior are not yet tested.
Multi-product requirements block this first compiler rather than silently becoming a single-product workflow.
Unspecified API recovery policies and calendar conflicts remain visible in each run's uncertainties.
The local lock covers this computer; another computer or the dashboard can still update the shared workspace.

Run instructions are in `builder/README.md`. `.env`, exports and full traces remain local and ignored by Git.
