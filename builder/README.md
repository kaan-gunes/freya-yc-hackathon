# Phone-agent builder

This builder reads supplied brief files or a case folder and its service contract. It uses the local Codex
CLI login with GPT-6.1-Sol to create a fresh policy, portable Freya workflow, and guard checks.
PDF reading uses pypdf; YAML contracts use PyYAML. DOCX and XLSX reading uses the
standard library. The phone model stays as `freya.AGENT_LLM`.

The source task selects the collections or general inbound service profile.
The source rules and any missing support are listed in each generated policy.
Local guard checks are not a live test score.

## Run

Install Python 3.10 or newer and the Codex CLI, then run `codex login`.
The local CLI must support `exec --ignore-user-config`.

From the repository root:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt

# Generate and check locally. No Freya key is needed.
bash scripts/build-agent.sh build-the-builder/briefs/brief-a.md \
  --openapi build-the-builder/tools/openapi.json --offline

# Generate, validate, publish, read back, export, and test PUB-01 once.
# build-the-builder/.env (or env.sh) must contain both team keys.
bash scripts/build-agent.sh build-the-builder/briefs/brief-a.md \
  --openapi build-the-builder/tools/openapi.json --slot kaan-brief-a
```

## Final folder input

The runner reads Markdown, UTF-8 text, JSON, YAML, CSV, PDF, DOCX and XLSX.
JavaScript/TOML examples are read as inert text, never executed.
Office macros and formulas are never executed. Excel formulas need a saved
cached result. Scanned PDFs need OCR before this reader can use them; old
`.doc` and `.xls` files must first be converted to modern Office formats.
Unreadable or unsupported documents stop with their source path.

```bash
bash scripts/build-agent.sh "{case_folder}" --mock-url "{mock_url}" \
  --slot core-final --submission-dir submission/selected
```

The folder must contain one explicit OpenAPI JSON/YAML contract, or complete
HTTP integration documents. With no schema file, a separate model call extracts
the contract with exact source-line evidence. Missing contracts, invented paths,
unknown fields or unresolved contract facts stop before phone-agent generation. Multiple
schemas require an explicit `--openapi path`. `--mock-url` is the complete service
base combined with the exact contract paths. Extracted contracts keep the full
original pathname, including any API prefix. All engine HTTP calls are bound to it before
validation. The supplied contract's methods, paths and fields stay intact.

Folder order is not rule priority. The builder uses source authority, version,
effective date and explicit amendments; examples do not amend bank policy.
It uses the requested conversation language. Turkish explicit consent, month
names, day words and decimal-comma amounts preserve the existing safety gates.
A reply confirming only one payment field does not approve the complete promise.
Relative dates use sourced call time and bounds. DOB still needs a numeric year;
fully word-spelled years are not supported by the shared normalizer.

Folder runs skip practice simulations. File runs can use `--skip-tests`.
Local validation, Freya dry-run, publish, readback, fixed phone-model check,
published-version check and official export remain required. Successful online
runs copy `export.workflow.json`, `trace.jsonl` and `manifest.json` into the empty
submission directory. Existing delivery files are never overwritten. The trace
includes the actual redacted full native Codex session records matched by thread ID,
stdout events, model purposes, timings,
source hashes, IDs, node/tool counts and an explicit `not_run` test state.
Candidate hashes prevent editing a generated candidate before a resume.

Each run has a real wall-clock limit, at most 30 minutes, including model work
and tests. Use the same slot to update the same workflow. The baseline is kept.
Up to two automatic repairs are allowed after local or Freya check failures,
within the same deadline. No failed candidate is published.
Repairs return only a JSON merge patch; the builder assembles and validates the
complete candidate before any publish. Arrays replace the entire prior array.
All call code and policy are inside the workflow; no local server is needed.

Before validation, `builder/compiler.py` adds source-owned confirmation gates
to each generated candidate. A reply after a confirmation question returns through
offer validation and a fresh readback. Current raw questions, refusals and
conditional consent cannot authorize a promise. Sourced AI/scam answers survive
offer clarification. Business values still come from the input policy; this is
the first source-owned part of the controller, not a complete policy compiler.

After the first real test passes, run three repeats against that same published
agent. This is a separate development test, so it does not extend a build's limit:

```bash
bash scripts/test-agent.sh AGENT_ID --only PUB-01 --reps 3
```

Only one simulation may run in the shared workspace. Tell the teammate before
publishing or testing. The local builder lock stops two local builds; it cannot
lock another computer or the dashboard. Do not update an agent during a test.

## Outputs and checks

`build-the-builder/out/<run>/` holds the input record, `policy.json`,
`workflow.json`, `checks.json`, `validation.json`, trace and run metadata.
Online runs also keep the server export and published workflow/agent/version IDs.
The trace records the builder model, purpose, timing, source hashes and test state.
The code revision includes whether the worktree has changes. Full model reasoning
is not stored. Generated artifacts are local and ignored by Git.
`raw-attempt-N.json` preserves the model response, including sparse repairs;
`candidate-attempt-N.json` preserves the assembled full candidate.
The compiled candidate is separate from the raw model response. The manifest
records the compiler source hash and the trace records `workflow_compiled`.
The compiler asks for a fresh answer when a payment non-answer has no current
text, amount or date. It preserves the proposal and persuasion count. A real
non-answer with current text still follows the sourced negotiation policy.

To reuse the last saved complete candidate from a prior generation run, add
`--resume-build build-the-builder/out/RUN_FOLDER` to the same build command.
The ordered brief/API/prompt/platform source paths, SHA256 hashes and line counts
must match its manifest, and the slot must be the same. Missing or changed inputs
stop before platform access. The current validator and source provenance run again,
then the same dry-run, publish, readback, export and test gates apply.
Resume makes no model call or repair. Its new manifest and trace record the original
run, generation commit, candidate hash and reuse time; `generation_attempts` is empty.
For compiled runs, the compiler source must also match. Legacy runs without
compiler metadata still use their original exact-source resume checks.

To compile an existing same-input draft without a model or Freya request:

```bash
python3 scripts/build_agent.py build-the-builder/briefs/brief-a.md \
  --openapi build-the-builder/tools/openapi.json --slot kaan-brief-a \
  --offline --compile-build build-the-builder/out/RUN_FOLDER
