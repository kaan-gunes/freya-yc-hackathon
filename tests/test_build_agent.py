import copy
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parent.parent
SPEC = importlib.util.spec_from_file_location("build_agent_runner", ROOT / "scripts/build_agent.py")
runner = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(runner)
import freya


class BuildAgentChecks(unittest.TestCase):
    def test_dry_run_rejection_is_repaired_before_save(self):
        self.run_mock_build()

    def test_two_dry_run_rejections_are_repaired_on_third_attempt_with_the_same_deadline(self):
        self.run_mock_build(dry_run_rejections=2)

    def test_merge_patch_updates_nested_fields_replaces_arrays_and_keeps_prior_immutable(self):
        prior = {"workflow": {"nodes": {"guard": {"code": "old code", "config": {"url": "bank", "timeout": 5, "obsolete": True}}}},
                 "checks": [{"id": "old-1"}, {"id": "old-2"}], "untouched": {"values": [1]}, "removed": 1}
        before = copy.deepcopy(prior)
        patch = {"workflow": {"nodes": {"guard": {"code": "new code", "config": {"timeout": 10, "obsolete": None}}}},
                 "checks": [{"id": "new"}], "removed": None}
        merged = runner.merge_patch(prior, patch)
        self.assertEqual(merged["workflow"]["nodes"]["guard"], {"code": "new code", "config": {"url": "bank", "timeout": 10}})
        self.assertEqual(merged["checks"], [{"id": "new"}])
        self.assertNotIn("removed", merged)
        self.assertEqual(prior, before)
        merged["untouched"]["values"].append(2)
        merged["checks"][0]["id"] = "changed after merge"
        self.assertEqual(prior, before)
        self.assertEqual(patch["checks"], [{"id": "new"}])
        self.assertEqual(runner.merge_patch([1], {"new": 2}), {"new": 2})
        self.assertIsNone(runner.merge_patch(prior, None))

    def test_sparse_repair_is_validated_as_a_complete_candidate_before_publish(self):
        self.run_mock_build(repair_patches=[{"workflow": {"nodes": {"guard": {"code": "repaired"}}},
                                            "checks": [{"id": "replacement"}]}],
                            expected_workflow={"nodes": {"guard": {"code": "repaired"}}}, expected_checks=[{"id": "replacement"}])

    def test_malformed_first_response_requests_a_full_candidate_before_sparse_repair(self):
        self.run_mock_build(malformed_first=True)

    def test_checked_version_survives_later_read_error_and_unrelated_raw_call(self):
        manifest = self.run_mock_build(
            simulation_extra={"read_errors": [{"source": "/api/v2/simulations/mock-simulation/iterations/mock-iteration",
                                                 "error": "GET metadata -> 503: unavailable"}],
                              "version_evidence": [{"source": "/api/v2/simulations/mock-simulation",
                                                    "field": "agentVersionNumber", "version": 7}]},
            raw_call={"id": "unrelated-call", "entityId": "other-agent", "agentVersionNumber": 99})
        self.assertEqual(manifest["live_test"]["reported_agent_versions"], [7])
        self.assertEqual(len(manifest["live_test"]["simulations"][0]["read_errors"]), 1)

    def run_mock_build(self, *, simulation_extra=None, raw_call=None, dry_run_rejections=1,
                       repair_patches=None, expected_workflow=None, expected_checks=None, malformed_first=False):
        with tempfile.TemporaryDirectory() as directory:
            kit = Path(directory).resolve() / "kit"
            (kit / "docs").mkdir(parents=True)
            for name in ("workflow-format.md", "tools-and-code.md", "api.md"):
                (kit / "docs" / name).write_text("Platform format\n")
            brief, openapi = kit / "brief.md", kit / "openapi.json"
            brief.write_text("1. Synthetic rule\n")
            openapi.write_text("{}")
            candidate = {"policy": {"source_rules": [{"source": str(brief), "line": 1}]},
                         "workflow": {"nodes": {}}, "checks": [],
                         "uncertainties": [], "summary": "Synthetic mock."}
            expected_workflow = candidate["workflow"] if expected_workflow is None else expected_workflow
            expected_checks = candidate["checks"] if expected_checks is None else expected_checks
            repair_patches = repair_patches or [{"summary": f"Repaired attempt {attempt}."} for attempt in range(2, dry_run_rejections + 2)]
            saved = {**expected_workflow, "agent_config": {"llmConfig": freya.AGENT_LLM}}
            results = kit / "results" / "mock"
            (results / "calls").mkdir(parents=True)
            (results / "summary.json").write_text(json.dumps({
                "status": "completed", "passed": 1, "total": 1,
                "reported_agent_versions": [7],
                "simulations": [{"status": "completed", "reported_agent_versions": [7],
                                 **(simulation_extra or {})}],
            }))
            if raw_call is not None:
                (results / "calls" / "unrelated.json").write_text(json.dumps(raw_call))
            (results / "official-results.json").write_text(json.dumps({
                "simulation_id": "mock-simulation", "iteration_id": "mock-iteration",
            }))
            prompts, deadlines = [], []

            def invoke(command, deadline, **kwargs):
                deadlines.append(deadline)
                if command[:2] == ["git", "rev-parse"]:
                    return 0, "synthetic-commit\n", ""
                if command[:2] == ["git", "status"]:
                    return 0, "", ""
                if command[0] == "codex":
                    self.assertNotIn("FREYA_API_KEY", kwargs["env"])
                    self.assertNotIn("FREYA_BANK_TEAM_KEY", kwargs["env"])
                    index = len(prompts)
                    payload = ("not JSON" if malformed_first and index == 0 else json.dumps(
                        candidate if index == int(malformed_first) else repair_patches[index - 1 - int(malformed_first)]))
                    Path(command[command.index("-o") + 1]).write_text(payload)
                    prompts.append(kwargs["input_text"])
                    return 0, '{"type":"turn.completed"}\n', ""
                self.assertTrue(command[1].endswith("/scripts/test_agent.py"))
                self.assertEqual(kwargs["env"]["FREYA_BUILDER_LOCK_OWNER"], str(os.getpid()))
                return 0, "Output: " + str(results) + "\n", ""

            def save(*args, **kwargs):
                self.assertEqual(dry_run.call_count, dry_run_rejections + 1, "save occurred before a passing dry-run")
                self.assertEqual(args[1], expected_workflow)
                return {"agent_id": "mock-agent", "workflow_id": "mock-workflow", "version": 7}

            def api(method, path, **kwargs):
                self.assertEqual(method, "GET")
                if path == "/api/v2/workflow/mock-workflow":
                    return {"workflow": {"workflow": saved}}
                self.assertEqual(path, "/api/v2/versions/workflow/mock-workflow")
                return {"versions": [{"id": "mock-version", "versionNumber": 7, "isPublished": True}]}

            def export(workflow_id, path):
                self.assertEqual(workflow_id, "mock-workflow")
                Path(path).write_text(json.dumps({"workflow_id": workflow_id, "workflow": saved}))

            local = {"ok": True, "valid": True, "errors": [], "checks": []}
            error = "POST /api/v2/workflow -> 400: Missing workflow.tools.0.function.description"
            with patch.object(runner, "KIT", kit), patch.object(runner, "invoke", invoke), \
                    patch("builder.validation.validate", side_effect=lambda *args: copy.deepcopy(local)) as local_validation, \
                    patch("freya.validate_workflow", side_effect=[RuntimeError(error)] * dry_run_rejections + [{"ok": True}]) as dry_run, \
                    patch("freya.save_workflow", side_effect=save) as save_workflow, \
                    patch("freya.workspace_id", return_value="mock-workspace"), \
                    patch("freya.api", side_effect=api), patch("freya.export_workflow", side_effect=export), \
                    patch.dict(os.environ, {"FREYA_API_KEY": "fak_synthetic_not_live",
                                            "FREYA_BANK_TEAM_KEY": "synthetic_bank_team_key"}), \
                    patch("sys.argv", ["build_agent.py", str(brief), "--openapi", str(openapi),
                                       "--budget-seconds", "60"]):
                self.assertEqual(runner.main(), 0)
                self.assertEqual(save_workflow.call_count, 1)
                self.assertEqual(local_validation.call_count, dry_run_rejections + 1)
                self.assertEqual(local_validation.call_args.args[0], expected_workflow)
                self.assertEqual(local_validation.call_args.args[1], candidate["policy"])
                self.assertEqual(local_validation.call_args.args[3], expected_checks)
            folder = next((kit / "out").iterdir())
            manifest = json.loads((folder / "manifest.json").read_text())
            self.assertEqual(manifest["status"], "completed")
            total_attempts = dry_run_rejections + 1 + int(malformed_first)
            first_full = 1 + int(malformed_first)
            self.assertEqual([attempt["valid"] for attempt in manifest["generation_attempts"]], [False] * (total_attempts - 1) + [True])
            self.assertEqual([attempt["output_format"] for attempt in manifest["generation_attempts"]],
                             ["full_candidate"] * first_full + ["merge_patch"] * dry_run_rejections)
            self.assertEqual(len(prompts), total_attempts)
            self.assertEqual(len(set(deadlines)), 1, "repair must not extend the fixed builder deadline")
            for prompt in prompts[1:]:
                self.assertIn(prompts[0], prompt)
                self.assertNotIn("fak_synthetic_not_live", prompt)
                self.assertNotIn("synthetic_bank_team_key", prompt)
            if malformed_first:
                self.assertIn("Return a complete corrected plain JSON object", prompts[1])
                self.assertNotIn("return ONLY a JSON merge patch", prompts[1])
            for prompt in prompts[first_full:]:
                self.assertIn(error, prompt)
                self.assertIn("return ONLY a JSON merge patch (RFC 7396)", prompt)
            self.assertEqual(json.loads((folder / "raw.json").read_text())["workflow"], expected_workflow)
            self.assertTrue(manifest["live_test"]["tested_version_verified"])
            self.assertTrue(json.loads((folder / "readback.json").read_text())["ok"])
            self.assertTrue((folder / "export.workflow.json").exists())
            for attempt in range(1, total_attempts + 1):
                for artifact in ("raw", "validation"):
                    self.assertTrue((folder / f"{artifact}-attempt-{attempt}.json").exists())
                if attempt < first_full:
                    continue
                for artifact in ("candidate", "policy", "workflow", "checks", "freya-validation"):
                    self.assertTrue((folder / f"{artifact}-attempt-{attempt}.json").exists())
                complete = json.loads((folder / f"candidate-attempt-{attempt}.json").read_text())
                self.assertEqual(set(complete), set(candidate))
                self.assertEqual(complete["policy"], candidate["policy"])
                if attempt > first_full:
                    self.assertEqual(json.loads((folder / f"raw-attempt-{attempt}.json").read_text()), repair_patches[attempt - first_full - 1])
                self.assertEqual(json.loads((folder / f"freya-validation-attempt-{attempt}.json").read_text())["ok"],
                                 attempt == total_attempts)
            trace = [json.loads(line) for line in (folder / "trace.jsonl").read_text().splitlines()]
            for event in ("model_begin", "model_end", "local_validation", "freya_validation"):
                self.assertEqual([row["attempt"] for row in trace if row["event"] == event],
                                 list(range(first_full if event == "freya_validation" else 1, total_attempts + 1)))
            self.assertEqual([row["attempt"] for row in json.loads((folder / "model-events.json").read_text())],
                             list(range(1, total_attempts + 1)))
            return manifest


if __name__ == "__main__":
    unittest.main()
