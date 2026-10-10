#!/usr/bin/env python3
"""Run the unmodified official scorer, keeping failures distinct from blocked runs."""
import argparse
import contextlib
import datetime as dt
import fcntl
import json
import os
from pathlib import Path
import re
import sys
import time
import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parent.parent
KIT = ROOT / "build-the-builder"
sys.path[:0] = [str(KIT / "tools"), str(KIT)]


def redact(text):
    for name in ("FREYA_API_KEY", "FREYA_BANK_TEAM_KEY"):
        value = os.environ.get(name)
        if value:
            text = text.replace(value, "[REDACTED]")
    return text


class BankUnavailable(RuntimeError):
    def __init__(self, details):
        self.details = details
        super().__init__(json.dumps(details, ensure_ascii=False))


class SimulationIncomplete(RuntimeError):
    pass


def acquire_test_lock():
    # shortcut: the inherited parent PID coordinates local scripts, use a shared lock service for remote testers.
    if os.environ.get("FREYA_BUILDER_LOCK_OWNER") == str(os.getppid()):
        return None
    lock = (KIT / ".builder.lock").open("a")
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        lock.close()
        raise RuntimeError("Another builder or test owns the local workspace lock; wait before testing.") from None
    return lock


def call_diagnostics(call):
    diagnostics = []
    for index, message in enumerate(call.get("messages", [])):
        if message.get("role") != "system":
            continue
        event = message.get("message")
        if isinstance(event, str):
            try:
                event = json.loads(event)
            except ValueError:
                continue
        if not isinstance(event, dict):
            continue
        name = str(event.get("event", "")).lower()
        result = event.get("result") if isinstance(event.get("result"), dict) else {}
        validation_errors = result.get("validation_errors", [])
        reason = str(event.get("reason", event.get("error", ""))).lower()
        kinds = []
        if name in ("function_call_complete", "function_call_complete_deferred") and validation_errors:
            kinds.append("state_write_rejected")
        if "extract" in name and (event.get("success") is False or event.get("accepted") is False
                or event.get("status") in ("failed", "error", "rejected") or name == "extraction_failed"
                or any(word in reason for word in ("failed", "rejected", "invalid", "discarded", "below threshold", "below_threshold", "low confidence", "low_confidence"))):
            kinds.append("extraction_failure")
        if name == "route_evaluated" and event.get("matched") is False:
            kinds.append("router_unmatched")
        if "fallback" in name or (name == "node_enter" and "fallback" in str(event.get("reason", "")).lower()):
            kinds.append("router_fallback")
        details = {key: event[key] for key in ("event", "function", "name", "reason", "error", "confidence", "value",
                                             "matched", "from_node", "target", "status", "accepted", "success") if key in event}
        if validation_errors:
            details["validation_errors"] = validation_errors
        text = json.dumps(details, ensure_ascii=False)
        for kind in kinds:
            diagnostics.append({"kind": kind, "message_id": message.get("messageId", index),
                                "node_id": message.get("nodeId"), "event": redact(text)[:2000]})
    return diagnostics


