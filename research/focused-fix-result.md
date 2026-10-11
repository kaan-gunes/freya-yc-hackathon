# Focused fix delivery — 11 October 2026

This is a source and local-test delivery for `FOCUSED_FIX_PROMPT.md`.
The starting checkout was clean at `e747763`. The newer commits after the reviewed
implementation `0331b18` only changed docs. Source commit:
[`f22ea8b`](https://github.com/kaan-gunes/freya-yc-hackathon/commit/f22ea8b7c952f816be8ad9d20b42a9befffea428).
The builder prompt and validator now require the behaviors below. Executable
guard examples are synthetic local candidates, not a new published workflow.

| Change | Local evidence |
| --- | --- |
| A current approval amount/date change clears old authorization, even with an empty or wrong correction label. The new value needs validation, readback and a fresh yes. Plain yes still works. | `tests/test_focused_approval_retry.py`: independent amount/date mutations, fresh approval and ordinary yes. |
| Record success and error both reach shared result code. A current API error may retry only with the OpenAPI no-write guarantee and the brief's budget. A required second attempt cannot be removed by lowering metadata. Timeout, missing status and stale result data cannot retry. | The same test file follows actual graph edges with the post-hook skipped, checks unchanged request bindings, retry success, the two-failure limit and a non-passthrough result-node rejection. |
| Promise field names follow the actual request and OpenAPI. Identity probes follow source-required question types. The builder passes the original brief lines to validation. | `tests/test_focused_inputs.py`: renamed API passes; wrong bindings and omitted required questions fail; date-only and text-only inputs keep meaningful checks. |
| Before identity, paid/dispute/plan claims keep stage-safe speech and close state. An insisting human request still reaches guarded transfer. | `tests/test_focused_conversation.py`: speech/route checks and a negative mutation of the actual close pre-hook body. |
| Payment month/day answers use call `now` separately from DOB's explicit-year rule. Ambiguous or impossible month/day answers ask for clarification. | The same file covers both month/day orders, “of” wording, year rollover, ambiguity, impossible dates and a broken year-required parser. Existing spoken-digit and cardinal-DOB checks remain. |
| Resume takes the lock before changing saved results and holds it through final saves. Execution time is preserved; read time is `recovery_seconds`. | `tests/test_test_agent.py`: lock rejection preserves every saved output and makes zero API calls; 128.45 execution seconds survives recovery and the official result output. |

The single full repository run was **105/108** in 654.470 seconds. Its three
failures were old fixtures for renamed customer binding, six-digit identity code
and renamed question properties. They were fixed during that run; five affected
checks passed on the updated source. The full suite was not repeated.

Focused approval/retry **6/6**, input **8/8**, conversation **6/6** and helper
**19/19** passed. The final approval/retry module passed again after result-node
and sourced-budget checks were added. Builder `self_check()` and
`git diff --check` passed. Build integration tests use mocks; their generation,
publish and simulation log messages do not represent real calls.

The API guarantee comes from the supplied OpenAPI `create_promise` 500 response:
it says nothing was recorded and permits repeating the call. The flattened
current-response error evidence comes from the historical PUB-10 observation in
`research/second-builder-result.md`, call `bed89b3d-9c60-4de3-9cc5-dd32162b35c1`.
That is previous evidence, not a new successful run.

No builder model call, generation, publish, live simulation or bank write was
started. Published v6 and generated exports were not edited. `PROJECT_CONTEXT.md`
still points to the previous reviewed commit. The official scorer and test-case
expectations were not changed. Secrets and raw results remain outside Git.

Remaining limits: a new generated agent and live run are required after review
to prove these source changes on Freya. The local source checks use explicit
English question/type and retry evidence, including “Ask N security questions”
and “If it fails, try once more” wording; this is
not a general prose parser. Old results without saved execution time keep it
unknown; the unchanged official numeric total uses zero for that missing value.
A+B, a separate LLM chief, broad history changes, spoken money and cross-turn
identity assembly remain outside this round.
