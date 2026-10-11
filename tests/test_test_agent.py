import importlib.util
import contextlib
import io
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import Mock, call, patch


ROOT = Path(__file__).resolve().parent.parent
SPEC = importlib.util.spec_from_file_location("test_agent_helper", ROOT / "scripts/test_agent.py")
helper = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(helper)
import freya
import run_cases


class TestHelperChecks(unittest.TestCase):
    def test_shell_wrapper_keeps_documented_paths_relative_to_repository(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "scripts").mkdir()
            wrapper = root / "scripts/test-agent.sh"
            wrapper.write_text((ROOT / "scripts/test-agent.sh").read_text())
            (root / "scripts/test_agent.py").write_text(
                "import sys\nfrom pathlib import Path\nprint(Path(sys.argv[-1]).resolve())\n")
            for flag in ("--resume", "--cases"):
                result = subprocess.run(["bash", str(wrapper), flag, "build-the-builder/results/saved"],
                                        cwd=root, capture_output=True, text=True, check=True)
                self.assertEqual(result.stdout.strip(), str((root / "build-the-builder/results/saved").resolve()))

    def test_get_503_is_bounded_but_writes_and_auth_errors_are_not_retried(self):
        unavailable = RuntimeError("GET /simulation -> 503: API key validation temporarily unavailable")
        api = Mock(side_effect=[unavailable, unavailable, {"status": "completed"}])
        with patch.object(helper.time, "sleep") as sleep:
            self.assertEqual(helper.freya_read_retry(api, "GET", "/simulation", workspaceId="mock"), {"status": "completed"})
            self.assertEqual(api.call_count, 3)
            self.assertEqual(sleep.call_args_list, [call(2), call(4)])
        for method, status in (("POST", 503), ("GET", 401)):
            api = Mock(side_effect=RuntimeError(f"{method} /simulation -> {status}: unavailable"))
            with patch.object(helper.time, "sleep") as sleep, self.assertRaises(RuntimeError):
                helper.freya_read_retry(api, method, "/simulation")
            self.assertEqual(api.call_count, 1)
            sleep.assert_not_called()
        api = Mock(side_effect=unavailable)
        with patch.object(helper.time, "sleep") as sleep, self.assertRaises(RuntimeError):
            helper.freya_read_retry(api, "GET", "/simulation")
        self.assertEqual(api.call_count, 4)
        self.assertEqual(sleep.call_args_list, [call(2), call(4), call(8)])

    def test_transient_get_transport_failure_recovers_with_bounded_backoff_but_post_never_retries(self):
        eof = helper.urllib.error.URLError(helper.ssl.SSLEOFError(8, "[SSL: UNEXPECTED_EOF_WHILE_READING] EOF occurred in violation of protocol"))
        for error in (eof, helper.urllib.error.URLError("UNEXPECTED_EOF_WHILE_READING"),
                      helper.urllib.error.URLError(TimeoutError("timed out")), ConnectionResetError("connection reset by peer")):
            with self.subTest(error_type=type(error).__name__):
                api = Mock(side_effect=[error, error, {"status": "completed"}])
                with patch.object(helper.time, "sleep") as sleep:
                    self.assertEqual(helper.freya_read_retry(api, "GET", "/simulation"), {"status": "completed"})
                self.assertEqual(api.call_count, 3)
                self.assertEqual(sleep.call_args_list, [call(2), call(4)])
                api = Mock(side_effect=error)
                with patch.object(helper.time, "sleep") as sleep, self.assertRaises(type(error)):
                    helper.freya_read_retry(api, "POST", "/simulation", {"agentId": "mock"})
                self.assertEqual(api.call_count, 1)
                sleep.assert_not_called()
        api = Mock(side_effect=eof)
        with patch.object(helper.time, "sleep") as sleep, self.assertRaises(helper.urllib.error.URLError):
            helper.freya_read_retry(api, "GET", "/simulation")
        self.assertEqual(api.call_count, 4)
        self.assertEqual(sleep.call_args_list, [call(2), call(4), call(8)])

    def test_permanent_get_errors_and_malformed_responses_are_not_retried(self):
        for error in (helper.urllib.error.URLError(helper.ssl.SSLCertVerificationError(1, "certificate verify failed")),
                      helper.urllib.error.URLError("hostname resolution failed"),
                      helper.urllib.error.HTTPError("https://example.invalid", 401, "Unauthorized", {}, None),
                      json.JSONDecodeError("invalid JSON", "not JSON", 0)):
            with self.subTest(error_type=type(error).__name__):
                api = Mock(side_effect=error)
                with patch.object(helper.time, "sleep") as sleep, self.assertRaises(type(error)):
                    helper.freya_read_retry(api, "GET", "/simulation")
                self.assertEqual(api.call_count, 1)
                sleep.assert_not_called()
                if isinstance(error, helper.urllib.error.HTTPError):
                    error.close()

    def make_evidence(self, folder, api=None, bank=None, report=None, resume=False):
        (folder / "calls").mkdir(exist_ok=True)
        report = report or {"agent_id": "agent-1", "simulations": [], "reported_agent_versions": [], "transcript_errors": []}
        return helper.RunEvidence(folder, report, freya, api or self.api, bank or self.bank, resume)

    @staticmethod
    def case():
        return next(case for case in json.loads((ROOT / "build-the-builder/public-test-set.json").read_text()) if case["id"] == "PUB-01")

    def bank(self, path, body=None):
        if body:
            return {"variables": {"customer_id": "customer-1"}}
        expected = self.case()["expected"]
        return {**expected, "calls": [{"tool": "close_call", "result": {}}]}

    @staticmethod
    def api(method, path, body=None, **params):
        if path in ("/api/v2/simulations", "/api/v2/simulations/sim-1"):
            return {"simulation": {"id": "sim-1", "agentId": "agent-1", "status": "completed", "agentVersionNumber": 7},
                    "dashboard": {"agentVersionNumber": 99}}
        if path.endswith("/iterations"):
            return {"iterations": [{"id": "it-1"}]}
        if path.endswith("/iterations/it-1"):
            return {"iteration": {"id": "it-1", "simulationId": "sim-1"}, "runs": [
                {"id": "run-1", "personaId": "persona-1", "callId": "call-1", "agentId": "agent-1", "agentVersionNumber": 7, "outcome": "pass"},
                {"id": "other-run", "personaId": "other-persona", "callId": "other-call", "agentId": "other-agent", "agentVersionNumber": 99}]}
        if path == "/api/v2/call/call-1":
            return {"call": {"id": "call-1", "entityId": "agent-1", "entityType": "agent", "entityVersionNumber": 7, "messages": []}}
        raise AssertionError((method, path))

    def run_official(self, evidence):
        with patch.object(freya, "api", evidence.api), patch.object(run_cases, "http", evidence.bank), patch.object(helper.time, "sleep"):
            return evidence.run_once(run_cases.run_once, "agent-1", [self.case()], {"PUB-01": "persona-1"})

    def test_sessions_and_simulation_are_saved_before_polling_fails(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)

            def api(method, path, body=None, **params):
                if method == "GET":
                    saved = json.loads((folder / "summary.json").read_text())["simulations"][0]
                    self.assertEqual(saved["simulation_id"], "sim-1")
                    self.assertEqual(saved["sessions"]["PUB-01"]["customer_id"], "customer-1")
                    raise RuntimeError(f"GET {path} -> 503: unavailable")
                return self.api(method, path, body, **params)

            api_mock = Mock(side_effect=api)
            evidence = self.make_evidence(folder, api=api_mock)
            with self.assertRaises(RuntimeError):
                self.run_official(evidence)
            run = evidence.report["simulations"][0]
            self.assertEqual(run["simulation_id"], "sim-1")
            self.assertIsNone(run["iteration_id"])
            self.assertEqual(run["scoring_status"], "incomplete")
            self.assertEqual(sum(item.args[0] == "POST" for item in api_mock.call_args_list), 1)
            self.assertNotIn("passed", evidence.report)

    def test_completed_execution_survives_ledger_failure_and_resumes_without_post(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)

            def bank(path, body=None):
                if body is None:
                    raise helper.BankUnavailable({"path": path, "http_status": 503})
                return self.bank(path, body)

            evidence = self.make_evidence(folder, bank=bank)
            with self.assertRaises(helper.BankUnavailable):
                self.run_official(evidence)
            run = evidence.report["simulations"][0]
            self.assertEqual((run["simulation_id"], run["iteration_id"]), ("sim-1", "it-1"))
            self.assertEqual(run["execution_status"], "completed")
            self.assertEqual((run["results_status"], run["scoring_status"]), ("failed", "incomplete"))
            self.assertEqual(run["call_ids"], ["call-1"])
            self.assertEqual(run["rows"], [])
            self.assertEqual(run["reported_agent_versions"], [7])
            self.assertTrue((folder / "calls/call-1.json").exists())
            saved = json.loads((folder / "summary.json").read_text())
            api, bank = Mock(side_effect=self.api), Mock(side_effect=self.bank)
            resumed = self.make_evidence(folder, api=api, bank=bank, report=saved, resume=True)
            with patch.object(freya, "run_simulation", resumed.resume_simulation):
                result = self.run_official(resumed)
            self.assertTrue(result[0][0]["pass"], "the unchanged official scorer must still accept the happy path")
            self.assertEqual(resumed.report["simulations"][0]["scoring_status"], "complete")
            self.assertTrue(all(item.args[0] == "GET" for item in api.call_args_list))
            self.assertTrue(all(item.args[1] is None for item in bank.call_args_list))

    def test_successful_metadata_version_is_not_lost_when_iteration_read_fails(self):
        with tempfile.TemporaryDirectory() as directory:
            def api(method, path, body=None, **params):
                if path.endswith("/iterations/it-1"):
                    raise RuntimeError(f"GET {path} -> 503: unavailable")
                return self.api(method, path, body, **params)

            evidence = self.make_evidence(Path(directory), api=api)
            with self.assertRaises(RuntimeError):
                self.run_official(evidence)
            self.assertEqual(evidence.report["reported_agent_versions"], [7])
            run = evidence.report["simulations"][0]
            self.assertEqual(run["iteration_id"], "it-1")
            self.assertEqual(run["execution_status"], "completed")
            self.assertTrue(any(item["source"] == "/api/v2/simulations/sim-1" for item in run["version_evidence"]))

    def test_call_entity_version_requires_owned_call_and_agent(self):
        with tempfile.TemporaryDirectory() as directory:
            evidence = self.make_evidence(Path(directory))
            self.run_official(evidence)
            run = evidence.report["simulations"][0]
            self.assertTrue(any(item["field"] == "entityVersionNumber" for item in run["version_evidence"]))
            for changed in ({"id": "other-call"}, {"entityId": "other-agent"}, {"assistantId": "other-agent"}, {"entityType": "persona"}):
                evidence.original_api = lambda *args, **kwargs: {"call": {"id": "call-1", "entityId": "agent-1", "entityVersionNumber": 99, **changed}}
                with self.assertRaises(RuntimeError):
                    evidence.api("GET", "/api/v2/call/call-1")
            self.assertEqual(run["reported_agent_versions"], [7])

    def test_real_workflow_call_shape_binds_entity_version_to_assistant_id(self):
        with tempfile.TemporaryDirectory() as directory:
            def api(method, path, body=None, **params):
                if path == "/api/v2/call/call-1":
                    return {"call": {"id": "call-1", "assistantId": "agent-1", "assistantEntityType": "workflow",
                                     "assistantWorkflowId": "workflow-1", "entityVersionNumber": 7, "messages": []}}
                return self.api(method, path, body, **params)

            evidence = self.make_evidence(Path(directory), api=api)
            self.run_official(evidence)
            run = evidence.report["simulations"][0]
            self.assertEqual(evidence.report["transcript_errors"], [])
            self.assertTrue(any(item["field"] == "entityVersionNumber" for item in run["version_evidence"]))
            self.assertEqual(run["reported_agent_versions"], [7])

    def test_selected_persona_ownership_conflicts_never_reach_the_official_scorer(self):
        for mismatch in ({"agentId": "other-agent"}, {"simulationId": "other-simulation"}, {"iterationId": "other-iteration"}):
            with self.subTest(mismatch=mismatch), tempfile.TemporaryDirectory() as directory:
                def api(method, path, body=None, **params):
                    result = self.api(method, path, body, **params)
                    if path.endswith("/iterations/it-1"):
                        result["runs"][0].update(mismatch)
                    return result

                bank = Mock(side_effect=self.bank)
                evidence = self.make_evidence(Path(directory), api=api, bank=bank)
                with patch.object(run_cases, "score_ledger") as scorer, self.assertRaisesRegex(RuntimeError, "Selected persona"):
                    self.run_official(evidence)
                scorer.assert_not_called()
                self.assertFalse(any(item.args[0].startswith("/v1/practice/ledger/") for item in bank.call_args_list))
                self.assertEqual(evidence.report["simulations"][0]["scoring_status"], "incomplete")

    def test_diagnostics_expose_schema_rejection_and_extraction_router_failures(self):
        events = [
            {"event": "function_call_complete", "function": "code_exec", "result": {"status": "success", "validation_errors": ["variable 'speech_date' rejected by schema validation"]}},
            {"event": "extraction_complete", "accepted": False, "error": "invalid enum"},
            {"event": "route_evaluated", "matched": False},
            {"event": "node_enter", "reason": "conversation fallback"}]
        messages = [{"role": "system", "messageId": str(index), "nodeId": "talk", "message": json.dumps(event)} for index, event in enumerate(events)]
        messages.append({"role": "user", "message": json.dumps(events[0])})
        self.assertEqual([item["kind"] for item in helper.call_diagnostics({"messages": messages})],
                         ["state_write_rejected", "extraction_failure", "router_unmatched", "router_fallback"])

    def test_diagnostic_redaction_happens_before_excerpt_truncation(self):
        secret = "synthetic-private-secret-with-a-long-tail"
        event = {"event": "extraction_failed", "reason": secret}
        event["reason"] = "x" * (1990 - json.dumps(event).index(secret)) + secret
        text = json.dumps(event)
        prefix_length = 2000 - text.index(secret)
        self.assertGreater(prefix_length, 0)
        self.assertLess(prefix_length, len(secret))
        with patch.dict(os.environ, {"FREYA_BANK_TEAM_KEY": secret}):
            diagnostic = helper.call_diagnostics({"messages": [{"role": "system", "message": text}]})[0]
        self.assertNotIn(secret[:prefix_length], diagnostic["event"])
        self.assertIn("[REDACTED]", diagnostic["event"])

    def test_real_event_shape_ignores_stale_failures_in_variable_snapshots(self):
        validation = ["variable 'speech_date' rejected by schema validation", "variable 'confirm_date' rejected by schema validation"]
        events = [
            {"event": "function_call_complete", "function": "code_exec", "result": {"status": "success", "validation_errors": validation}},
            {"event": "variable_extracted", "name": "speech_event", "value": "refuse", "confidence": 1.0,
             "variable_table": {"last_error": {"validation_errors": validation, "reason": "invalid extraction failed"}}},
            {"event": "extraction_failed", "name": "speech_event", "reason": "low_confidence", "confidence": 0.679},
            {"event": "function_call_complete", "function": "code_exec", "result": {"status": "success", "validation_errors": validation}},
            {"event": "route_evaluated", "matched": False, "reason": "No transition matched",
             "variable_table": {"last_error": {"validation_errors": validation}}}]
        messages = [{"role": "system", "message": json.dumps(event)} for event in events]
        diagnostics = helper.call_diagnostics({"messages": messages})
        self.assertEqual([item["kind"] for item in diagnostics],
                         ["state_write_rejected", "extraction_failure", "state_write_rejected", "router_unmatched"])
        self.assertTrue(all("variable_table" not in item["event"] for item in diagnostics))

    def test_semantic_fallback_reports_only_direct_current_route_status_without_private_speech(self):
        private_speech = "Synthetic private identity answer"
        secret = "synthetic-private-key"
        events = [
            {"event": "route_evaluated", "matched": True,
             "variable_table": {"decision_status": "fallback:incomplete_identity_answer", "speech_text": private_speech}},
            {"event": "route_evaluated", "matched": True,
             "variable_table": {"decision_status": "fallback:incomplete_identity_answer:" + secret, "speech_text": private_speech}},
            {"event": "route_evaluated", "matched": True, "variable_table": {"decision_status": "processed",
             "snapshot": {"decision_status": "fallback:stale"}}},
            {"event": "route_evaluated", "matched": True, "variable_table": {"decision_status": {"value": "fallback:stale"}}},
            {"event": "variable_extracted", "value": "fallback:stale", "variable_table": {"decision_status": "fallback:stale"}},
            {"event": "node_enter", "workflowSnapshot": {"variable_table": {"decision_status": "fallback:stale"}}}]
        messages = [{"role": "system", "messageId": str(index), "message": json.dumps(event)} for index, event in enumerate(events)]
        messages.append({"role": "user", "message": json.dumps(events[0])})
        with patch.dict(os.environ, {"FREYA_BANK_TEAM_KEY": secret}):
            diagnostics = helper.call_diagnostics({"messages": messages})
        self.assertEqual([item["kind"] for item in diagnostics], ["decision_fallback", "decision_fallback"])
        self.assertEqual([item["message_id"] for item in diagnostics], ["0", "1"])
        self.assertEqual(json.loads(diagnostics[0]["event"])["decision_status"], "fallback:incomplete_identity_answer")
        self.assertIn("[REDACTED]", diagnostics[1]["event"])
        self.assertNotIn(secret, json.dumps(diagnostics))
        self.assertNotIn(private_speech, json.dumps(diagnostics))
        self.assertNotIn("variable_table", json.dumps(diagnostics))

    def test_unknown_create_is_saved_and_cannot_be_resumed(self):
        with tempfile.TemporaryDirectory() as directory:
            evidence = self.make_evidence(Path(directory), api=Mock(side_effect=RuntimeError("POST /api/v2/simulations -> 503: unavailable")))
            with self.assertRaises(RuntimeError):
                self.run_official(evidence)
            run = evidence.report["simulations"][0]
            self.assertEqual(run["execution_status"], "creation_unknown")
            self.assertIsNone(run["simulation_id"])
            self.assertEqual(run["sessions"]["PUB-01"]["customer_id"], "customer-1")
            resumed = self.make_evidence(Path(directory), report=evidence.report, resume=True)
            resumed.current = run
            with self.assertRaisesRegex(RuntimeError, "ambiguous POST"):
                resumed.resume_simulation("agent-1", "ignored", {})

    def test_failed_execution_has_no_complete_score(self):
        with tempfile.TemporaryDirectory() as directory:
            def api(method, path, body=None, **params):
                result = self.api(method, path, body, **params)
                if "simulation" in result:
                    result["simulation"]["status"] = "failed"
                return result

            evidence = self.make_evidence(Path(directory), api=api)
            with self.assertRaises(helper.SimulationIncomplete):
                self.run_official(evidence)
            self.assertEqual(evidence.report["simulations"][0]["execution_status"], "failed")
            self.assertEqual(evidence.report["simulations"][0]["scoring_status"], "incomplete")

    def test_cli_resume_rebuilds_persona_cache_locally_and_recovers_the_official_score(self):
        with tempfile.TemporaryDirectory() as directory:
            kit = Path(directory)
            cases_path = kit / "input-cases.json"
            cases_path.write_text(json.dumps([self.case()]))
            unavailable = True

            def bank(path, body=None):
                if body is None and unavailable:
                    raise helper.BankUnavailable({"path": path, "http_status": 503})
                return self.bank(path, body)

            api = Mock(side_effect=self.api)
            with patch.object(helper, "KIT", kit), patch.object(run_cases, "ROOT", kit), \
                    patch.object(freya, "api", api), patch.object(helper, "bank_http", bank), \
                    patch.object(freya, "create_personas", return_value={"personas": [{"id": "persona-1"}]}), \
                    patch.object(helper.time, "sleep"), \
                    patch.dict(os.environ, {"FREYA_API_KEY": "mock-freya-key", "FREYA_BANK_TEAM_KEY": "mock-private-bank-key", "FREYA_BUILDER_LOCK_OWNER": "invalid"}), \
                    contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                with patch.object(helper.sys, "argv", ["test_agent.py", "agent-1", "--cases", str(cases_path)]):
                    self.assertEqual(helper.main(), 2)
                folder = next((kit / "results").iterdir())
                report = json.loads((folder / "summary.json").read_text())
                self.assertEqual(report["status"], "blocked_by_bank")
                self.assertEqual(report["simulations"][0]["execution_status"], "completed")
                (kit / ".personas.json").unlink()
                unavailable = False
                api.reset_mock()
                with patch.object(helper.sys, "argv", ["test_agent.py", "--resume", str(folder)]):
                    self.assertEqual(helper.main(), 0)
                report = json.loads((folder / "summary.json").read_text())
                self.assertEqual((report["status"], report["passed"], report["total"]), ("completed", 1, 1))
                self.assertEqual(report["reported_agent_versions"], [7])
                self.assertTrue(all(item.args[0] == "GET" for item in api.call_args_list))

    def test_standalone_test_uses_builder_lock(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(helper, "KIT", Path(directory)), \
                patch.dict(os.environ, {"FREYA_BUILDER_LOCK_OWNER": "invalid"}):
            lock = helper.acquire_test_lock()
            try:
                with self.assertRaises(RuntimeError):
                    helper.acquire_test_lock()
            finally:
                lock.close()
            helper.acquire_test_lock().close()
        with patch.dict(os.environ, {"FREYA_BUILDER_LOCK_OWNER": str(os.getppid())}):
            self.assertIsNone(helper.acquire_test_lock())


if __name__ == "__main__":
    unittest.main()
