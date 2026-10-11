import unittest

from builder.validation import _run_check, validate
from tests.test_builder_validation import candidate


def snippet(workflow, node):
    return workflow["nodes"][node]["pre_actions"][0]["function"]["parameters"]["properties"]["code"]["default"]


class FocusedConversationTests(unittest.TestCase):
    def test_yearless_payment_forms_and_year_rollover(self):
        workflow, policy, _, _ = candidate()
        code = snippet(workflow, "offer")
        fixture = policy["security"]["validation_fixture"]
        for raw, today, expected, deadline in (
            ("6 November", "2026-11-05", "2026-11-06", "2026-11-20"),
            ("October 23rd", "2026-10-14", "2026-10-23", "2026-10-27"),
            ("the 23rd of October", "2026-10-14", "2026-10-23", "2026-10-27"),
            ("4 January", "2026-12-31", "2027-01-04", "2027-01-11"),
        ):
            with self.subTest(raw=raw):
                _run_check(code, {"vars": dict(fixture, date=raw, now=today + "T09:00:00", deadline=deadline),
                                  "expected": {"route": "confirmation", "validated_date": expected, "record_authorization": ""}})

    def test_ambiguous_or_impossible_payment_date_does_not_read_back(self):
        workflow, policy, _, _ = candidate()
        for raw in ("31 February", "October 14th"):
            with self.subTest(raw=raw):
                _run_check(snippet(workflow, "offer"), {
                    "vars": dict(policy["security"]["validation_fixture"], date=raw, deadline="2027-10-20"),
                    "expected": {"route": "clarify", "offer_fingerprint": "", "record_authorization": ""}})
        self.assertEqual(workflow["nodes"]["clarify_date"]["node_type"], "conversation")
        self.assertIn("year", workflow["nodes"]["clarify_date"]["on_enter"]["text"])

    def test_pre_identity_claims_stay_at_identity_and_human_request_survives(self):
        workflow, policy, _, _ = candidate()
        fixture = policy["security"]["validation_third_party_fixture"]
        for event in ("paid", "dispute", "plan"):
            with self.subTest(event=event):
                _run_check(snippet(workflow, "decision"), {
                    "vars": dict(fixture, speech_event=event),
                    "expected": {"route": "listen", "stage": "identity", "record_authorization": ""}})
        _run_check(snippet(workflow, "decision"), {
            "vars": dict(fixture, speech_event="human"),
            "expected": {"route": "listen", "human_requested": True}})
        _run_check(snippet(workflow, "decision"), {
            "vars": policy["security"]["validation_pre_identity_human_fixture"],
            "expected": {"route": "transfer", "record_authorization": ""}})

    def test_validator_catches_pre_identity_speech_and_account_close(self):
        arguments = candidate()
        code = snippet(arguments[0], "decision")
        arguments[0]["nodes"]["decision"]["pre_actions"][0]["function"]["parameters"]["properties"]["code"]["default"] = code + "\nif event == 'paid':\n    vars['route'] = 'prepaid'\n"
        arguments[0]["nodes"]["decision"]["transitions"].insert(0, {
            "target_node": "end", "condition": {"logic": "or", "conditions": [{"variable": "route", "operator": "equals", "operand": "prepaid"}]}, "description": "bad paid close"})
        arguments[0]["nodes"]["end"]["terminal"]["function"]["parameters"]["properties"]["spoken_message"]["default"] = "Payments can take one business day to appear. Goodbye."
        report = validate(*arguments)
        self.assertFalse(report["ok"])
        self.assertTrue(any(check["name"] == "independent_pre_identity_paid" and not check["ok"] for check in report["checks"]), report)

    def test_validator_catches_paid_close_state_while_identity_listener_remains(self):
        arguments = candidate()
        code = arguments[0]["nodes"]["decision"]["pre_actions"][0]["function"]["parameters"]["properties"]["code"]
        code["default"] += "\nif event == 'paid' and vars.get('bank_status') != 'verified':\n    vars['outcome'] = 'paid'\n"
        report = validate(*arguments)
        self.assertTrue(any(check["name"] == "independent_pre_identity_paid" and not check["ok"] and "close outcome" in check.get("error", "") for check in report["checks"]), report)

    def test_validator_catches_year_required_payment_parser(self):
        arguments = candidate()
        code = arguments[0]["nodes"]["offer"]["pre_actions"][0]["function"]["parameters"]["properties"]["code"]
        code["default"] = code["default"].replace("day = payment_day(vars.get('date', ''))", "day = datetime.date.fromisoformat(vars.get('date', ''))")
        report = validate(*arguments)
        self.assertTrue(any("payment_month_day" in check["name"] and not check["ok"] for check in report["checks"]), report)


if __name__ == "__main__":
    unittest.main()
