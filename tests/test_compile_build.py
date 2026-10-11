import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parent.parent
SPEC = importlib.util.spec_from_file_location("compile_build_runner", ROOT / "scripts/build_agent.py")
runner = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(runner)


class CompileBuildChecks(unittest.TestCase):
    def test_compile_requires_offline_and_excludes_resume_and_model_repair(self):
        for flags in (
            ["--compile-build", "seed"],
            ["--offline", "--compile-build", "seed", "--resume-build", "seed"],
            ["--offline", "--compile-build", "seed", "--repair-build", "seed"],
        ):
            with self.subTest(flags=flags), patch("sys.argv", ["build_agent.py", "brief", "--openapi", "api", *flags]), \
                    patch.object(runner, "invoke") as invoke, \
                    patch("builder.compiler.compile_candidate") as compile_candidate, self.assertRaises(SystemExit):
                runner.main()
            invoke.assert_not_called()
            compile_candidate.assert_not_called()

    def test_compiles_once_validates_the_result_and_records_source_without_remote_calls(self):
        self.run_compile()

    def test_compiled_result_remains_reusable_without_any_generation_attempt(self):
        self.run_compile(resume=True)

    def test_invalid_compilation_or_missing_provenance_cannot_succeed(self):
        for failure in ("compiler", "validation", "provenance"):
            with self.subTest(failure=failure):
                self.run_compile(failure=failure)

    def test_seed_requires_matching_brief_api_platform_sources_and_slot(self):
        # Only the compiler prompt may differ on this explicit compilation path.
        for changed in (0, 1, 3, 4, 5, "slot", "order"):
            with self.subTest(changed=changed):
                self.run_compile(changed=changed)

    def test_resume_pins_compiler_but_explicit_recompile_accepts_changed_compiler(self):
        with tempfile.TemporaryDirectory() as directory:
            seed = Path(directory)
            compiler_source = runner.source(ROOT / "builder/compiler.py")[0]
            compiler_source["sha256"] = "old-compiler-hash"
            sources = [{"path": "brief.md", "sha256": "same", "lines": 1}]
            manifest = {"sources": sources, "slot": "kaan-brief", "code_commit": "prior-code",
                        "generation_attempts": [], "compilation_attempts": [{"attempt": 1}],
                        "compiler_source": compiler_source}
            (seed / "manifest.json").write_text(json.dumps(manifest))
            candidate = {"policy": {}, "workflow": {}, "checks": [], "uncertainties": [], "summary": "Seed"}
            path = seed / "candidate-attempt-1.json"
            path.write_text(json.dumps(candidate))
            original = path.read_bytes()
            with self.assertRaisesRegex(ValueError, "compiler source does not match"):
                runner.resume_candidate(seed, sources, "kaan-brief")
            metadata, draft = runner.repair_candidate(seed, sources, "kaan-brief")
            self.assertEqual(draft, candidate)
            self.assertEqual(metadata["candidate_sha256"], hashlib.sha256(original).hexdigest())
            self.assertEqual(path.read_bytes(), original)

    def run_compile(self, *, failure=None, changed=None, resume=False):
        with tempfile.TemporaryDirectory() as directory:
            kit = Path(directory).resolve()
            (kit / "docs").mkdir()
            brief, api = kit / "brief.md", kit / "openapi.json"
            brief.write_text("1. Synthetic rule\n")
            api.write_text("{}")
            for name in ("workflow-format.md", "tools-and-code.md", "api.md"):
                (kit / "docs" / name).write_text("Synthetic platform format\n")
            paths = [brief, api, ROOT / "builder/prompt.md",
                     *[kit / "docs" / name for name in ("workflow-format.md", "tools-and-code.md", "api.md")]]
            sources = [runner.source(path)[0] for path in paths]
            old_sources = copy.deepcopy(sources)
            old_sources[2]["sha256"] = "prior-compiler-prompt"
            if type(changed) is int:
                old_sources[changed]["sha256"] = "changed-source"
            elif changed == "order":
                old_sources.reverse()
            seed = kit / "seed"
            seed.mkdir()
            seed_manifest = {"sources": old_sources, "slot": "other-slot" if changed == "slot" else "kaan-brief",
                             "code_commit": "seed-code", "generation_attempts": [{"attempt": 2}]}
            seed_manifest["compiler_source"] = {**runner.source(ROOT / "builder/compiler.py")[0], "sha256": "old-compiler-hash"}
            manifest_path = seed / "manifest.json"
            manifest_path.write_text(json.dumps(seed_manifest))
            candidate = {"policy": {"source_rules": [{"source": sources[0]["path"], "line": 1}]},
                         "workflow": {"nodes": {"guard": {"code": "uncompiled"}}}, "checks": [],
                         "uncertainties": [], "summary": "Seed"}
            seed_path = seed / "candidate-attempt-2.json"
            seed_path.write_text(json.dumps(candidate))
            original_seed, original_manifest = seed_path.read_bytes(), manifest_path.read_bytes()
            compiled = copy.deepcopy(candidate)
            compiled["workflow"]["nodes"]["guard"]["code"] = "source-owned guard"
            if failure == "provenance":
                compiled["policy"]["source_rules"] = []
            deadlines = []

            def invoke(command, deadline, **kwargs):
                deadlines.append(deadline)
                if command[:2] == ["git", "rev-parse"]:
                    return 0, "current-code\n", ""
                if command[:2] == ["git", "status"]:
                    return 0, "", ""
                self.fail("Offline compilation must never call Codex or a live helper: " + str(command))

            def validate(workflow, policy, openapi, checks, **kwargs):
                self.assertEqual(openapi, {})
                self.assertEqual(kwargs["brief_lines"], {sources[0]["path"]: ["1. Synthetic rule"]})
                if workflow == candidate["workflow"]:
                    return {"ok": False, "valid": False, "errors": ["Seed needs source-owned guard"], "checks": []}
                self.assertEqual(workflow, compiled["workflow"])
                self.assertEqual(policy, compiled["policy"])
                self.assertEqual(checks, compiled["checks"])
                valid = failure != "validation"
                return {"ok": valid, "valid": valid, "errors": [] if valid else ["Compiled guard rejected"], "checks": []}

            with patch.object(runner, "KIT", kit), patch.object(runner, "invoke", invoke), \
                    patch("builder.compiler.compile_candidate", **({"side_effect": ValueError("Unsafe shortcut")}
                          if failure == "compiler" else {"return_value": (compiled, ["Guard compiled"])})) as compiler, \
                    patch("builder.validation.validate", side_effect=validate) as validation, \
                    patch("freya.validate_workflow") as dry_run, patch("freya.save_workflow") as save, \
                    patch("freya.update_workflow") as update, patch("freya.api") as remote, \
                    patch("freya.export_workflow") as export, \
                    patch("sys.argv", ["build_agent.py", str(brief), "--openapi", str(api), "--offline",
                                       "--compile-build", str(seed), "--budget-seconds", "60"]):
                self.assertEqual(runner.main(), 2 if failure or changed is not None else 0)
                folder = next((kit / "out").iterdir())
                manifest = json.loads((folder / "manifest.json").read_text())
                trace = [json.loads(line) for line in (folder / "trace.jsonl").read_text().splitlines()]
                self.assertEqual(manifest["generation_attempts"], [])
                self.assertEqual(manifest["live_test"]["status"], "not_run")
                self.assertNotIn("builder_model", manifest)
                self.assertFalse(any(row["event"].startswith("model_") for row in trace))
                self.assertEqual(len(set(deadlines)), 1)
                self.assertEqual(seed_path.read_bytes(), original_seed)
                self.assertEqual(manifest_path.read_bytes(), original_manifest)
                self.assertEqual(manifest["compiler_source"], runner.source(ROOT / "builder/compiler.py")[0])
                if changed is not None:
                    compiler.assert_not_called()
                    validation.assert_not_called()
                    self.assertEqual(manifest["status"], "incomplete")
                else:
                    compiler.assert_called_once_with(candidate)
                    self.assertEqual(manifest["compile_seed"]["candidate_sha256"], hashlib.sha256(original_seed).hexdigest())
                    self.assertEqual(manifest["compilation_attempts"][0]["attempt"], 1)
                    self.assertEqual(manifest["compilation_attempts"][0]["valid"], failure is None)
                    self.assertEqual(manifest["status"], "incomplete" if failure else "completed_local")
                    self.assertEqual(validation.call_count, 1 if failure == "compiler" else 2)
                    report = json.loads((folder / "validation.json").read_text())
                    if failure != "compiler":
                        self.assertEqual(report["provenance"]["ok"], failure != "provenance")
                        self.assertEqual(report["provenance"]["numbered_rules"], 1)
                        saved = json.loads((folder / "candidate-attempt-1.json").read_text())
                        self.assertEqual(saved, compiled)
                        events = [row["event"] for row in trace]
                        self.assertLess(events.index("workflow_compiled"), events.index("local_validation"))
                    if failure:
                        self.assertTrue(report["errors"])
                    if resume:
                        metadata, raw = runner.resume_candidate(folder, sources, "kaan-brief")
                        self.assertEqual(json.loads(raw), compiled)
                        self.assertEqual(metadata["candidate_sha256"], hashlib.sha256((folder / "candidate-attempt-1.json").read_bytes()).hexdigest())
                        compiler.reset_mock()
                        validation.reset_mock()
                        with patch("sys.argv", ["build_agent.py", str(brief), "--openapi", str(api), "--offline",
                                                "--resume-build", str(folder), "--budget-seconds", "60"]):
                            self.assertEqual(runner.main(), 0)
                        compiler.assert_not_called()
                        self.assertEqual(validation.call_count, 1)
                        resumed_folder = next(path for path in (kit / "out").iterdir() if path != folder)
                        resumed = json.loads((resumed_folder / "manifest.json").read_text())
                        self.assertEqual(resumed["generation_attempts"], [])
                        self.assertTrue(resumed["resume_validation"]["valid"])
                for operation in (dry_run, save, update, remote, export):
                    operation.assert_not_called()


if __name__ == "__main__":
    unittest.main()