class RunEvidence:
    """Observe the official runner's I/O; resume only reads already known remote runs."""

    def __init__(self, folder, report, freya, api, bank, resume=False):
        self.folder, self.report, self.freya = folder, report, freya
        self.original_api, self.original_bank, self.resume = api, bank, resume
        self.current, self.index = None, 0

    def save(self):
        self.report["reported_agent_versions"] = sorted({version for run in self.report["simulations"]
                for version in run["reported_agent_versions"]}, key=str)
        for name, value in (("simulations.json", self.report["simulations"]), ("summary.json", self.report)):
            path = self.folder / name
            temporary = path.with_suffix(".tmp")
            temporary.write_text(redact(json.dumps(value, indent=2, ensure_ascii=False)))
            temporary.replace(path)

    def add_versions(self, source, records, entity=False):
        run = self.current
        for record in records:
            if not isinstance(record, dict):
                continue
            owners = [record[key] for key in ("agentId", "entityId", "assistantId") if record.get(key) is not None]
            if owners and any(owner != self.report["agent_id"] for owner in owners):
                continue
            if record.get("simulationId", run["simulation_id"]) != run["simulation_id"]:
                continue
            if record.get("iterationId", run["iteration_id"]) != run["iteration_id"]:
                continue
            field = "entityVersionNumber" if entity else "agentVersionNumber"
            version = record.get(field)
            if isinstance(version, bool) or not isinstance(version, int) or version < 1:
                continue
            evidence = {"source": source, "field": field, "version": version,
                        "call_id": record.get("callId", record.get("id") if entity else None)}
            if evidence not in run["version_evidence"]:
                run["version_evidence"].append(evidence)
            run["reported_agent_versions"] = sorted({item["version"] for item in run["version_evidence"]}, key=str)

    def api(self, method, path, body=None, **params):
        if self.resume and method != "GET":
            raise RuntimeError("Resume is read-only; refusing to repeat a remote write.")
        run = self.current
        if run and method == "POST" and path == "/api/v2/simulations":
            run["execution_status"] = "creating"
            self.save()
        try:
            value = freya_read_retry(self.original_api, method, path, body, **params)
        except Exception as error:
            if run:
                run["read_errors"].append({"source": path, "error": redact(str(error))})
                if method == "POST":
                    run["execution_status"] = "creation_unknown"
                self.save()
            raise
        if not run:
            return value
        if method == "POST" and path == "/api/v2/simulations":
            simulation = value.get("simulation") or value
            run.update(simulation_id=simulation["id"], status=simulation.get("status", "submitted"),
                       execution_status=simulation.get("status", "submitted"))
            self.add_versions(path, [simulation])
            self.save()
        simulation_path = f"/api/v2/simulations/{run['simulation_id']}"
        if method == "GET" and path == simulation_path:
            simulation = value.get("simulation") or value
            if simulation.get("id") != run["simulation_id"] or simulation.get("agentId", self.report["agent_id"]) != self.report["agent_id"]:
                raise RuntimeError("Simulation metadata does not belong to this agent/run.")
            run.update(status=simulation.get("status", run["status"]), execution_status=simulation.get("status", run["execution_status"]))
            self.add_versions(path, [simulation])
        elif method == "GET" and path == simulation_path + "/iterations":
            iterations = (value.get("iterations") or value.get("items") or []) if isinstance(value, dict) else value
            if iterations and not run["iteration_id"]:
                run["iteration_id"] = iterations[0]["id"]
        elif method == "GET" and path == simulation_path + f"/iterations/{run['iteration_id']}":
            iteration = value.get("iteration", {})
            if (iteration.get("id", run["iteration_id"]) != run["iteration_id"]
                    or iteration.get("simulationId", run["simulation_id"]) != run["simulation_id"]):
                raise RuntimeError("Iteration metadata does not belong to this run.")
            self.add_versions(path, [iteration])
            expected_personas = set(run["persona_ids"].values())
            runs = [item for item in value.get("runs", []) if item.get("personaId") in expected_personas]
            for item in runs:
                if (item.get("agentId", self.report["agent_id"]) != self.report["agent_id"]
                        or item.get("simulationId", run["simulation_id"]) != run["simulation_id"]
                        or item.get("iterationId", run["iteration_id"]) != run["iteration_id"]):
                    raise RuntimeError("Selected persona run metadata does not belong to this agent/run.")
            for item in runs:
                if item.get("callId"):
                    run["call_ids"] = sorted(set(run["call_ids"] + [item["callId"]]))
            self.add_versions(path, runs)
            run["results_status"] = "reading"
        elif method == "GET" and path.startswith("/api/v2/call/"):
            call_id = path.rsplit("/", 1)[-1]
            call = value.get("call", {})
            if (call_id not in run["call_ids"] or call.get("id") != call_id
                    or call.get("simulationId", run["simulation_id"]) != run["simulation_id"]
                    or call.get("iterationId", run["iteration_id"]) != run["iteration_id"]):
                raise RuntimeError("Call metadata does not belong to this run.")
            owners = [call[key] for key in ("agentId", "entityId", "assistantId") if call.get(key) is not None]
            if any(owner != self.report["agent_id"] for owner in owners):
                raise RuntimeError("Call metadata belongs to another agent.")
            entity_type = call.get("assistantEntityType", call.get("entityType", "agent"))
            if str(entity_type).lower() not in ("agent", "workflow"):
                raise RuntimeError("Call metadata does not describe an agent.")
            self.add_versions(path, [call], entity=True)
            self.add_versions(path, [call])
            if not re.fullmatch(r"[A-Za-z0-9_-]+", call_id):
                raise RuntimeError("Invalid call identifier.")
            (self.folder / "calls" / (call_id + ".json")).write_text(redact(json.dumps(call, indent=2, ensure_ascii=False)))
            run["diagnostics"] = [item for item in run["diagnostics"] if item["call_id"] != call_id]
            run["diagnostics"].extend({"call_id": call_id, **item} for item in call_diagnostics(call))
        self.save()
        return value

    def bank(self, path, body=None):
        run = self.current
        if body is not None:
            if self.resume:
                if path != "/v1/practice/sessions" or body["case"] not in run["sessions"]:
                    raise RuntimeError("Resume cannot recreate missing bank sessions.")
                return {"variables": run["sessions"][body["case"]]}
            run["execution_status"] = "creating_sessions"
            self.save()
        try:
            value = self.original_bank(path, body)
        except Exception as error:
            run["read_errors"].append({"source": path, "error": redact(str(error))})
            if body is not None:
                run["execution_status"] = "session_creation_unknown"
            self.save()
            raise
        if path == "/v1/practice/sessions":
            run["sessions"][body["case"]] = value["variables"]
            run["session_ids"][body["case"]] = value.get("sessionId", value.get("session_id", value["variables"].get("customer_id")))
        elif path.startswith("/v1/practice/ledger/"):
            run["ledger_customer_ids"] = sorted(set(run["ledger_customer_ids"] + [path.rsplit("/", 1)[-1]]))
            run["results_status"] = "reading"
        self.save()
        return value

    def resume_simulation(self, agent_id, name, variables_by_persona, **kwargs):
        run = self.current
        if agent_id != self.report["agent_id"] or not run.get("simulation_id"):
            raise RuntimeError("No known simulation to resume; an ambiguous POST will not be repeated.")
        while True:
            value = self.freya.api("GET", f"/api/v2/simulations/{run['simulation_id']}")
            status = (value.get("simulation") or value).get("status")
            if status in ("completed", "failed", "paused"):
                break
            time.sleep(10)
        if not run["iteration_id"]:
            self.freya.api("GET", f"/api/v2/simulations/{run['simulation_id']}/iterations")
        if not run["iteration_id"]:
            raise SimulationIncomplete("The known simulation has no readable iteration yet.")
        return run["simulation_id"], run["iteration_id"], status

    def run_once(self, original, agent_id, cases, ids):
        if self.resume:
            self.current = self.report["simulations"][self.index]
            ids = self.current["persona_ids"]
        else:
            self.current = {"simulation_id": None, "iteration_id": None, "status": "preparing",
                    "execution_status": "preparing", "results_status": "pending", "scoring_status": "pending",
                    "sessions": {}, "session_ids": {}, "persona_ids": ids, "rows": [], "call_ids": [], "ledger_customer_ids": [],
                    "reported_agent_versions": [], "version_evidence": [], "read_errors": [], "diagnostics": []}
            self.report["simulations"].append(self.current)
        self.index += 1
        self.current.update(results_status="pending", scoring_status="pending")
        self.save()
        try:
            result = original(agent_id, cases, ids)
            rows, simulation_id, iteration_id, status, seconds, _ = result
            self.current.update(rows=rows, simulation_id=simulation_id, iteration_id=iteration_id,
                                status=status, execution_status=status, seconds=seconds)
            if status != "completed":
                raise SimulationIncomplete(f"Simulation {simulation_id} ended as {status}; no complete score was produced.")
            self.current.update(results_status="complete", scoring_status="complete")
            return result
        except Exception:
            self.current.update(results_status="failed", scoring_status="incomplete")
            raise
        finally:
            for call_id in self.current["call_ids"]:
                try:
                    self.freya.get_call(call_id)
                except Exception as error:
                    self.report["transcript_errors"].append({"call_id": call_id, "error": redact(str(error))})
            self.save()


