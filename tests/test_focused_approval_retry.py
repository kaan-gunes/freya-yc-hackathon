"""Independent approval and real record-graph checks; no bank or model calls."""

import unittest

from builder.validation import _run_check, validate
from tests.test_builder_validation import candidate


def snippet(arguments, node):
    return arguments[0]["nodes"][node]["pre_actions"][0]["function"]["parameters"]["properties"]["code"]


class FocusedApprovalRetryTests(unittest.TestCase):
    def assert_failed_probe(self, arguments, name):
        report = validate(*arguments)
        probe = next(check for check in report["checks"] if check["name"] == name)
        self.assertFalse(probe["ok"], report)
        self.assertFalse(report["ok"], report)

    def test_plain_yes_and_marker_independent_corrections(self):
        arguments = candidate()
        report = validate(*arguments)
        names = ["independent_valid_record_and_duplicate"] + [
            f"independent_approval_{field}_{marker}_correction_marker"
            for field in ("amount", "date") for marker in ("missing", "wrong")
        ]
        for name in names:
            with self.subTest(probe=name):
                self.assertTrue(next(check["ok"] for check in report["checks"] if check["name"] == name), report)
        for field in ("amount", "date"):
            broken = candidate()
            code = snippet(broken, "approval")
            code["default"] = code["default"].replace("or changed_" + field, "or False")
            for marker in ("missing", "wrong"):
                with self.subTest(field=field, marker=marker):
                    self.assert_failed_probe(broken, f"independent_approval_{field}_{marker}_correction_marker")

    def test_changed_values_are_reread_and_only_new_yes_authorizes_them(self):
        arguments = candidate()
        code = lambda node: snippet(arguments, node)["default"]
        for field, value in (("amount", "30"), ("date", "2026-10-15")):
            for marker in ("", "no"):
                with self.subTest(field=field, marker=marker):
                    state = _run_check(code("offer"), {"vars": arguments[1]["security"]["validation_fixture"], "expected": {}})["vars"]
                    state.update(approval="yes", correction=marker, approval_text="Yes, use the new value.")
                    state["approval_" + field] = value
                    state = _run_check(code("approval"), {"vars": state, "expected": {"route": "offer", "record_authorization": "", "readback_fingerprint": ""}})["vars"]
                    state = _run_check(code("offer"), {"vars": state, "expected": {"route": "confirmation", "record_authorization": "", "validated_" + field: float(value) if field == "amount" else value}})["vars"]
                    state.update(approval="yes", approval_text="Yes, I confirm.")
                    _run_check(code("approval"), {"vars": state, "expected": {"route": "record", "record_authorization": "authorized", "write_attempts": 1}})

    def test_skipped_error_hook_reaches_one_real_retry_and_success(self):
        report = validate(*candidate())
        for name in ("independent_api_error_500_skipped_hook_retry", "independent_api_error_500_skipped_hook_then_success", "independent_failed_record_retry_limit", "independent_failed_record_then_success", "independent_unknown_record_no_retry", "independent_stale_record_status_no_retry", "independent_missing_record_status_no_retry", "independent_missing_record_body_no_retry", "independent_api_error_504_without_no_write_guarantee"):
            with self.subTest(probe=name):
                self.assertTrue(next(check["ok"] for check in report["checks"] if check["name"] == name), report)
        arguments = candidate()
        code = snippet(arguments, "record_result")
        code["default"] = code["default"].replace("status_code == '500'", "status_code == '501'")
        self.assert_failed_probe(arguments, "independent_api_error_500_skipped_hook_retry")

    def test_business_failure_retry_preserves_every_approved_request_field(self):
        for field, value in (("product", "other-product"), ("amount", 999), ("date", "2026-10-15")):
            with self.subTest(field=field):
                arguments = candidate()
                code = snippet(arguments, "record_result")
                code["default"] += f"if status == 'success' and ok == 'false':\n    vars['validated_{field}'] = {value!r}\n"
                report = validate(*arguments)
                self.assertFalse(report["ok"], report)
                for name in ("independent_failed_record_retry_limit", "independent_failed_record_then_success"):
                    probe = next(check for check in report["checks"] if check["name"] == name)
                    self.assertFalse(probe["ok"], report)
                    self.assertIn("immutable approved bank request", probe["error"])
                self.assertTrue(next(check["ok"] for check in report["checks"] if check["name"] == "independent_api_error_500_skipped_hook_retry"))

    def test_old_hook_only_graph_is_rejected(self):
        arguments = candidate()
        arguments[0]["nodes"]["record"]["transitions"][0]["target_node"] = "end"
        report = validate(*arguments)
        self.assertFalse(report["ok"], report)
        self.assertTrue(any("success and error must always reach record_result_node" in error for error in report["errors"]), report)
        arguments = candidate()
        arguments[0]["nodes"]["record"]["passthrough_default_transition"] = "end"
        report = validate(*arguments)
        self.assertFalse(report["ok"], report)
        self.assertTrue(any("record fallback must also reach record_result_node" in error for error in report["errors"]), report)
        arguments = candidate()
        arguments[0]["nodes"]["record_result"]["passthrough"] = False
        report = validate(*arguments)
        self.assertFalse(report["ok"], report)
        self.assertTrue(any("passthrough result-processing code node" in error for error in report["errors"]), report)

    def test_retry_uses_api_guarantee_not_an_invented_status_rule(self):
        arguments = candidate()
        arguments[2]["paths"]["/create_promise"]["post"]["responses"]["500"]["description"] = "The request failed. Its recording status is unknown."
        self.assert_failed_probe(arguments, "independent_api_error_500_without_no_write_guarantee")
        arguments = candidate()
        arguments[1]["source_rules"].append({"id": "retry", "source": "brief.md", "line": 37, "stage": "record", "text": "If it fails, try once more."})
        arguments[1]["security"]["write_attempt_limit"] = 1
        report = validate(*arguments)
        self.assertFalse(report["ok"], report)
        self.assertTrue(any("source-required second attempt" in error for error in report["errors"]), report)

    def test_stale_status_and_body_must_be_cleared_before_each_attempt(self):
        for field, probe in (("status_code", "independent_stale_record_status_no_retry"), ("data.ok", "independent_missing_record_body_no_retry")):
            with self.subTest(field=field):
                arguments = candidate()
                code = snippet(arguments, "approval")
                code["default"] = code["default"].replace(f"    vars['record_response.{field}'] = ''\n", "")
                self.assert_failed_probe(arguments, probe)


if __name__ == "__main__":
    unittest.main()
