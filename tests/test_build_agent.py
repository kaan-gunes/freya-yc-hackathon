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
            saved = {**candidate["workflow"], "agent_config": {"llmConfig": freya.AGENT_LLM}}
            results = kit / "results" / "mock"
            (results / "calls").mkdir(parents=True)
            (results / "summary.json").write_text(json.dumps({
                "status": "completed", "passed": 1, "total": 1,
                "reported_agent_versions": [7],
                "simulations": [{"status": "completed", "reported_agent_versions": [7]}],
            }))
            (results / "official-results.json").write_text(json.dumps({
                "simulation_id": "mock-simulation", "iteration_id": "mock-iteration",
            }))
            prompts = []

            def invoke(command, deadline, **kwargs):
                if command[:2] == ["git", "rev-parse"]:
                    return 0, "synthetic-commit\n", ""
                if command[:2] == ["git", "status"]:
                    return 0, "", ""
                if command[0] == "codex":
                    self.assertNotIn("FREYA_API_KEY", kwargs["env"])
                    self.assertNotIn("FREYA_BANK_TEAM_KEY", kwargs["env"])
                    Path(command[command.index("-o") + 1]).write_text(json.dumps(candidate))
                    prompts.append(kwargs["input_text"])
                    return 0, '{"type":"turn.completed"}\n', ""
                self.assertTrue(command[1].endswith("/scripts/test_agent.py"))
                self.assertEqual(kwargs["env"]["FREYA_BUILDER_LOCK_OWNER"], str(os.getpid()))
                return 0, "Output: " + str(results) + "\n", ""

            def save(*args, **kwargs):
                self.assertEqual(dry_run.call_count, 2, "save occurred before a passing dry-run")
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
                    patch("builder.validation.validate", side_effect=lambda *args: copy.deepcopy(local)), \
                    patch("freya.validate_workflow", side_effect=[RuntimeError(error), {"ok": True}]) as dry_run, \
                    patch("freya.save_workflow", side_effect=save) as save_workflow, \
                    patch("freya.workspace_id", return_value="mock-workspace"), \
                    patch("freya.api", side_effect=api), patch("freya.export_workflow", side_effect=export), \
                    patch.dict(os.environ, {"FREYA_API_KEY": "fak_synthetic_not_live",
                                            "FREYA_BANK_TEAM_KEY": "synthetic_bank_team_key"}), \
                    patch("sys.argv", ["build_agent.py", str(brief), "--openapi", str(openapi),
                                       "--budget-seconds", "60"]):
                self.assertEqual(runner.main(), 0)
                self.assertEqual(save_workflow.call_count, 1)
            folder = next((kit / "out").iterdir())
            manifest = json.loads((folder / "manifest.json").read_text())
            self.assertEqual(manifest["status"], "completed")
            self.assertEqual([attempt["valid"] for attempt in manifest["generation_attempts"]], [False, True])
            self.assertEqual(len(prompts), 2)
            self.assertIn(prompts[0], prompts[1])
            self.assertIn(error, prompts[1])
            self.assertNotIn("fak_synthetic_not_live", prompts[1])
            self.assertNotIn("synthetic_bank_team_key", prompts[1])
            self.assertTrue(manifest["live_test"]["tested_version_verified"])
            self.assertTrue(json.loads((folder / "readback.json").read_text())["ok"])
            self.assertTrue((folder / "export.workflow.json").exists())
            self.assertFalse(json.loads((folder / "freya-validation-attempt-1.json").read_text())["ok"])


if __name__ == "__main__":
    unittest.main()
