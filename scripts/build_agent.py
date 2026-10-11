#!/usr/bin/env python3
"""Build a portable Freya phone agent from complete briefs and an OpenAPI file."""
import argparse
import copy
import datetime as dt
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parent.parent
KIT = ROOT / "build-the-builder"
sys.path[:0] = [str(ROOT), str(KIT)]


class BudgetExpired(TimeoutError):
    pass


def now():
    return dt.datetime.now(dt.timezone.utc).isoformat()


def redact(text):
    for name, value in os.environ.items():
        if value and ("KEY" in name or "TOKEN" in name or "SECRET" in name):
            text = text.replace(value, "[REDACTED]")
    return text


def model_environment():
    return {name: value for name, value in os.environ.items()
            if not ("KEY" in name or "TOKEN" in name or "SECRET" in name
                    or name.startswith("ANTHROPIC_") or name.startswith("OPENAI_")
                    or name in ("CODEX_THREAD_ID", "CODEX_INTERNAL_ORIGINATOR_OVERRIDE"))}


def write_json(path, value):
    path.write_text(redact(json.dumps(value, indent=2, ensure_ascii=False)) + "\n")


def readback_changes(sent, saved, path="workflow"):
    """Require all submitted values; extra server defaults are allowed."""
    if isinstance(sent, dict):
        if not isinstance(saved, dict):
            return [path + ": expected object"]
        errors = []
        for key, value in sent.items():
            child = path + "." + key
            errors += ([child + ": removed"] if key not in saved
                       else readback_changes(value, saved[key], child))
        return errors
    if isinstance(sent, list):
        if not isinstance(saved, list) or len(sent) != len(saved):
            return [path + ": array changed"]
        return [error for index, value in enumerate(sent)
                for error in readback_changes(value, saved[index], f"{path}[{index}]")]
    return [] if sent == saved and isinstance(sent, bool) == isinstance(saved, bool) else [path + ": value changed"]


def source(path):
    path = path.resolve()
    raw = path.read_bytes()
    content = raw.decode("utf-8")
    label = str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else str(path)
    return {"path": label, "sha256": hashlib.sha256(raw).hexdigest(),
            "lines": len(content.splitlines())}, content


def resume_candidate(directory, sources, slot):
    directory = directory.resolve()
    previous = json.loads((directory / "manifest.json").read_text())
    if previous.get("sources") != sources:
        raise ValueError("Resume sources do not match the saved manifest in order, path, hash and line count.")
    if previous.get("slot") != slot:
        raise ValueError("Resume must use the saved workflow slot.")
    commit = previous.get("code_commit")
    if not isinstance(commit, str) or not commit.strip():
        raise ValueError("Resume manifest has no generation code commit.")
    attempts = previous.get("generation_attempts")
    if not isinstance(attempts, list) or not attempts or not isinstance(attempts[-1], dict):
        raise ValueError("Resume manifest has no recorded generation attempt.")
    attempt = attempts[-1].get("attempt")
    if type(attempt) is not int or attempt < 1:
        raise ValueError("Resume manifest has an invalid generation attempt.")
    path = directory / f"candidate-attempt-{attempt}.json"
    raw = path.read_bytes()
    return {"run_directory": str(directory), "code_commit": commit,
            "candidate_path": str(path), "candidate_sha256": hashlib.sha256(raw).hexdigest(),
            "generation_started_at": previous.get("started_at"),
            "generation_elapsed_seconds": previous.get("elapsed_seconds"),
            "reused_at": now()}, raw.decode("utf-8")


def repair_candidate(directory, sources, slot):
    """Use a same-input draft for one offline model repair, never unchanged reuse."""
    previous = json.loads((directory / "manifest.json").read_text())
    old_sources = previous.get("sources")
    if not isinstance(old_sources, list) or len(old_sources) != len(sources):
        raise ValueError("Repair seed needs the same ordered source files.")
    for old, current in zip(old_sources, sources):
        if not isinstance(old, dict) or old.get("path") != current["path"]:
            raise ValueError("Repair seed source paths/order do not match.")
        if current["path"] != "builder/prompt.md" and old != current:
            raise ValueError("Repair seed brief/API/platform sources must match exactly.")
    # Only this separate repair path permits a changed compiler prompt.
    metadata, raw = resume_candidate(directory, old_sources, slot)
    metadata["seeded_at"] = metadata.pop("reused_at")
    metadata["sources"] = old_sources
    return metadata, parse_model_output(raw)