def freya_read_retry(api, method, path, body=None, **params):
    for attempt in range(4):
        try:
            return api(method, path, body, **params)
        except RuntimeError as error:
            if method != "GET" or not str(error).startswith(f"GET {path} -> 503:") or attempt == 3:
                raise
            delay = 2 ** (attempt + 1)
            print(f"Freya GET returned 503; retrying in {delay} seconds ({attempt + 1}/3).", flush=True)
            time.sleep(delay)


def decode_bank_response(path, status, headers, raw):
    text = redact(raw.decode("utf-8", errors="replace"))
    details = {"path": path, "http_status": status,
               "cloudflare_ray": headers.get("CF-Ray"),
               "content_type": headers.get("Content-Type")}
    try:
        data = json.loads(text)
    except ValueError:
        raise BankUnavailable({**details, "response": text[:1000],
                               "cause": "Bank returned a non-JSON response."}) from None
    if status >= 400:
        raise BankUnavailable({**details, "response": data,
                               "cause": "Bank rejected the request."})
    if path == "/v1/practice/sessions" and (
            not isinstance(data, dict) or not isinstance(data.get("variables"), dict)):
        raise BankUnavailable({**details, "response": data,
                               "cause": "Bank did not create a practice customer."})
    return data


def bank_http(path, body=None):
    import score
    headers = dict(score.UA)
    headers["x-team-key"] = os.environ["FREYA_BANK_TEAM_KEY"]
    request = urllib.request.Request(
        score.HOST + path,
        data=json.dumps(body).encode() if body is not None else None,
        headers=headers, method="POST" if body is not None else "GET")
    try:
        response = urllib.request.urlopen(request, timeout=20)
    except urllib.error.HTTPError as error:
        response = error
    except (urllib.error.URLError, TimeoutError) as error:
        raise BankUnavailable({"path": path, "cause": redact(str(error))}) from None
    with response:
        return decode_bank_response(path, response.status, response.headers, response.read())


