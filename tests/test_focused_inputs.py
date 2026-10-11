import unittest

from builder.validation import validate
from tests.test_builder_validation import candidate


class FocusedInputTests(unittest.TestCase):
    def renamed_promise(self):
        arguments = candidate()
        workflow, policy, openapi, _ = arguments
        request = workflow["nodes"]["record"]["pre_actions"][0]["function"]["parameters"]["properties"]["body"]
        schema = openapi["paths"]["/create_promise"]["post"]["requestBody"]["content"]["application/json"]["schema"]
        mapping = {"amount": "payment_amount", "date": "payment_date"}
        for body in (request, schema):
            for old, new in mapping.items():
                body["properties"][new] = body["properties"].pop(old)
            body["required"] = [mapping.get(name, name) for name in body["required"]]
        policy["security"]["promise_request_fields"] = mapping
        return arguments

    def assert_rejected(self, arguments, message, **kwargs):
        report = validate(*arguments, **kwargs)
        self.assertFalse(report["ok"], report)
        self.assertIn(message, "\n".join(report["errors"]))

    def test_renamed_promise_request_preserves_independent_checks(self):
        report = validate(*self.renamed_promise())
        self.assertTrue(report["ok"], report)
        checks = {check["name"] for check in report["checks"] if check["ok"]}
        self.assertIn("independent_shared_currency_amount_record", checks)
        self.assertIn("independent_current_full_amount_record", checks)

    def test_wrong_semantic_binding_is_rejected(self):
        arguments = self.renamed_promise()
        arguments[1]["security"]["promise_request_fields"]["amount"] = "product_id"
        self.assert_rejected(arguments, "promise_request_fields.amount")
        arguments = self.renamed_promise()
        body = arguments[0]["nodes"]["record"]["pre_actions"][0]["function"]["parameters"]["properties"]["body"]
        body["properties"]["payment_amount"]["default"] = "{{bank_full_amount:json}}"
        self.assert_rejected(arguments, "amount promise did not bind the original numeric amount")

    def test_required_identity_question_cannot_be_removed_with_its_fixture(self):
        arguments = candidate()
        security = arguments[1]["security"]
        security["identity_questions"].pop()
        del security["validation_identity_code_fixture"]
        self.assert_rejected(arguments, "omitted a required identity question")
        arguments = candidate()
        arguments[1]["security"]["identity_questions"] = []
        self.assert_rejected(arguments, "explicitly declare every source-required question")

    def test_missing_required_fixtures_cannot_skip_identity_probes(self):
        for fixture in ("validation_identity_answer_fixture", "validation_identity_code_fixture"):
            with self.subTest(fixture=fixture):
                arguments = candidate()
                del arguments[1]["security"][fixture]
                self.assert_rejected(arguments, fixture)

    def test_original_multiline_identity_rule_is_used(self):
        arguments = candidate()
        lines = [""] * 14
        for rule in arguments[1]["source_rules"]:
            lines[rule["line"] - 1] = rule["text"]
        lines[10:14] = ["11. Ask TWO security questions:", "First the date of birth.", "Then the last four digits of the phone number.", ""]
        report = validate(*arguments, brief_lines={"brief.md": lines})
        self.assertTrue(report["ok"], report)

    def test_supplied_brief_cannot_be_rewritten_to_skip_required_question(self):
        arguments = candidate()
        rule = next(rule for rule in arguments[1]["source_rules"] if rule["id"] == "A11")
        actual_lines = [""] * 11
        for source in arguments[1]["source_rules"]:
            actual_lines[source["line"] - 1] = source["text"]
        rule["text"] = "Ask one security question: the date of birth."
        arguments[1]["security"]["identity_questions"].pop()
        self.assert_rejected(arguments, "omitted a required identity question", brief_lines={"brief.md": actual_lines})

    def test_date_only_input_does_not_require_numeric_code(self):
        arguments = candidate()
        security = arguments[1]["security"]
        security["identity_questions"].pop()
        next(rule for rule in arguments[1]["source_rules"] if rule["id"] == "A11")["text"] = "Ask one security question: the date of birth."
        del security["validation_identity_code_fixture"]
        del security["validation_identity_code_request_context"]
        report = validate(*arguments)
        self.assertTrue(report["ok"], report)
        self.assertTrue(any(check["name"] == "independent_identity_date_words_day_first" for check in report["checks"]))
        self.assertFalse(any("identity_code" in check["name"] for check in report["checks"]))

    def test_text_identity_still_runs_required_question_and_blank_speech_checks(self):
        arguments = candidate()
        workflow, policy, openapi, _ = arguments
        security = policy["security"]
        fixture = {"customer_id": "c-fixture", "bank_status": "unverified", "stage": "identity_text", "party_confirmation": "confirmed", "speech_event": "yes", "speech_answer": "Saffron"}
        security["identity_questions"] = [{"kind": "text", "source_rule": "A11", "source_text": "birthplace", "request_context": {"field": "birthplace"}, "fixture": fixture}]
        next(rule for rule in policy["source_rules"] if rule["id"] == "A11")["text"] = "Ask one security question: birthplace. Never ask DOB."
        for field in ("validation_identity_answer_fixture", "validation_identity_request_context", "validation_identity_code_fixture", "validation_identity_code_request_context"):
            del security[field]
        request = workflow["nodes"]["verify"]["pre_actions"][0]["function"]["parameters"]["properties"]["body"]
        schema = openapi["paths"]["/verify_identity"]["post"]["requestBody"]["content"]["application/json"]["schema"]
        for body in (request, schema):
            body["properties"]["field"]["enum"] = ["birthplace"]
        code = workflow["nodes"]["decision"]["pre_actions"][0]["function"]["parameters"]["properties"]["code"]
        code["default"] = code["default"].replace("        if vars.get('stage') == 'identity_phone':", "        if vars.get('stage') == 'identity_text':\n            vars['verification_answer'] = answer.strip()\n            vars['verification_question'] = 'birthplace'\n            vars['route'] = 'verify'\n        elif vars.get('stage') == 'identity_phone':")
        report = validate(*arguments)
        self.assertTrue(report["ok"], report)
        names = {check["name"] for check in report["checks"]}
        self.assertIn("independent_required_identity_question_0", names)
        self.assertIn("independent_missing_identity_text_speech_0", names)
        self.assertFalse(any("identity_date" in name or "identity_code" in name for name in names))
        code["default"] = code["default"].replace("vars['verification_question'] = 'birthplace'", "vars['verification_question'] = 'phone_last4'")
        self.assert_rejected(arguments, "invalid field enum")


if __name__ == "__main__":
    unittest.main()
