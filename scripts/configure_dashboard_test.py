#!/usr/bin/env python3
"""Attach the organiser's existing synthetic fixture to the sample's dashboard test.

This only supplies test inputs. It does not create a new bank customer or change policy.
Run from build-the-builder after sourcing env.sh.
"""
import argparse
import datetime as dt
import json
from pathlib import Path
import sys

KIT = Path(__file__).resolve().parent.parent / "build-the-builder"
sys.path.insert(0, str(KIT))
import freya


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source_workflow_id")
    args = parser.parse_args()
    source = freya.api("GET", f"/api/v2/workflow/{args.source_workflow_id}",
                       workspaceId=freya.workspace_id())["workflow"]["workflow"]
    inputs = source.get("test_variables") or {}
    if not inputs.get("customer_id"):
        raise SystemExit("The source workflow has no configured practice customer.")
    workflow = json.loads((KIT / "examples/base-agent.json").read_text())
    for key in ("customer_id", "first_name", "last_name", "title", "now"):
        if key not in inputs:
            raise SystemExit(f"Missing test input: {key}")
        workflow.setdefault("test_variables", {})[key] = inputs[key]
    # Expected identity answers remain outside the phone agent's context.
    state_file = KIT / ".freya-agents.json"
    result = freya.save_workflow("baseline-base", workflow, state_file=str(state_file))
    report = {"at": dt.datetime.now(dt.timezone.utc).isoformat(),
              "source_workflow_id": args.source_workflow_id, **result,
              "updated_test_inputs": ["customer_id", "first_name", "last_name", "title", "now"],
              "policy_changed": False,
              "warning": "Dashboard fixture is shared and resets only as documented; not a fresh scored session."}
    folder = KIT / "results"
    folder.mkdir(exist_ok=True)
    (folder / "dashboard-baseline-setup.json").write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
