import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("final_build_runner", ROOT / "scripts/build_agent.py")
runner = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(runner)
import freya


def api_tool(url, name="source_action"):
    return {"function": {"name": name, "handler": "__function__:api_call",
                         "parameters": {"properties": {"url": {"default": url}, "method": {"default": "POST"}}}}}


class FinalRunnerChecks(unittest.TestCase):
    def test_folder_discovers_unique_schema_and_keeps_explicit_file_precedence(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory).resolve()
            api = folder / "contract.json"
            api.write_text(json.dumps({"openapi": "3.0.3", "paths": {}}))
            a, b = folder / "A.md", folder / "B.md"
            a.write_text("Earlier rule")
            b.write_text("Later rule")
            (folder / "customers.json").write_text('{"customers": []}')
            docs, schema = runner.case_inputs([folder])
            self.assertEqual(schema, api)
            self.assertEqual(docs, [a, b, folder / "customers.json"])
            self.assertEqual(runner.case_inputs([b, a], api)[0], [b, a])
            (folder / "second.json").write_text(api.read_text())
            with self.assertRaisesRegex(ValueError, "found 2"):
                runner.case_inputs([folder])
            self.assertEqual(runner.case_inputs([folder], api)[1], api)

    def test_missing_schema_remains_explicit_for_source_contract_extraction(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory).resolve()
            (folder / "service.md").write_text("Call the bank to record a promise.")
            self.assertEqual(runner.case_inputs([folder]), ([folder / "service.md"], None))

    def test_mock_url_has_no_credentials_or_template_and_keeps_api_prefix(self):
        self.assertEqual(runner.mock_base_url("https://team.workers.dev/v2/"), "https://team.workers.dev/v2")
        for value in ("relative", "ftp://example.com", "https://user:pass@example.com", "https://example.com?key=secret",
                      "https://example.com#secret", "https://{{host}}", "https://example.com:invalid", "https://example.com/\n"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                runner.mock_base_url(value)

    def test_mock_binding_covers_all_actions_and_preserves_paths_queries_and_fixtures(self):
        original = "https://source.example/v1"
        target = "https://team.workers.dev/custom"
        candidate = {"workflow": {
            "nodes": {"action": {"pre_actions": [api_tool(original + "/lookup?mode=latest")]},
                      "listener": {"tools": [api_tool("/write", "source_write")]}},
            "global_nodes": {"global": {"pre_actions": [api_tool(original + "/global", "source_global")]}},
            "tools": [api_tool(original + "/close", "source_close")]},
            "policy": {"api_bindings": {"server": original, "lookup": {"url": original + "/lookup"}},
                       "source_rules": [{"text": original + "/source-quote"}]},
            "checks": [{"request_url": original + "/write", "body": {"customer_id": "synthetic"}}]}
        before = copy.deepcopy(candidate)
        schema = {"servers": [{"url": original}], "paths": {"/write": {"post": {}}}}
        bound, effective, changes = runner.bind_mock(candidate, schema, target)
        self.assertEqual(candidate, before)
        self.assertEqual(schema["servers"][0]["url"], original)
        self.assertEqual(effective["servers"][0]["url"], target)
        self.assertEqual({row["url"] for row in changes}, {target + "/lookup?mode=latest", target + "/write", target + "/global", target + "/close"})
        self.assertEqual(bound["checks"][0]["request_url"], target + "/write")
        self.assertEqual(bound["policy"]["api_bindings"]["server"], target)
        self.assertEqual(bound["policy"]["source_rules"], before["policy"]["source_rules"])
        self.assertEqual(runner.bind_mock(bound, schema, target)[0], bound)
        same_host = "https://source.example"
        rebound, _, _ = runner.bind_mock(candidate, schema, same_host)
        self.assertEqual(rebound["workflow"]["tools"][0]["function"]["parameters"]["properties"]["url"]["default"], same_host + "/close")
        self.assertEqual(runner.workflow_counts(bound["workflow"]), {"node_count": 3, "tool_count": 4, "api_tool_count": 4})
        bound["workflow"]["tools"][0]["function"]["parameters"]["properties"]["url"]["default"] = "https://other.example/close"
        with self.assertRaisesRegex(ValueError, "outside the supplied service"):
            runner.bind_mock(bound, schema, target)

    def test_strict_resume_rejects_changed_mock_url_and_language_dependency(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory).resolve()
            candidate = {"workflow": {}}
            (folder / "candidate-attempt-1.json").write_text(json.dumps(candidate))
            manifest = {"sources": [], "slot": "final", "code_commit": "synthetic", "generation_attempts": [{"attempt": 1}],
                        "mock_url": "https://team.workers.dev", "language_source": {"path": "builder/language.py", "sha256": "old", "lines": 1}}
            (folder / "manifest.json").write_text(json.dumps(manifest))
            with patch.object(runner, "source", return_value=({"path": "builder/language.py", "sha256": "old", "lines": 1}, "")):
                self.assertEqual(runner.resume_candidate(folder, [], "final", mock_url="https://team.workers.dev")[1], json.dumps(candidate))
                with self.assertRaisesRegex(ValueError, "mock URL"):
                    runner.resume_candidate(folder, [], "final", mock_url="https://other.workers.dev")
            with patch.object(runner, "source", return_value=({"path": "builder/language.py", "sha256": "changed", "lines": 1}, "")):
                with self.assertRaisesRegex(ValueError, "language source"):
                    runner.resume_candidate(folder, [], "final", mock_url="https://team.workers.dev")
            manifest.pop("language_source")
            manifest["input_reader_source"] = {"path": "builder/inputs.py", "sha256": "old", "lines": 1}
            (folder / "manifest.json").write_text(json.dumps(manifest))
            with patch.object(runner, "source", return_value=({"path": "builder/inputs.py", "sha256": "changed", "lines": 1}, "")):
                with self.assertRaisesRegex(ValueError, "input reader source"):
                    runner.resume_candidate(folder, [], "final", mock_url="https://team.workers.dev")
            manifest.pop("input_reader_source")
            manifest["candidate_sha256"] = hashlib.sha256((folder / "candidate-attempt-1.json").read_bytes()).hexdigest()
            (folder / "manifest.json").write_text(json.dumps(manifest))
            self.assertTrue(runner.resume_candidate(folder, [], "final", mock_url="https://team.workers.dev")[0]["generation_hash_verified"])
            (folder / "candidate-attempt-1.json").write_text('{"workflow":{"edited":true}}')
            with self.assertRaisesRegex(ValueError, "original generation hash"):
                runner.resume_candidate(folder, [], "final", mock_url="https://team.workers.dev")

    def test_final_online_export_and_trace_skip_practice_without_bank_test_credentials(self):
        self.run_final()

    def test_prose_contract_is_extracted_with_evidence_before_workflow_generation(self):
        self.run_final(prose=True)

    def test_final_keeps_validation_readback_and_published_version_gates(self):
        for failure in ("local", "dry-run", "readback", "version"):
            with self.subTest(failure=failure):
                self.run_final(failure)

    def test_final_refuses_overwriting_delivery(self):
        self.run_final("delivery")

    def run_final(self, failure=None, prose=False):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            kit, case, delivery = root / "kit", root / "case", root / "selected"
            (kit / "docs").mkdir(parents=True)
            case.mkdir()
            brief, api = case / "brief.md", case / "contract.json"
            brief.write_text("1. Synthetic bank rule\n")
            contract = {"openapi": "3.0.3", "servers": [{"url": "https://source.example/v1"}], "paths": {"/source_action": {"post": {"operationId": "source_action"}}}}
            api.write_text(json.dumps(contract))
            for name in ("workflow-format.md", "tools-and-code.md", "api.md"):
                (kit / "docs" / name).write_text("Synthetic format\n")
            candidate = {"policy": {"source_rules": [{"source": str(brief), "line": 1}], "api_bindings": {"server": contract["servers"][0]["url"]}},
                         "workflow": {"nodes": {"action": {"pre_actions": [api_tool("https://source.example/v1/source_action")]}}},
                         "checks": [], "uncertainties": [], "summary": "Synthetic final candidate."}
            target = "https://team.workers.dev/custom"
            if prose:
                api.unlink()
                brief.write_text("POST /source_action is the complete synthetic API contract\n")
                candidate["policy"].update(workflow_kind="service", source_rules=[{
                    "source": str(brief), "line": 1, "text": brief.read_text().strip()}])
                candidate["workflow"]["nodes"]["action"]["pre_actions"] = [api_tool(target + "/source_action")]
            expected, _, _ = runner.bind_mock(candidate, contract, target)
            generated = []

            def invoke(command, deadline, **kwargs):
                if command[:2] == ["git", "rev-parse"]:
                    return 0, "synthetic-commit\n", ""
                if command[:2] == ["git", "status"]:
                    return 0, "", ""
                self.assertEqual(command[0], "codex", "final must never invoke the practice helper")
                self.assertNotIn("FREYA_API_KEY", kwargs["env"])
                generated.append(kwargs["input_text"])
                if prose and len(generated) == 1:
                    extracted = copy.deepcopy(contract)
                    extracted["servers"] = [{"url": target}]
                    extracted["paths"]["/source_action"]["post"]["responses"] = {"200": {"description": "Synthetic response"}}
                    output = {"openapi": extracted, "evidence": [{"operationId": "source_action", "source": str(brief),
                        "line": 1, "text": brief.read_text().strip()}], "uncertainties": []}
                else:
                    output = candidate if len(generated) == (2 if prose else 1) else {}
                Path(command[command.index("-o") + 1]).write_text(json.dumps(output))
                return 0, '{"type":"item.completed","item":{"type":"agent_message","text":"Visible session message"}}\n{"type":"turn.completed"}\n', ""

            def save(slot, workflow, **kwargs):
                self.assertEqual(workflow, expected["workflow"])
                return {"agent_id": "final-agent", "workflow_id": "final-workflow", "version": 2}

            saved = {**expected["workflow"], "agent_config": {"llmConfig": freya.AGENT_LLM}}
            def remote(method, path, **kwargs):
                self.assertEqual(method, "GET")
                if path == "/api/v2/workflow/final-workflow":
                    return {"workflow": {"workflow": {**saved, "nodes": {}} if failure == "readback" else saved}}
                self.assertEqual(path, "/api/v2/versions/workflow/final-workflow")
                return {"versions": [{"versionNumber": 2, "id": "final-version", "isPublished": failure != "version"}]}

            def export(workflow_id, path):
                self.assertEqual(workflow_id, "final-workflow")
                Path(path).write_text(json.dumps({"workflow": saved}))

            if failure == "delivery":
                delivery.mkdir()
                (delivery / "manifest.json").write_text("Do not overwrite")
            local = {"valid": failure != "local", "errors": ["Synthetic failure"] if failure == "local" else [], "checks": []}
            with patch.object(runner, "KIT", kit), patch.object(runner, "invoke", side_effect=invoke), \
                 patch("builder.compiler.compile_candidate", side_effect=lambda value, schema=None: (value, [])), \
                 patch("builder.validation.validate", return_value=local) as validate, \
                 patch("freya.validate_workflow", return_value={"ok": failure != "dry-run"}) as dry_run, \
                 patch("freya.save_workflow", side_effect=save) as publish, patch("freya.api", side_effect=remote), \
                 patch("freya.workspace_id", return_value="synthetic-workspace"), \
                 patch("freya.export_workflow", side_effect=export) as exported, \
                 patch.dict(os.environ, {"FREYA_API_KEY": "synthetic_api_key"}, clear=True), \
                 patch("sys.argv", ["build_agent.py", str(case), "--mock-url", target, "--submission-dir", str(delivery), "--budget-seconds", "60"]):
                self.assertEqual(runner.main(), 2 if failure else 0)
            folder = next((kit / "out").iterdir())
            manifest = json.loads((folder / "manifest.json").read_text())
            self.assertEqual(manifest["live_test"], {"status": "not_run", "reason": "final_case"})
            self.assertEqual(manifest["mock_url"], target)
            if failure:
                self.assertEqual(manifest["status"], "incomplete")
                exported.assert_not_called()
                self.assertEqual(publish.call_count, int(failure in ("readback", "version")))
                if failure in ("local", "delivery"):
                    dry_run.assert_not_called()
                self.assertFalse((delivery / "export.workflow.json").exists())
                if failure == "delivery":
                    self.assertEqual((delivery / "manifest.json").read_text(), "Do not overwrite")
                return
            self.assertEqual(manifest["status"], "completed")
            self.assertEqual(manifest["node_count"], 1)
            self.assertEqual(manifest["api_tool_count"], 1)
            self.assertEqual(manifest["published_version_id"], "final-version")
            self.assertTrue(manifest["ended_at"])
            self.assertEqual(validate.call_args.args[2]["servers"], [{"url": target}])
            if prose:
                self.assertEqual(len(generated), 2)
                self.assertIn("inferred_schema_sha256", manifest)
                self.assertTrue((folder / "contract-evidence.json").exists())
            else:
                self.assertEqual(manifest["sources"][1], runner.source(api)[0], "raw schema hash must remain unchanged")
            self.assertEqual(json.loads((folder / "bound.openapi.json").read_text())["servers"], [{"url": target}])
            self.assertIn("RUNTIME SERVICE BINDING", generated[-1])
            self.assertIn("this listing is not rule priority", generated[-1])
            for name in ("export.workflow.json", "trace.jsonl", "manifest.json"):
                self.assertEqual((delivery / name).read_bytes(), (folder / name).read_bytes())
                self.assertNotIn("synthetic_api_key", (delivery / name).read_text())
            events = [json.loads(line) for line in (delivery / "trace.jsonl").read_text().splitlines()]
            self.assertEqual(events[-1]["event"], "end")
            self.assertEqual(events[-1]["workflow_id"], "final-workflow")
            self.assertEqual(events[-1]["live_test"]["status"], "not_run")
            self.assertIn("test_skipped", [event["event"] for event in events])
            self.assertNotIn("test_begin", [event["event"] for event in events])
            self.assertTrue(next(event for event in events if event["event"] == "model_begin")["purpose"])
            self.assertTrue(any(event.get("event") == "agent_session" and event["item"].get("item", {}).get("text") == "Visible session message" for event in events))
            self.assertEqual(dry_run.call_count, 1)
            self.assertEqual(publish.call_count, 1)


if __name__ == "__main__":
    unittest.main()
