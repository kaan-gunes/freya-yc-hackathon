import copy
import unittest

from builder.validation import _parse, _run_check, _safe_import, validate
from tests.test_builder_validation import candidate, guard, route
from tests.test_focused_conversation import snippet


def relative_candidate():
    arguments = candidate()
    workflow, policy, _, _ = arguments
    policy["security"]["validation_third_party_fixture"].update(
        speech_text="I am his sister.", speech_answer="1990-04-12")
    code = workflow["nodes"]["decision"]["pre_actions"][0]["function"]["parameters"]["properties"]["code"]
    code["default"] = code["default"].replace(
        "if event == 'third_party':\n    vars['party_confirmation'] = ''",
        "if event == 'third_party' or re.search(r'\\bsister\\b', speech_text, re.I):\n"
        "    vars['party_confirmation'] = ''\n"
        "    vars['stage'] = 'callback'\n"
        "    vars['outcome'] = 'not_reached'\n"
        "    vars['reason'] = 'unclear'\n"
        "    vars['route'] = 'callback'")
    workflow["nodes"]["callback"] = copy.deepcopy(workflow["nodes"]["identity"])
    workflow["nodes"]["callback"].update(name="callback", on_enter={"type": "tts", "text": "When can the customer be reached?"})
    workflow["nodes"]["decision"]["transitions"].insert(0, route("callback", guard("route", "callback")))
    return arguments


class ValidatorCompatTests(unittest.TestCase):
    def test_regex_alias_works_without_opening_other_members(self):
        for code in (
            "import re\nvars['matched'] = bool(re.fullmatch('yes', 'YES', re.I))",
            "from re import fullmatch, I\nvars['matched'] = bool(fullmatch('yes', 'YES', I))",
        ):
            with self.subTest(code=code):
                _parse(code)
                _run_check(code, {"expected": {"matched": True}})
        self.assertEqual(_safe_import("re").I, _safe_import("re").IGNORECASE)
        self.assertFalse(hasattr(_safe_import("re"), "purge"))
        with self.assertRaisesRegex(ValueError, "outside the allowlist"):
            _parse("from re import purge")
        with self.assertRaisesRegex(ValueError, "outside the standard-library allowlist"):
            _parse("import os")

    def test_customer_claims_and_relative_callback_have_consistent_close_states(self):
        arguments = relative_candidate()
        report = validate(*arguments)
        self.assertTrue(report["ok"], report)
        for event in ("paid", "dispute", "plan"):
            for suffix in ("", "_relative"):
                name = f"independent_pre_identity_{event}{suffix}"
                self.assertTrue(next(check["ok"] for check in report["checks"] if check["name"] == name))
            _run_check(snippet(arguments[0], "decision"), {
                "vars": dict(arguments[1]["security"]["validation_third_party_fixture"], speech_event=event),
                "expected": {"route": "callback", "party_confirmation": "", "bank_status": "unverified",
                             "record_authorization": "", "outcome": "not_reached", "reason": "unclear"}})

    def test_account_outcomes_before_identity_are_rejected_for_both_callers(self):
        for event, outcome, reason in (("paid", "paid", ""), ("dispute", "no_promise", "dispute"),
                                       ("plan", "transferred", "restructuring")):
            with self.subTest(event=event):
                arguments = relative_candidate()
                code = arguments[0]["nodes"]["decision"]["pre_actions"][0]["function"]["parameters"]["properties"]["code"]
                code["default"] += f"\nif event == {event!r} and vars.get('bank_status') != 'verified':\n    vars['outcome'] = {outcome!r}\n    vars['reason'] = {reason!r}\n"
                report = validate(*arguments)
                self.assertFalse(report["ok"], report)
                for suffix in ("", "_relative"):
                    probe = next(check for check in report["checks"] if check["name"] == f"independent_pre_identity_{event}{suffix}")
                    self.assertFalse(probe["ok"], report)
                    self.assertIn("close outcome/reason", probe["error"])


if __name__ == "__main__":
    unittest.main()