```

This path makes one deterministic compilation and runs the full validator and
provenance checks. The saved draft must have the same ordered brief/API/platform
sources and slot. The prompt and compiler may change only on this explicit path
or on model repair; ordinary resume stays strict. Its manifest records
`compile_seed` and `compilation_attempts`; `generation_attempts` stays empty.

For one offline model repair of an old complete draft, use `--offline
--repair-build build-the-builder/out/RUN_FOLDER`. The slot and all ordered
brief/API/platform paths, hashes and line counts must still match. Only the
compiler prompt may change on this separate path. The draft is not a rule source;
the model receives all current inputs and current validation errors, returns a
merge patch, and the assembled candidate passes current validation and provenance.
There is one model attempt within the same 30-minute limit and local lock. No
Freya request or test runs. The trace records `candidate_seeded_for_model_repair`,
the old source/hash evidence and a real generation attempt, rather than reuse.
`--resume-build` still requires every source hash to match exactly.

The local validator checks stage boundaries, API fields, Python syntax, and
executes generated guard examples with restricted Python. It also runs its own
expected checks on shared state across offer, readback, approval and record.
These cover valid recording, rejected offers followed by yes, changed offers,
corrections, mixed exceptions, duplicate writes, failed/unknown writes, retry
limits, returning from completed identity, silent replies, third-party identity
interrupts and six month-name date forms at the real verification request.
Synthetic fixture inputs and
variable roles come from the candidate; expected safety rules come from code.
Current amount/date changes must force a new readback even without a correction
label. Record success and errors both pass through a result code node; skipped
post-hooks, stale status, safe retries and unknown timeouts are checked through
the real graph. Promise field names are checked against the actual OpenAPI and
request. Identity question declarations use the original brief evidence; date
and numeric-code probes apply only to required question types. Pre-identity
speech/closing and payment dates without a year also have independent checks.
Word-day payment probes reach both the fresh decision and shared offer guard.
For sources requiring minimum/support/restructuring, separate conversation input
fixtures test mixed intents with missing or wrong event labels, current bank
minimum answers, stale-question clearing, normal closings and skipped-code retry
speech. These inspect the actual TTS and guarded request fields. A code timeout
cannot be caught by a snippet that never started; its fallback listener needs
literal speech and no bank tools.

The graph checks require offer/readback guards on record paths, reachable actions
and terminals, and reject unconditional action loops. Callback, transfer and
note actions need code guards and trusted request fields. Python checks allow
direct variable reads and literal-key writes, block variable-table aliases and
real-clock aliases, and forbid request changes in pre-hooks. Only the final
close hook may replace its outcome/reason body fields. These are supported-code
checks, not a general Python sandbox or proof of every business rule. Time and
calendar behavior still needs source checks and live cases.

Listening nodes route every reply through code. They have no model tools or
semantic routing fallback. Code consumes and clears plain string speech fields,
handles exceptions, and selects the exact stage question. This local schema
check does not prove the platform accepted each reset. Freya dry-run, readback,
export and live call diagnostics provide separate evidence.

Failures stop the run with a visible report. A missing key or an unfinished test
is reported as not run or incomplete, with no invented score. Never copy secrets
into prompts, reports or Git. `.env` and `env.sh` stay local.

The test helper saves session, simulation, iteration and call identities as soon
as they arrive. Its summary separates call execution, result reads and scoring.
Each successful metadata source adds version evidence. Call versions use
`entityVersionNumber` only for calls matched to this simulation and agent;
dashboard versions are not test evidence. Call diagnostics expose rejected
state writes, extraction errors, unmatched routes and direct decision fallbacks,
without copying raw speech into diagnostic excerpts.
`function_call_error` for `code_exec` is reported as `code_execution_failure`.

If a read fails after a simulation was created, resume the saved run:

```bash
bash scripts/test-agent.sh --resume build-the-builder/results/RESULT_FOLDER
```

Resume uses saved bank sessions and only reads the known simulation. It does not
repeat writes. An unknown create result without a simulation ID cannot be
resumed automatically. Incomplete ledger reads have no invented score.
The lock is acquired before saved results are changed. Resume preserves execution
seconds and stores its read time separately as recovery_seconds. Old runs without
saved execution timing keep that value unknown; official numeric totals use zero.

## Next checks

First verify PUB-01 once and three times. Then test all Brief A cases, correction
and split-answer styles, and modified synthetic brief inputs. Complete A+B rules
before claiming multi-product support. Keep official scoring expectations unchanged.
