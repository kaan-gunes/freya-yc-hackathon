import importlib.util
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, call, patch


ROOT = Path(__file__).resolve().parent.parent
SPEC = importlib.util.spec_from_file_location("test_agent_helper", ROOT / "scripts/test_agent.py")
helper = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(helper)


class TestHelperChecks(unittest.TestCase):
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

    def test_incomplete_simulation_keeps_completed_evidence_without_a_score(self):
        simulations = []
        rows = [{"id": "case", "call_id": "call-1", "pass": True}]
        completed = helper.record_simulation((rows, "sim-1", "it-1", "completed", 12, 1), simulations)
        self.assertEqual(completed["rows"], rows)
        for status in ("failed", "paused"):
            with self.assertRaises(helper.SimulationIncomplete):
                helper.record_simulation((rows, "sim-2", "it-2", status, 3, 1), simulations)
            self.assertEqual(simulations[-1]["status"], status)
            self.assertEqual(simulations[-1]["rows"], rows)
        self.assertEqual(len(simulations), 3)
        self.assertEqual(helper.version_numbers({"runs": [{"agentVersionNumber": 7}]}), [7])

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