class Tee:
    def __init__(self, terminal, log):
        self.terminal, self.log = terminal, log

    def write(self, text):
        text = redact(text)
        self.terminal.write(text)
        self.log.write(text)
        self.flush()
        return len(text)

    def flush(self):
        self.terminal.flush()
        self.log.flush()


def now():
    return dt.datetime.now(dt.timezone.utc).isoformat()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("agent_id", nargs="?", help="Default: the saved baseline agent")
    parser.add_argument("--brief", choices=["A", "B"])
    parser.add_argument("--only", help="Comma-separated public case ids, e.g. PUB-01")
    parser.add_argument("--style", choices=["pieces", "corrects", "talkative", "asks_back", "in_words"])
    parser.add_argument("--reps", type=int)
    parser.add_argument("--cases", type=Path, help="Custom expectations/personas for existing case ids")
    parser.add_argument("--resume", type=Path, help="Read and score known runs from an existing result folder; no remote writes")
    args = parser.parse_args()
    if args.reps is not None and args.reps < 1:
        parser.error("--reps must be at least 1")
    if not os.environ.get("FREYA_API_KEY") or os.environ["FREYA_API_KEY"] == "fak_your_key_here":
        parser.error("Set FREYA_API_KEY in build-the-builder/env.sh")
    if len(os.environ.get("FREYA_BANK_TEAM_KEY", "")) < 16:
        parser.error("FREYA_BANK_TEAM_KEY must contain at least 16 characters")
    report = None
    if args.resume:
        if any(value is not None for value in (args.brief, args.only, args.style, args.reps, args.cases)):
            parser.error("--resume reuses the saved cases, style and repetitions; do not add run filters")
        folder = args.resume.resolve()
        report = json.loads((folder / "summary.json").read_text())
        if args.agent_id and args.agent_id != report["agent_id"]:
            parser.error("The requested agent does not own this saved run")
        if not report["simulations"] or any(not run.get("simulation_id") for run in report["simulations"]):
            parser.error("A simulation id is missing. Resolve the ambiguous create request first; no POST will be repeated")
        if any(set(run.get("sessions", {})) != set(report["cases"]) for run in report["simulations"]):
            parser.error("Saved bank sessions are incomplete; resume cannot recreate them")
        args.agent_id, args.brief, args.style, args.reps = report["agent_id"], report["brief"], report["style"], len(report["simulations"])
        args.only, args.cases = ",".join(report["cases"]), folder / "cases.json"
        report.update(status="running", resumed_at=now())
        for key in ("passed", "total", "ended_at", "error", "error_type"):
            report.pop(key, None)
    args.brief, args.reps = args.brief or "A", args.reps or 1
    agent_id = args.agent_id
    if not agent_id:
        state = KIT / ".freya-agents.json"
        agents = json.loads(state.read_text()) if state.exists() else {}
        agent_id = agents.get("baseline-base", {}).get("agent_id")
        if not agent_id:
            parser.error("Provide an agent_id; no saved baseline was found")
    cases_path = args.cases.resolve() if args.cases else KIT / "public-test-set.json"
    cases = json.loads(cases_path.read_text())
    selected = [c for c in cases if c["brief"] == args.brief
                and (not args.only or c["id"] in args.only.split(","))]
    if not selected:
        parser.error("No cases match these filters")
    if not report:
        stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        folder = KIT / "results" / (stamp + "-" + agent_id[:8])
        folder.mkdir(parents=True)
        report = {"started_at": now(), "agent_id": agent_id, "brief": args.brief,
                  "style": args.style, "reps": args.reps,
                  "cases": [c["id"] for c in selected], "status": "running",
                  "simulations": [], "reported_agent_versions": [], "transcript_errors": []}
        (folder / "cases.json").write_text(redact(json.dumps(selected, indent=2, ensure_ascii=False)))
    import freya
    import score
    import run_cases
    # Keep the original scoring rules; capture evidence and classify incomplete runs.
    original_run_once = run_cases.run_once
    original_api = freya.api
    original_simulation, original_personas = freya.run_simulation, freya.create_personas
    original_score_http, original_runner_http = score.http, run_cases.http
    (folder / "calls").mkdir(exist_ok=True)
    evidence = RunEvidence(folder, report, freya, original_api, bank_http, resume=bool(args.resume))
    evidence.save()

    if args.resume:
        # The official runner may rebuild its local persona cache; reuse the saved remote IDs.
        saved_ids = report["simulations"][0]["persona_ids"]
        persona_names = {run_cases.persona_for(case, {"identity": case["identity"]}, args.style)["name"]: saved_ids[case["id"]]
                         for case in selected}
        freya.create_personas = lambda specs: {"personas": [{"id": persona_names[spec["name"]]} for spec in specs]}
        freya.run_simulation = evidence.resume_simulation
    run_cases.run_once = lambda *arguments: evidence.run_once(original_run_once, *arguments)
    score.http = run_cases.http = evidence.bank
    sys.argv = ["run_cases.py", agent_id, "--brief", args.brief, "--cases", str(cases_path),
                "--reps", str(args.reps), "--out", str(folder / "official-results.json")]
    if args.only:
        sys.argv += ["--only", args.only]
    if args.style:
        sys.argv += ["--style", args.style]
    print("Output:", folder, flush=True)
    exit_code = 0
    lock = None
    with (folder / "console.log").open("a" if args.resume else "w") as log:
        with contextlib.redirect_stdout(Tee(sys.stdout, log)), contextlib.redirect_stderr(Tee(sys.stderr, log)):
            try:
                lock = acquire_test_lock()
                freya.api = evidence.api
                run_cases.main()
                results = json.loads((folder / "official-results.json").read_text())
                if args.reps == report["reps"]:
                    report.update(status="completed", passed=results["passed"], total=results["total"])
                    exit_code = 0 if results["passed"] == results["total"] else 1
                else:
                    report.update(status="incomplete", partial_passed=results["passed"], partial_total=results["total"],
                                  error="Known runs were recovered; requested repetitions are still missing.")
                    exit_code = 2
            except BankUnavailable as error:
                report.update(status="blocked_by_bank", error=error.details)
                print("BLOCKED: bank service unavailable; no complete score was produced.")
                print(json.dumps(error.details, ensure_ascii=False, indent=2))
                exit_code = 2
            except Exception as error:
                report.update(status="incomplete", error=redact(str(error)), error_type=type(error).__name__)
                print("INCOMPLETE:", type(error).__name__, redact(str(error)))
                exit_code = 2
            finally:
                run_cases.run_once = original_run_once
                freya.api = original_api
                freya.run_simulation, freya.create_personas = original_simulation, original_personas
                score.http, run_cases.http = original_score_http, original_runner_http
                if lock:
                    lock.close()
    report["ended_at"] = now()
    evidence.save()
    print("Summary:", folder / "summary.json", flush=True)
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