def invoke(command, deadline, *, cwd=ROOT, env=None, input_text=None):
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise BudgetExpired("The build time budget ended.")
    process = subprocess.Popen(command, cwd=cwd, env=env, stdin=subprocess.PIPE,
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                               text=True, start_new_session=True)
    try:
        stdout, stderr = process.communicate(input_text, timeout=remaining)
    except (subprocess.TimeoutExpired, BudgetExpired):
        os.killpg(process.pid, signal.SIGKILL)
        stdout, stderr = process.communicate()
        error = BudgetExpired("The build time budget ended during " + Path(command[0]).name + ".")
        error.stdout = stdout
        error.stderr = stderr
        raise error from None
    except BaseException:
        os.killpg(process.pid, signal.SIGKILL)
        process.communicate()
        raise
    return process.returncode, stdout, stderr


def model_metadata(stdout, stderr, requested_model):
    events, errors = [], []
    model_match = re.search(r"^model:\s*(\S+)", stderr, re.MULTILINE)
    model = requested_model or (model_match.group(1) if model_match else "Codex CLI default (not reported)")
    for line in stdout.splitlines():
        try:
            event = json.loads(line)
        except ValueError:
            continue
        row = {"type": event.get("type", "unknown")}
        if isinstance(event.get("model"), str):
            model = event["model"]
        if isinstance(event.get("item"), dict):
            row["item_type"] = event["item"].get("type")
        if isinstance(event.get("usage"), dict):
            row["usage"] = {key: value for key, value in event["usage"].items()
                            if isinstance(value, (int, float))}
        if event.get("type") in ("error", "turn.failed"):
            error = event.get("error", event)
            message = error.get("message") if isinstance(error, dict) else str(error)
            if message:
                errors.append(redact(message)[:1000])
        events.append(row)
    return model, events, errors


def parse_model_output(text):
    text = text.strip()
    if text.startswith("```json\n") and text.endswith("\n```"):
        text = text[len("```json\n"):-len("\n```")]
    return json.loads(text)


def merge_patch(target, patch):
    """Apply RFC 7396 without changing the prior candidate."""
    if not isinstance(patch, dict):
        return copy.deepcopy(patch)
    merged = copy.deepcopy(target) if isinstance(target, dict) else {}
    for key, value in patch.items():
        if value is None:
            merged.pop(key, None)
        else:
            merged[key] = merge_patch(merged.get(key), value)
    return merged


def test_version_errors(simulations, version, reps):
    if not isinstance(simulations, list) or len(simulations) != reps:
        return [f"Expected version evidence for {reps} simulation(s)."]
    errors = []
    for index, simulation in enumerate(simulations, 1):
        if not isinstance(simulation, dict) or simulation.get("status") != "completed":
            errors.append(f"Simulation {index} did not complete.")
            continue
        versions = simulation.get("reported_agent_versions")
        if not isinstance(versions, list) or not versions or set(versions) != {version}:
            errors.append(f"Simulation {index} did not prove published version {version}.")
    return errors


def provenance_report(policy, brief_lines):
    numbered = {(label, number) for label, lines in brief_lines.items()
                for number, line in enumerate(lines, 1) if re.match(r"^\s*\d+\.\s", line)}
    covered, errors = set(), []
    rules = policy.get("source_rules") if isinstance(policy, dict) else None
    if not isinstance(rules, list):
        return {"ok": False, "errors": ["policy.source_rules must be a list"], "numbered_rules": len(numbered)}
    for index, rule in enumerate(rules):
        if not isinstance(rule, dict):
            errors.append(f"source_rules[{index}] must be an object")
            continue
        label, line = rule.get("source"), rule.get("line")
        if label not in brief_lines or type(line) is not int or not 1 <= line <= len(brief_lines[label]):
            errors.append(f"source_rules[{index}] has an unknown source or invalid line")
            continue
        evidence = (label, line)
        if any(source_label == label for source_label, _ in numbered) and evidence not in numbered:
            errors.append(f"source_rules[{index}] must point to the numbered rule header")
        covered.add(evidence)
    errors += [f"Missing numbered source rule: {label}:{line}" for label, line in sorted(numbered - covered)]
    return {"ok": not errors, "errors": errors, "numbered_rules": len(numbered),
            "covered_numbered_rules": len(numbered & covered)}


