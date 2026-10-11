import copy
import hashlib
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
    def test_offline_seed_repair_is_one_model_call_and_never_unchanged_reuse(self):
        for invalid in (False, True):
            with self.subTest(invalid=invalid), tempfile.TemporaryDirectory() as directory:
                kit = Path(directory)
                (kit / "docs").mkdir()
                brief, api = kit / "brief.md", kit / "api.json"
                brief.write_text("1. A synthetic source rule\n")
                api.write_text("{}")
                for name in ("workflow-format.md", "tools-and-code.md", "api.md"):
                    (kit / "docs" / name).write_text("Synthetic format\n")
                paths = [brief, api, ROOT / "builder/prompt.md", *[kit / "docs" / name for name in ("workflow-format.md", "tools-and-code.md", "api.md")]]
                sources = [runner.source(path)[0] for path in paths]
                previous = kit / "seed"
                previous.mkdir()
                old_sources = copy.deepcopy(sources)
                old_sources[2]["sha256"] = "old-prompt-hash"
                (previous / "manifest.json").write_text(json.dumps({"sources": old_sources, "slot": "kaan-brief", "code_commit": "old-code", "generation_attempts": [{"attempt": 1}]}))
                draft = {"policy": {"source_rules": [{"source": sources[0]["path"], "line": 1}]}, "workflow": {"nodes": {"guard": "old"}}, "checks": [], "uncertainties": [], "summary": "Old draft"}
                path = previous / "candidate-attempt-1.json"
                path.write_text(json.dumps(draft))
                original = path.read_bytes()
                calls, deadlines = [], []
                def invoke(command, deadline, **kwargs):
                    deadlines.append(deadline)
                    if command[:2] == ["git", "rev-parse"]:
                        return 0, "new-code\n", ""
                    if command[:2] == ["git", "status"]:
                        return 0, "", ""
                    self.assertEqual(command[0], "codex")
                    calls.append(kwargs["input_text"])
                    Path(command[command.index("-o") + 1]).write_text(json.dumps({"workflow": {"nodes": {"guard": "repaired"}}}))
                    return 0, '{"type":"turn.completed"}\n', ""
                bad = {"ok": False, "errors": ["conversation error"], "checks": []}
                with patch.object(runner, "KIT", kit), patch.object(runner, "invoke", invoke), \
                     patch("builder.validation.validate", side_effect=[bad, bad if invalid else {"ok": True, "errors": [], "checks": []}]), \
                     patch("freya.validate_workflow") as dry_run, patch("freya.save_workflow") as save, patch("freya.api") as remote, \
                     patch("sys.argv", ["build_agent.py", str(brief), "--openapi", str(api), "--offline", "--repair-build", str(previous), "--budget-seconds", "60"]):
                    self.assertEqual(runner.main(), 2 if invalid else 0)
                dry_run.assert_not_called(); save.assert_not_called(); remote.assert_not_called()
                self.assertEqual(len(calls), 1)
                self.assertEqual(len(set(deadlines)), 1)
                self.assertIn("NOT A RULE SOURCE", calls[0])
                self.assertEqual(path.read_bytes(), original)
                output = next((kit / "out").iterdir())
                manifest = json.loads((output / "manifest.json").read_text())
                self.assertEqual(len(manifest["generation_attempts"]), 1)
                self.assertEqual(manifest["generation_attempts"][0]["output_format"], "merge_patch")
                self.assertEqual(manifest["live_test"]["status"], "not_run")
                self.assertNotIn("resume_build", manifest)
                self.assertEqual(manifest["repair_seed"]["candidate_sha256"], hashlib.sha256(original).hexdigest())
                self.assertEqual(json.loads((output / "candidate-attempt-1.json").read_text())["workflow"]["nodes"]["guard"], "repaired")
                trace = (output / "trace.jsonl").read_text()
                self.assertIn("candidate_seeded_for_model_repair", trace)
                self.assertNotIn("candidate_reused", trace)
                for index in (0, 1, 3, 4, 5):
                    changed = copy.deepcopy(sources)
                    changed[index]["sha256"] = "changed-input"
                    with self.assertRaisesRegex(ValueError, "sources must match exactly"):
                        runner.repair_candidate(previous, changed, "kaan-brief")
                with self.assertRaisesRegex(ValueError, "Resume sources do not match"):
                    runner.resume_candidate(previous, sources, "kaan-brief")

    def test_seed_repair_rejects_online_or_resume_combination_before_any_work(self):
        for flags in (["--repair-build", "seed"], ["--offline", "--repair-build", "seed", "--resume-build", "seed"]):
            with self.subTest(flags=flags), patch("sys.argv", ["build_agent.py", "brief", "--openapi", "api", *flags]), \
                 patch.object(runner, "invoke") as invoke, self.assertRaises(SystemExit):
                runner.main()
            invoke.assert_not_called()

    def test_resume_revalidates_and_uses_existing_publish_readback_export_test_path(self):
        self.run_mock_build(resume=True, dry_run_rejections=0)

    def test_resume_rejects_each_changed_source_before_platform_access(self):
        for index in range(6):
            with self.subTest(source=index):
                self.run_mock_build(resume=True, resume_failure=f"source-{index}", dry_run_rejections=0)

    def test_resume_rejects_missing_sources_and_candidate_before_platform_access(self):
        for failure in ("missing-source", "missing-candidate", "missing-manifest", "missing-manifest-source", "source-order",
                        "slot", "commit", "attempt"):
            with self.subTest(failure=failure):
                self.run_mock_build(resume=True, resume_failure=failure, dry_run_rejections=0)

    def test_resume_rejects_bad_candidate_or_provenance_before_platform_access(self):
        for failure in ("json", "shape", "invalid", "provenance"):
            with self.subTest(failure=failure):
                self.run_mock_build(resume=True, resume_failure=failure, dry_run_rejections=0)

    def test_resume_dry_run_rejection_stops_without_save_generation_or_repair(self):
        self.run_mock_build(resume=True, resume_failure="dry-run", dry_run_rejections=1)

    def test_resume_budget_expiry_stops_before_save(self):
        self.run_mock_build(resume=True, resume_failure="budget", dry_run_rejections=0)

    def test_resume_keeps_lock_readback_and_version_gates(self):
        for failure in ("lock", "readback", "version"):
            with self.subTest(failure=failure):
                self.run_mock_build(resume=True, resume_failure=failure, dry_run_rejections=0)

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

    def test_repair_merges_the_uncompiled_draft_and_recompiles_before_publish(self):
        self.run_mock_build(compiler_marker=True, expected_workflow={"nodes": {}, "compiler_marker": True})

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
                       repair_patches=None, expected_workflow=None, expected_checks=None, malformed_first=False,
                       resume=False, resume_failure=None, compiler_marker=False):
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
            original_source = runner.source
            source_paths = [brief, openapi, ROOT / "builder/prompt.md",
                            *[kit / "docs" / name for name in ("workflow-format.md", "tools-and-code.md", "api.md")]]
            previous = kit / "previous-run"
            previous.mkdir()
            old_manifest = {"sources": [original_source(path)[0] for path in source_paths],
                            "slot": "kaan-brief", "code_commit": "original-generation-commit",
                            "started_at": "2026-10-11T10:00:00+00:00", "elapsed_seconds": 1200,
                            "generation_attempts": [{"attempt": 3}]}
            if resume_failure == "missing-manifest-source":
                old_manifest["sources"].pop()
            if resume_failure == "source-order":
                old_manifest["sources"].reverse()
            if resume_failure == "slot":
                old_manifest["slot"] = "different-slot"
            if resume_failure == "commit":
                old_manifest.pop("code_commit")
            if resume_failure == "attempt":
                old_manifest["generation_attempts"][-1]["attempt"] = "../candidate"
            if resume_failure == "provenance":
                candidate["policy"]["source_rules"] = []
            if resume_failure == "shape":
                candidate.pop("summary")
            (previous / "manifest.json").write_text(json.dumps(old_manifest))
            candidate_path = previous / "candidate-attempt-3.json"
            candidate_path.write_text("broken JSON" if resume_failure == "json" else json.dumps(candidate))
            original_candidate = candidate_path.read_bytes()
            if resume_failure == "missing-candidate":
                candidate_path.unlink()
            if resume_failure == "missing-manifest":
                (previous / "manifest.json").unlink()

            def current_source(path):
                if resume_failure == "missing-source" and path == openapi:
                    raise FileNotFoundError("Missing source")
                metadata, content = original_source(path)
                if path in source_paths and resume_failure == f"source-{source_paths.index(path)}":
                    content = '{"changed": true}' if path == openapi else content + "\nChanged source\n"
                    metadata.update(sha256=hashlib.sha256(content.encode()).hexdigest(), lines=len(content.splitlines()))
                return metadata, content

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
            from builder.compiler import compile_candidate as actual_compile
            def compile_candidate(value, schema=None):
                if not compiler_marker:
                    return actual_compile(value)
                self.assertNotIn("compiler_marker", value["workflow"])
                compiled = copy.deepcopy(value)
                compiled["workflow"]["compiler_marker"] = True
                return compiled, []

            def invoke(command, deadline, **kwargs):
                deadlines.append(deadline)
                if command[:2] == ["git", "rev-parse"]:
                    return 0, "synthetic-commit\n", ""
                if command[:2] == ["git", "status"]:
                    return 0, "", ""
                if command[0] == "codex":
                    self.assertFalse(resume, "resume must never generate or repair")
                    self.assertNotIn("FREYA_API_KEY", kwargs["env"])
                    self.assertNotIn("FREYA_BANK_TEAM_KEY", kwargs["env"])
                    index = len(prompts)
                    if compiler_marker and index:
                        self.assertNotIn("compiler_marker", kwargs["input_text"])
                    payload = ("not JSON" if malformed_first and index == 0 else json.dumps(
                        candidate if index == int(malformed_first) else repair_patches[index - 1 - int(malformed_first)]))
                    Path(command[command.index("-o") + 1]).write_text(payload)
                    prompts.append(kwargs["input_text"])
                    return 0, '{"type":"turn.completed"}\n', ""
                self.assertTrue(command[1].endswith("/scripts/test_agent.py"))
                self.assertNotIn(resume_failure, ("lock", "readback", "version"))
                self.assertEqual(kwargs["env"]["FREYA_BUILDER_LOCK_OWNER"], str(os.getpid()))
                return 0, "Output: " + str(results) + "\n", ""

            def save(*args, **kwargs):
                self.assertEqual(dry_run.call_count, dry_run_rejections + 1, "save occurred before a passing dry-run")
                self.assertEqual(args[1], expected_workflow)
                return {"agent_id": "mock-agent", "workflow_id": "mock-workflow", "version": 7}

            def api(method, path, **kwargs):
                self.assertEqual(method, "GET")
                if path == "/api/v2/workflow/mock-workflow":
                    return {"workflow": {"workflow": {**saved, "nodes": []} if resume_failure == "readback" else saved}}
                self.assertEqual(path, "/api/v2/versions/workflow/mock-workflow")
                return {"versions": [{"id": "mock-version", "versionNumber": 7, "isPublished": resume_failure != "version"}]}

            def export(workflow_id, path):
                self.assertEqual(workflow_id, "mock-workflow")
                Path(path).write_text(json.dumps({"workflow_id": workflow_id, "workflow": saved}))

            local = {"ok": resume_failure != "invalid", "valid": resume_failure != "invalid",
                     "errors": ["Invalid current workflow"] if resume_failure == "invalid" else [], "checks": []}
            error = "POST /api/v2/workflow -> 400: Missing workflow.tools.0.function.description"
            with patch.object(runner, "KIT", kit), patch.object(runner, "invoke", invoke), \
                    patch("builder.compiler.compile_candidate", side_effect=compile_candidate), \
                    patch.object(runner, "source", side_effect=current_source), \
                    patch("builder.validation.validate", side_effect=lambda *args, **kwargs: copy.deepcopy(local)) as local_validation, \
                    patch("freya.validate_workflow", side_effect=([runner.BudgetExpired("Time budget ended")] if resume_failure == "budget"
                                                                else [RuntimeError(error)] * dry_run_rejections + [{"ok": True}])) as dry_run, \
                    patch("freya.save_workflow", side_effect=save) as save_workflow, \
                    patch("freya.workspace_id", return_value="mock-workspace"), \
                    patch("freya.api", side_effect=api) as remote_read, patch("freya.export_workflow", side_effect=export) as remote_export, \
                    patch.dict(os.environ, {"FREYA_API_KEY": "fak_synthetic_not_live",
                                            "FREYA_BANK_TEAM_KEY": "synthetic_bank_team_key"}), \
                    patch("sys.argv", ["build_agent.py", str(brief), "--openapi", str(openapi),
                                       "--budget-seconds", "60", *(["--resume-build", str(previous)] if resume else [])]):
                if resume_failure == "lock":
                    with patch.object(runner.fcntl, "flock", side_effect=BlockingIOError):
                        code = runner.main()
                else:
                    code = runner.main()
                self.assertEqual(code, 2 if resume_failure else 0)
                if resume:
                    folder = next((kit / "out").iterdir())
                    manifest = json.loads((folder / "manifest.json").read_text())
                    trace = [json.loads(line) for line in (folder / "trace.jsonl").read_text().splitlines()]
                    self.assertEqual(manifest["generation_attempts"], [])
                    self.assertFalse(prompts)
                    self.assertFalse(any(row["event"].startswith("model_") for row in trace))
                    self.assertNotIn("builder_model", manifest)
                    self.assertEqual(len(set(deadlines)), 1)
                    if candidate_path.exists():
                        self.assertEqual(candidate_path.read_bytes(), original_candidate)
                    if resume_failure:
                        self.assertEqual(manifest["status"], "incomplete_budget" if resume_failure == "budget" else "incomplete")
                        self.assertIn("error", manifest)
                        self.assertEqual(save_workflow.call_count, int(resume_failure in ("readback", "version")))
                        remote_export.assert_not_called()
                        if resume_failure not in ("dry-run", "readback", "version", "budget"):
                            dry_run.assert_not_called()
                            remote_read.assert_not_called()
                        else:
                            self.assertEqual(dry_run.call_count, 1)
                        return manifest
                    self.assertEqual(manifest["status"], "completed")
                    self.assertEqual(manifest["resume_build"]["code_commit"], "original-generation-commit")
                    self.assertEqual(manifest["resume_build"]["candidate_sha256"], hashlib.sha256(original_candidate).hexdigest())
                    self.assertEqual(manifest["resume_build"]["generation_elapsed_seconds"], 1200)
                    self.assertTrue(manifest["resume_build"]["reused_at"])
                    self.assertTrue(manifest["resume_validation"]["valid"])
                    self.assertTrue(manifest["live_test"]["tested_version_verified"])
                    self.assertTrue(json.loads((folder / "readback.json").read_text())["ok"])
                    self.assertEqual(local_validation.call_count, 1)
                    self.assertEqual(dry_run.call_count, 1)
                    self.assertEqual(save_workflow.call_count, 1)
                    self.assertEqual(remote_export.call_count, 1)
                    self.assertEqual(json.loads((folder / "candidate-attempt-1.json").read_text()), candidate)
                    self.assertTrue((folder / "export.workflow.json").exists())
                    self.assertIn("candidate_reused", [row["event"] for row in trace])
                    return manifest
                self.assertEqual(save_workflow.call_count, 1)
                self.assertEqual(local_validation.call_count, dry_run_rejections + 1)
                self.assertEqual(local_validation.call_args.args[0], expected_workflow)
                self.assertEqual(local_validation.call_args.args[1], candidate["policy"])
                self.assertEqual(local_validation.call_args.args[3], expected_checks)
                self.assertEqual(local_validation.call_args.kwargs["brief_lines"], {str(brief): ["1. Synthetic rule"]})
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
