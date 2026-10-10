#!/usr/bin/env python3
"""Run the unmodified official scorer, keeping failures distinct from blocked runs."""
import argparse
import contextlib
import datetime as dt
import json
import os
from pathlib import Path
import sys
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
    parser.add_argument("--brief", choices=["A", "B"], default="A")
    parser.add_argument("--only", help="Comma-separated public case ids, e.g. PUB-01")
    parser.add_argument("--style", choices=["pieces", "corrects", "talkative", "asks_back", "in_words"])
    parser.add_argument("--reps", type=int, default=1)
    parser.add_argument("--cases", type=Path, help="Custom expectations/personas for existing case ids")
    args = parser.parse_args()
    if args.reps < 1:
        parser.error("--reps must be at least 1")
    if not os.environ.get("FREYA_API_KEY") or os.environ["FREYA_API_KEY"] == "fak_your_key_here":
        parser.error("Set FREYA_API_KEY in build-the-builder/env.sh")
    if len(os.environ.get("FREYA_BANK_TEAM_KEY", "")) < 16:
        parser.error("FREYA_BANK_TEAM_KEY must contain at least 16 characters")
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
    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    folder = KIT / "results" / (stamp + "-" + agent_id[:8])
    folder.mkdir(parents=True)
    report = {"started_at": now(), "agent_id": agent_id, "brief": args.brief,
              "style": args.style, "reps": args.reps,
              "cases": [c["id"] for c in selected], "status": "running"}
    import freya
    import score
    import run_cases
    # Keep the original scoring rules; change only transport error reporting.
    score.http = bank_http
    run_cases.http = bank_http
    sys.argv = ["run_cases.py", agent_id, "--brief", args.brief, "--cases", str(cases_path),
                "--reps", str(args.reps), "--out", str(folder / "official-results.json")]
    if args.only:
        sys.argv += ["--only", args.only]
    if args.style:
        sys.argv += ["--style", args.style]
    print("Output:", folder, flush=True)
    exit_code = 0
    with (folder / "console.log").open("w") as log:
        with contextlib.redirect_stdout(Tee(sys.stdout, log)), contextlib.redirect_stderr(Tee(sys.stderr, log)):
            try:
                run_cases.main()
                results = json.loads((folder / "official-results.json").read_text())
                report.update(status="completed", passed=results["passed"], total=results["total"])
                calls = sorted({r["call_id"] for rows in results["all_rows"] for r in rows if r.get("call_id")})
                (folder / "calls").mkdir()
                report["transcript_errors"] = []
                for call_id in calls:
                    try:
                        call = freya.get_call(call_id)
                        (folder / "calls" / (call_id + ".json")).write_text(
                            redact(json.dumps(call, indent=2, ensure_ascii=False)))
                    except Exception as error:
                        report["transcript_errors"].append({"call_id": call_id, "error": redact(str(error))})
                exit_code = 0 if results["passed"] == results["total"] else 1
            except BankUnavailable as error:
                report.update(status="blocked_by_bank", error=error.details)
                print("BLOCKED: bank service unavailable; no complete score was produced.")
                print(json.dumps(error.details, ensure_ascii=False, indent=2))
                exit_code = 2
            except Exception as error:
                report.update(status="incomplete", error=redact(str(error)), error_type=type(error).__name__)
                print("INCOMPLETE:", type(error).__name__, redact(str(error)))
                exit_code = 2
    report["ended_at"] = now()
    (folder / "summary.json").write_text(json.dumps(report, indent=2, ensure_ascii=False))
    print("Summary:", folder / "summary.json", flush=True)
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