def self_check():
    assert not readback_changes({"a": [1, {"b": "x"}]}, {"a": [1, {"b": "x", "c": 2}], "d": 3})
    assert readback_changes({"a": {"b": 1}}, {"a": {}}) == ["workflow.a.b: removed"]
    assert readback_changes({"a": True}, {"a": 1})
    assert readback_changes({"a": [1]}, {"a": [1, 2]})
    model, rows, errors = model_metadata('{"type":"item.completed","item":{"type":"reasoning","text":"PRIVATE"}}\n', "model: test-model\n", None)
    assert model == "test-model" and "PRIVATE" not in json.dumps(rows) and not errors
    assert parse_model_output('{"workflow":{"nodes":{}}}') == {"workflow": {"nodes": {}}}
    assert parse_model_output('```json\n{"workflow":{"nodes":{}}}\n```') == {"workflow": {"nodes": {}}}
    verified = {"status": "completed", "reported_agent_versions": [4]}
    assert not test_version_errors([verified, verified, verified], 4, 3)
    assert test_version_errors([verified, verified, {"status": "completed", "reported_agent_versions": []}], 4, 3)
    assert test_version_errors([verified, {"status": "completed", "reported_agent_versions": [4, 5]}, verified], 4, 3)
    assert test_version_errors([verified], 4, 3)
    assert test_version_errors([{**verified, "status": "paused"}], 4, 1)
    assert all(not ("KEY" in key or "TOKEN" in key or "SECRET" in key) for key in model_environment())
    evidence = {"brief.md": ["1. One rule", "detail", "2. Another rule"]}
    assert provenance_report({"source_rules": [{"source": "brief.md", "line": 1}, {"source": "brief.md", "line": 3}]}, evidence)["ok"]
    assert not provenance_report({"source_rules": [{"source": "brief.md", "line": 2}]}, evidence)["ok"]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("briefs", nargs="+", type=Path, help="Complete brief files in precedence order")
    parser.add_argument("--openapi", required=True, type=Path)
    parser.add_argument("--slot", help="Own stable Freya slot; default: kaan-<first brief stem>")
    parser.add_argument("--offline", action="store_true", help="Generate and validate without Freya access")
    parser.add_argument("--resume-build", type=Path, help="Reuse the last complete saved candidate with identical sources; no generation or repair")
    parser.add_argument("--repair-build", type=Path, help="One offline model repair of a same-brief/API draft; current inputs remain authoritative")
    parser.add_argument("--model", default="gpt-6.1-sol", help="Builder model; default: gpt-6.1-sol")
    parser.add_argument("--brief", choices=["A", "B"], default="A", help="Official scorer brief filter")
    parser.add_argument("--only", default="PUB-01", help="Comma-separated official case ids")
    parser.add_argument("--reps", type=int, default=1)
    parser.add_argument("--budget-seconds", type=int, default=1800)
    args = parser.parse_args()
    if args.repair_build and (not args.offline or args.resume_build):
        parser.error("--repair-build requires --offline and cannot be combined with --resume-build")
    if not 1 <= args.budget_seconds <= 1800:
        parser.error("--budget-seconds must be between 1 and 1800")
    if args.reps < 1:
        parser.error("--reps must be at least 1")
    slot = args.slot or "kaan-" + args.briefs[0].stem
    if slot == "baseline-base":
        parser.error("The baseline-base slot is reserved; choose your own slot")
    started = time.monotonic()
    deadline = started + args.budget_seconds
    folder = KIT / "out" / dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    folder.mkdir(parents=True)
    manifest = {"started_at": now(), "status": "running", "budget_seconds": args.budget_seconds,
                "slot": slot, "offline": args.offline,
                "live_test": {"status": "not_run"}, "generation_attempts": [], "artifacts": str(folder)}
    trace = folder / "trace.jsonl"

    def event(kind, **details):
        with trace.open("a") as handle:
            handle.write(redact(json.dumps({"at": now(), "event": kind, **details}, ensure_ascii=False)) + "\n")

    def alarm(_signum, _frame):
        raise BudgetExpired("The build time budget ended.")

    previous_handler = signal.signal(signal.SIGALRM, alarm)
    signal.setitimer(signal.ITIMER_REAL, max(0.001, deadline - time.monotonic()))
    lock = None
    exit_code = 2
    event("begin", slot=slot, budget_seconds=args.budget_seconds)
    print("Build output:", folder, flush=True)
    try:
        if not args.offline:
            if not os.environ.get("FREYA_API_KEY") or os.environ["FREYA_API_KEY"] == "fak_your_key_here":
                manifest["status"] = "blocked_missing_credentials"
                raise ValueError("Set FREYA_API_KEY in build-the-builder/.env or env.sh, or use --offline.")
            if len(os.environ.get("FREYA_BANK_TEAM_KEY", "")) < 16:
                manifest["status"] = "blocked_missing_credentials"
                raise ValueError("FREYA_BANK_TEAM_KEY must contain at least 16 characters.")
        code, commit, _ = invoke(["git", "rev-parse", "HEAD"], deadline)
        if code:
            raise RuntimeError("Could not read the code commit.")
        _, dirty, _ = invoke(["git", "status", "--porcelain"], deadline)
        manifest.update(code_commit=commit.strip(), code_dirty=bool(dirty.strip()),
                        code_changes=dirty.splitlines())
        docs = [ROOT / "builder/prompt.md", KIT / "docs/workflow-format.md",
                KIT / "docs/tools-and-code.md", KIT / "docs/api.md"]
        sources, sections, brief_lines = [], [], {}
        inputs = folder / "inputs"
        inputs.mkdir()
        for index, path in enumerate([*args.briefs, args.openapi, *docs]):
            metadata, content = source(path)
            sources.append(metadata)
            if index < len(args.briefs):
                brief_lines[metadata["path"]] = content.splitlines()
            if index <= len(args.briefs):
                copy_name = f"brief-{index + 1:02d}-{path.name}" if index < len(args.briefs) else "openapi.json"
                (inputs / copy_name).write_text(redact(content))
            if index == len(args.briefs):
                openapi = json.loads(content)
            numbered = "\n".join(f"{number}: {line}" for number, line in enumerate(content.splitlines(), 1))
            sections.append(f"\n=== SOURCE {metadata['path']} ({metadata['lines']} lines) ===\n{numbered}\n=== END SOURCE ===\n")
        manifest["sources"] = sources
        prompt = ("Build from the complete source files below. Briefs are in precedence order; later briefs amend earlier ones. "
                  "Use only these supplied inputs. Do not use tools or read local files. "
                  "Return a plain JSON object with policy, workflow, checks, uncertainties, and summary; no private reasoning. "
                  "All source line numbers are 1-based.\n"
                  + "\n".join(sections))
        (folder / "input-prompt.txt").write_text(redact(prompt))
        command = ["codex", "exec", "--ignore-user-config", "--ephemeral", "--json", "--color", "never",
                   "-s", "read-only", "-o", str(folder / "raw.json")]
        for feature in ("shell_tool", "unified_exec", "apps", "plugins", "hooks", "multi_agent"):
            command += ["--disable", feature]
        if args.model:
            command += ["--model", args.model]
        command.append("-")
        from builder.validation import validate
        model_prompt, all_events, candidate = prompt, [], None
        if args.repair_build:
            lock = (KIT / ".builder.lock").open("a")
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                raise RuntimeError("Another builder owns the local workspace lock.") from None
            seed, candidate = repair_candidate(args.repair_build, sources, slot)
            if not isinstance(candidate, dict) or set(candidate) != {"policy", "workflow", "checks", "uncertainties", "summary"}:
                raise ValueError("Repair seed must be a complete candidate.")
            manifest["repair_seed"] = seed
            event("candidate_seeded_for_model_repair", **seed)
            seed_report = validate(candidate["workflow"], candidate["policy"], openapi, candidate["checks"], brief_lines=brief_lines)
            write_json(folder / "seed-validation.json", seed_report)
            model_prompt = (prompt + "\n=== UNTRUSTED STARTING DRAFT (NOT A RULE SOURCE) ===\n"
                            + redact(json.dumps(candidate)) + "\n=== CURRENT VALIDATION ERRORS ===\n"
                            + redact(json.dumps(seed_report))
                            + "\nReturn ONLY a JSON merge patch (RFC 7396) repairing this draft against ALL current inputs. "
                            "Arrays replace completely; null deletes. Implement the current conversation contract. "
                            "Do not weaken checks or trust old policy facts. This is the only model attempt.\n")
        if args.resume_build:
            reuse, raw_text = resume_candidate(args.resume_build, sources, slot)
            manifest["resume_build"] = reuse
            event("candidate_reused", **reuse)
            print("Revalidating the saved candidate; no model generation or repair.", flush=True)
        for attempt in ((1,) if args.resume_build or args.repair_build else (1, 2, 3)):
            output_format = "merge_patch" if candidate is not None else "full_candidate"
            raw_path = folder / "raw.json"
            if not args.resume_build:
                purpose = ("Repair an untrusted same-input draft against the current compiler contract." if args.repair_build else
                           "Extract sourced policy and generate the portable workflow and local checks." if attempt == 1
                           else "Repair the generated candidate using validation errors and the same complete source inputs.")
                event("model_begin", attempt=attempt, model=args.model or "Codex CLI default", purpose=purpose, output_format=output_format)
                print("Generating policy and workflow with Codex." if attempt == 1 else "Repairing the candidate from validation errors.", flush=True)
                try:
                    returncode, stdout, stderr = invoke(command, deadline, env=model_environment(), input_text=model_prompt)
                except BudgetExpired as error:
                    _, rows, _ = model_metadata(getattr(error, "stdout", ""), getattr(error, "stderr", ""), args.model)
                    write_json(folder / "model-events.json", all_events + [{"attempt": attempt, **row} for row in rows])
                    raise
                model, rows, errors = model_metadata(stdout, stderr, args.model)
                manifest["builder_model"] = model
                all_events += [{"attempt": attempt, **row} for row in rows]
                write_json(folder / "model-events.json", all_events)
                event("model_end", attempt=attempt, model=model, purpose=purpose, output_format=output_format, exit_code=returncode)
                if returncode:
                    raise RuntimeError("Codex generation failed: " + ("; ".join(errors) or redact(stderr)[-1200:]))
                raw_text = raw_path.read_text()
            raw_path.write_text(redact(raw_text))
            (folder / f"raw-attempt-{attempt}.json").write_text(redact(raw_text))
            try:
                raw = parse_model_output(raw_text)
                if candidate is not None:
                    raw = merge_patch(candidate, raw)
                if not isinstance(raw, dict) or set(raw) != {"policy", "workflow", "checks", "uncertainties", "summary"}:
                    raise ValueError("Model result must contain exactly policy/workflow/checks/uncertainties/summary.")
                if not isinstance(raw["uncertainties"], list) or any(not isinstance(item, str) for item in raw["uncertainties"]) or not isinstance(raw["summary"], str):
                    raise ValueError("Model uncertainties must be a string list and summary must be a string.")
                candidate = raw
                write_json(raw_path, raw)
                write_json(folder / f"candidate-attempt-{attempt}.json", raw)
                policy, workflow, checks = (raw[key] for key in ("policy", "workflow", "checks"))
                for name, value in (("policy", policy), ("workflow", workflow), ("checks", checks)):
                    write_json(folder / f"{name}.json", value)
                    write_json(folder / f"{name}-attempt-{attempt}.json", value)
                manifest.update(uncertainties=raw["uncertainties"], summary=raw["summary"])
                report = validate(workflow, policy, openapi, checks, brief_lines=brief_lines)
                evidence = provenance_report(policy, brief_lines)
                report["provenance"] = evidence
                report.setdefault("errors", []).extend(evidence["errors"])
                if not evidence["ok"]:
                    report.update(ok=False, valid=False)
            except (ValueError, TypeError, KeyError) as error:
                report = {"ok": False, "valid": False, "errors": [f"{type(error).__name__}: {error}"], "checks": []}
            write_json(folder / "validation.json", report)
            write_json(folder / f"validation-attempt-{attempt}.json", report)
            valid = bool(report.get("valid", report.get("ok"))) and not report.get("errors")
            event("local_validation", attempt=attempt, valid=valid, errors=report.get("errors", []))
            if valid and not args.offline:
                import freya
                if lock is None:
                    lock = (KIT / ".builder.lock").open("a")
                    try:
                        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    except BlockingIOError:
                        raise RuntimeError("Another builder owns the local workspace lock; wait before validating or publishing.") from None
                try:
                    dry_run = freya.validate_workflow(slot, workflow)
                except RuntimeError as error:
                    dry_run = {"ok": False, "error": redact(str(error))}
                    write_json(folder / "freya-validation.json", dry_run)
                    write_json(folder / f"freya-validation-attempt-{attempt}.json", dry_run)
                    if not re.search(r" -> (400|422):", str(error)):
                        event("freya_validation", attempt=attempt, valid=False, error=redact(str(error)))
                        raise
                dry_run_failed = isinstance(dry_run, dict) and (
                    dry_run.get("ok") is False or dry_run.get("success") is False or dry_run.get("errors"))
                write_json(folder / "freya-validation.json", dry_run)
                write_json(folder / f"freya-validation-attempt-{attempt}.json", dry_run)
                report["freya_validation"] = dry_run
                if dry_run_failed:
                    report.setdefault("errors", []).append("Freya dry-run rejected the candidate: " + redact(json.dumps(dry_run, ensure_ascii=False)))
                    report.update(ok=False, valid=False)
                    valid = False
                write_json(folder / "validation.json", report)
                write_json(folder / f"validation-attempt-{attempt}.json", report)
                event("freya_validation", attempt=attempt, valid=not dry_run_failed)
            if args.resume_build:
                manifest["resume_validation"] = {"valid": valid, "errors": report.get("errors", [])}
            else:
                manifest["generation_attempts"].append({"attempt": attempt, "model": model, "valid": valid,
                                                         "output_format": output_format,
                                                         "errors": report.get("errors", [])})
            if valid or args.resume_build:
                break
            repair_instruction = (
                "For this repair, override earlier full-output instructions: return ONLY a JSON merge patch (RFC 7396) "
                "with changed policy/workflow/checks/uncertainties/summary fields. Omit unchanged fields. "
                "Objects merge recursively, null deletes a key, and arrays replace the whole array. "
                "Include complete replacement code strings only when they change."
                if candidate is not None else
                "Return a complete corrected plain JSON object with policy/workflow/checks/uncertainties/summary.")
            model_prompt = (prompt + "\n=== PRIOR GENERATED CANDIDATE ===\n" + redact(json.dumps(candidate) if candidate is not None else raw_text)
                            + "\n=== VALIDATION ERRORS ===\n" + redact(json.dumps(report, ensure_ascii=False))
                            + "\n" + repair_instruction + " "
                            "Use only the original inputs for business facts. Do not weaken checks or skip source rules.\n")
        if not valid:
            raise ValueError("Candidate failed validation; see validation.json.")
        if args.offline:
            manifest["status"] = "completed_local"
            exit_code = 0
        else:
            ids = freya.save_workflow(slot, workflow, state_file=str(KIT / ".freya-agents.json"))
            manifest.update(agent_id=ids["agent_id"], workflow_id=ids["workflow_id"])
            event("workflow_saved", **ids)
            # A create does not run the client's model repair and publish path.
            version = ids.get("version")
            if version is None:
                version = freya.update_workflow(ids["workflow_id"], workflow)
                state_path = KIT / ".freya-agents.json"
                state = json.loads(state_path.read_text())
                state[slot]["version"] = version
                write_json(state_path, state)
            saved = freya.api("GET", f"/api/v2/workflow/{ids['workflow_id']}",
                             workspaceId=freya.workspace_id())["workflow"]["workflow"]
            changes = readback_changes(workflow, saved)
            changes += readback_changes(freya.AGENT_LLM, (saved.get("agent_config") or {}).get("llmConfig", {}),
                                        "workflow.agent_config.llmConfig")
            write_json(folder / "readback.json", {"ok": not changes, "changes": changes})
            if changes:
                raise ValueError("Freya changed submitted fields; see readback.json.")
            versions = freya.api("GET", f"/api/v2/versions/workflow/{ids['workflow_id']}",
                                 workspaceId=freya.workspace_id())["versions"]
            newest = max(versions, key=lambda item: item["versionNumber"])
            write_json(folder / "versions.json", versions)
            if newest["versionNumber"] != version or not newest.get("isPublished"):
                raise ValueError("The newest generated workflow version is not published.")
            manifest.update(published_version=version, published_version_id=newest["id"])
            freya.export_workflow(ids["workflow_id"], str(folder / "export.workflow.json"))
            export_path = folder / "export.workflow.json"
            write_json(export_path, json.loads(export_path.read_text()))
            event("workflow_verified", agent_id=ids["agent_id"], workflow_id=ids["workflow_id"], published_version=version)
            test_command = [sys.executable, str(ROOT / "scripts/test_agent.py"), ids["agent_id"],
                            "--brief", args.brief, "--only", args.only, "--reps", str(args.reps)]
            manifest["live_test"] = {"status": "running", "brief": args.brief, "only": args.only, "reps": args.reps}
            event("test_begin", **manifest["live_test"])
            print(f"Testing {args.only or args.brief}, {args.reps} run(s), version {version}.", flush=True)
            try:
                returncode, stdout, stderr = invoke(test_command, deadline, cwd=KIT,
                    env={**os.environ, "FREYA_BUILDER_LOCK_OWNER": str(os.getpid())})
            except BudgetExpired as error:
                (folder / "test-console.log").write_text(redact(getattr(error, "stdout", "") + getattr(error, "stderr", "")))
                manifest["live_test"].update(status="incomplete_budget", remote_simulation_may_continue=True)
                raise
            (folder / "test-console.log").write_text(redact(stdout + stderr))
            output_match = re.search(r"^Output:\s*(.+)$", stdout, re.MULTILINE)
            if not output_match:
                raise RuntimeError("Test helper did not report its output folder; see test-console.log.")
            result_folder = Path(output_match.group(1).strip())
            manifest["live_test"].update(output=str(result_folder), exit_code=returncode)
            summary = json.loads((result_folder / "summary.json").read_text())
            manifest["live_test"].update(summary)
            if summary["status"] != "completed":
                manifest["status"] = "incomplete_test"
                raise RuntimeError("Live test did not complete; inspect its summary.json.")
            results = json.loads((result_folder / "official-results.json").read_text())
            manifest["live_test"].update(simulation_id=results["simulation_id"], iteration_id=results["iteration_id"])
            tested_versions = set(summary.get("reported_agent_versions", []))
            verification_errors = test_version_errors(summary.get("simulations"), version, args.reps)
            manifest["live_test"].update(reported_agent_versions=sorted(tested_versions),
                                         version_verification_errors=verification_errors,
                                         tested_version_verified=not verification_errors and tested_versions == {version})
            event("test_end", **manifest["live_test"])
            if verification_errors or tested_versions != {version}:
                raise RuntimeError("Tested agent version could not be matched to the published version.")
            manifest["status"] = "completed"
            exit_code = returncode
    except BudgetExpired as error:
        manifest.update(status="incomplete_budget", error=str(error))
        print("INCOMPLETE: time budget ended; this is not a scored failure.", flush=True)
    except Exception as error:
        if manifest["status"] == "running":
            manifest["status"] = "incomplete"
        manifest.update(error=redact(str(error)), error_type=type(error).__name__)
        print("INCOMPLETE:", redact(str(error)), flush=True)
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, previous_handler)
        if lock:
            lock.close()
        manifest.update(ended_at=now(), elapsed_seconds=round(time.monotonic() - started, 2))
        write_json(folder / "manifest.json", manifest)
        event("end", status=manifest["status"], elapsed_seconds=manifest["elapsed_seconds"])
        print("Manifest:", folder / "manifest.json", flush=True)
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
