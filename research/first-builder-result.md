# First builder result — 2026-10-10

The builder generated Brief A, passed local and Freya checks, published version 1,
read it back, and exported it. The first PUB-01 test stopped on a Freya service
error. It produced no score.

## Short plan and choices

1. Read complete briefs and OpenAPI. Extract fresh rules with source lines.
2. Generate a portable workflow and guard checks. Separate speech, bank facts, offers, confirmation and saved promises.
3. Validate locally and on Freya, publish to one stable slot, read back and export.
4. Test PUB-01 once, then three times on the same published version. Keep the local evidence.

The builder uses the local Codex CLI login and `gpt-6.1-sol`. Python's standard
library handles the run, validation and the existing Freya client. The phone
model stays as `freya.AGENT_LLM`; the exported provider and model are both
`experimental-5`. No local runtime service is needed. Each build has at most
30 minutes, including its test, and one automatic repair.

Build commands are in [builder/README.md](/Users/hamitarslan/Desktop/Projects/freya-yc-hackathon/builder/README.md).

## Published run

| Field | Result |
|---|---|
| Run | `20261010T193513442543Z` |
| Source commit | `4c7f5853a92aa932c3ac24a03c62ef84497d2415` — clean at start |
| Build time | 1,077.43 seconds, about 18 minutes |
| Generated workflow | 15 nodes, 47 source rules, 26 passing guard checks |
| Agent ID | `404df3cd-803d-4656-89ac-ac122f9d31d2` |
| Workflow ID | `e14dbbfa-9fd9-4bb0-9a4e-882897366f8d` |
| Published version | `1` |
| Version ID | `8a8bcd69-3657-4d55-b494-1bfbb3d5e2ea` |
| Save, readback and export | Passed; no submitted field was lost or changed |
| Overall run status | `incomplete_test`; live score unavailable |

The first candidate failed the closing-node manifest check. The builder repaired
it automatically from the same sources. The second candidate passed. Generated
files were not edited by hand. All 20 current repository tests pass.

Local evidence: [manifest](/Users/hamitarslan/Desktop/Projects/freya-yc-hackathon/build-the-builder/out/20261010T193513442543Z/manifest.json),
[policy](/Users/hamitarslan/Desktop/Projects/freya-yc-hackathon/build-the-builder/out/20261010T193513442543Z/policy.json),
[workflow](/Users/hamitarslan/Desktop/Projects/freya-yc-hackathon/build-the-builder/out/20261010T193513442543Z/workflow.json),
[validation](/Users/hamitarslan/Desktop/Projects/freya-yc-hackathon/build-the-builder/out/20261010T193513442543Z/validation.json),
[server export](/Users/hamitarslan/Desktop/Projects/freya-yc-hackathon/build-the-builder/out/20261010T193513442543Z/export.workflow.json),
and [trace](/Users/hamitarslan/Desktop/Projects/freya-yc-hackathon/build-the-builder/out/20261010T193513442543Z/trace.jsonl).

## First live test

The helper started PUB-01 once, then stopped while reading simulation status.
Freya returned HTTP 503: “API key validation is temporarily unavailable.”
This is an incomplete test, with no agent pass or fail score. The tested version
was not confirmed. The remote simulation may have continued after the helper stopped.

Simulation ID: `c69cae64-1161-4984-9097-a07e907e44eb`. Its final status is not confirmed
in this report. See the [test summary](/Users/hamitarslan/Desktop/Projects/freya-yc-hackathon/build-the-builder/results/20261010T195132348238Z-404df3cd/summary.json).

Helper fix `2b9cde4` retries only Freya GET requests returning HTTP 503, at 2, 4 and
8 seconds. Writes and authentication errors are not retried. Four bounded read
attempts still returned the same 503. Two more spaced checks failed, most
recently at 20:01 UTC. The [recovery record](/Users/hamitarslan/Desktop/Projects/freya-yc-hackathon/build-the-builder/results/20261010T195132348238Z-404df3cd/recovery-checks.jsonl)
keeps the error and timestamps. No new simulation has started and the published
agent is unchanged.

Once the previous simulation has ended and the shared workspace is free, retry
one official case against this agent:

```bash
bash scripts/test-agent.sh 404df3cd-803d-4656-89ac-ac122f9d31d2 --only PUB-01
```

## Known limits

- A local code replay found that a question after completed identity can leave
  the caller in the identity stage. A later answer can close with `service_error`.
  The [synthetic replay](/Users/hamitarslan/Desktop/Projects/freya-yc-hackathon/build-the-builder/out/20261010T193513442543Z/identity-interruption-replay.json)
  uses the published decision code; it is not a live test. This needs a compiler
  fix and another generated version.
- The full Brief A suite, PUB-01 three repeats, and A+B multi-product behavior
  are not tested. Multi-product requirements currently block this compiler.
- Brief A does not define all service-failure recovery and closing rules. The
  generated fallback outcomes are provisional. Successful promises are preserved.
- Some calendar cases make the required suggestion fall in the past or beyond
  the deadline. The guard stops those writes rather than changing the policy.
- Speech extraction and spoken policy still need live checks. Local guard tests
  do not prove a full conversation is correct.
- The local lock covers this computer. Another computer or the dashboard can
  still change the shared workspace. Do not update the agent during a test.

The manifest keeps the generator's uncertainty notes. Later checks and publication
records supersede its early note that the corrected candidate had not yet been
rerun. `.env`, exports and full traces remain local and ignored by Git.
