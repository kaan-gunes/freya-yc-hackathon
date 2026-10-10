import copy
import json
import pathlib
import unittest

from builder.validation import _json_equal, _parse, _run_check, validate


ROOT = pathlib.Path(__file__).resolve().parents[1]
OPENAPI = json.loads((ROOT / "build-the-builder/tools/openapi.json").read_text())


def guard(variable, operand):
    return {"logic": "or", "conditions": [{"variable": variable, "operator": "equals", "operand": operand}]}


def route(target, condition=None):
    return {"target_node": target, "condition": condition or {"operator": "always"}, "description": target}


def api(name, defaults, **extra):
    source = OPENAPI["paths"]["/" + name]["post"]["requestBody"]["content"]["application/json"]["schema"]
    fields = {key: dict(source["properties"][key], default=value) for key, value in defaults.items()}
    return dict(type="function", config={"maxRetries": 0}, function={
        "name": name, "handler": "__function__:api_call", "description": "Run " + name + " when the workflow requires it.", "parameters": {
            "type": "object", "properties": {
                "url": {"type": "string", "default": OPENAPI["servers"][0]["url"] + "/" + name},
                "method": {"type": "string", "default": "POST"},
                "body": {"type": "object", "properties": fields, "required": source["required"]},
            },
        },
    }, **extra)


def code_node(name, code, transitions):
    return {"name": name, "node_type": "code", "passthrough": True, "pre_actions": [{
        "type": "function", "function": {"name": "code_exec", "handler": "__function__:code_exec", "parameters": {
            "type": "object", "properties": {"code": {"type": "string", "default": code}},
        }},
    }], "transitions": transitions}


def candidate():
    identity = "data = result.get('data', {})\nvars['bank_status'] = 'verified' if data.get('ok') is True and data.get('all_verified') is True else 'unverified'\n"
    offer = "import datetime\nvars['record_authorization'] = ''\ntry:\n    day = datetime.date.fromisoformat(vars.get('date', ''))\n    if float(vars.get('amount', 0)) >= 20 and day.isoformat() >= '2026-10-14':\n        vars['record_authorization'] = 'offer_valid'\nexcept Exception:\n    pass\n"
    approval = "vars['record_authorization'] = ''\nif vars.get('approval') == 'yes' and not vars.get('correction') and not vars.get('recorded'):\n    vars['record_authorization'] = 'authorized'\n"
    saved = "vars['recorded'] = result.get('data', {}).get('ok') is True\n"
    closing = "body = config.get('body', {})\nbody['outcome'] = vars.get('outcome', 'not_verified')\nif body['outcome'] in ('promise', 'paid'):\n    body.pop('reason', None)\nelse:\n    body['reason'] = vars.get('reason', 'declined')\nconfig['body'] = body\n"
    workflow = {"initial_node": "identity", "nodes": {
        "identity": {"name": "identity", "node_type": "conversation", "tools": [api("verify_identity", {"customer_id": "{{customer_id}}", "field": "date_of_birth", "answer": "{{answer}}"}, post_process_code=identity)], "transitions": [route("account", guard("bank_status", "verified"))]},
        "account": {"name": "account", "node_type": "api_request", "passthrough": True, "pre_actions": [api("get_account", {"customer_id": "{{customer_id}}"})], "transitions": [route("offer")]},
        "offer": code_node("offer", offer, [route("confirmation")]),
        "confirmation": {"name": "confirmation", "node_type": "conversation", "extraction_schema": [{"name": "approval", "type": "string"}], "transitions": [route("approval", {"operator": "matches_intent", "description": "answered"})]},
        "approval": code_node("approval", approval, [route("record", guard("record_authorization", "authorized")), route("confirmation")]),
        "record": {"name": "record", "node_type": "api_request", "passthrough": True, "pre_actions": [api("create_promise", {"customer_id": "{{customer_id}}", "product_id": "{{validated_product}}", "amount": "{{validated_amount:json}}", "date": "{{validated_date}}"}, post_process_code=saved)], "transitions": [route("end")]},
        "end": {"name": "end", "node_type": "end_call", "transitions": [], "terminal": {"type": "function", "function": {"name": "end_call", "handler": "__function__:end_call", "parameters": {"type": "object", "properties": {"message_mode": {"type": "string", "default": "custom"}, "spoken_message": {"type": "string", "default": "Thank you. Goodbye."}}}}}},
    }, "tools": [api("close_call", {"customer_id": "{{customer_id}}", "outcome": "not_verified", "reason": "declined"}, pre_process_code=closing)]}
    workflow["tools"][0]["config"]["alwaysRunsAt"] = ["end_of_call"]
    policy = {"security": {
        "customer_id_field": "customer_id", "customer_id_variable": "customer_id",
        "identity_nodes": ["identity"], "trusted_variables": ["bank_status", "record_authorization", "recorded", "validated_product", "validated_amount", "validated_date"],
        "bank_verification_variable": "bank_status", "bank_gate": {"node": "identity", "variable": "bank_status", "operand": "verified", "target": "account"},
        "account_nodes": ["account"], "offer_guard_node": "offer", "approval_guard_node": "approval", "confirmation_nodes": ["confirmation"], "record_nodes": ["record"], "close_nodes": ["end"],
    }, "source_rules": [{"id": "A1", "source": "brief.md", "line": 1, "text": "rule", "stage": "identity"}], "unsupported": []}
    checks = [
        {"name": "identity_unverified", "node_id": "identity:verify_identity:post", "vars": {"bank_status": "verified"}, "result": {"data": {"ok": True, "all_verified": False}}, "expected": {"bank_status": "unverified"}},
        {"name": "invalid_amount", "node_id": "offer", "vars": {"amount": 1, "date": "2026-10-14"}, "expected": {"record_authorization": ""}},
        {"name": "invalid_date", "node_id": "offer", "vars": {"amount": 25, "date": "2026-02-30"}, "expected": {"record_authorization": ""}},
        {"name": "correction_clears_confirmation", "node_id": "approval", "vars": {"record_authorization": "authorized", "approval": "yes", "correction": True}, "expected": {"record_authorization": ""}},
        {"name": "business_failure_not_success", "node_id": "record:create_promise:post", "vars": {"recorded": True}, "result": {"status": "success", "status_code": 200, "data": {"ok": False}}, "expected": {"recorded": False}},
        {"name": "duplicate_promise_blocked", "node_id": "approval", "vars": {"approval": "yes", "recorded": True}, "expected": {"record_authorization": ""}},
        {"name": "negative_confirmation", "node_id": "approval", "vars": {"approval": "no", "record_authorization": "authorized"}, "expected": {"record_authorization": ""}},
    ]
    return workflow, policy, copy.deepcopy(OPENAPI), checks


class ValidationTests(unittest.TestCase):
    def assert_rejected(self, arguments, text):
        report = validate(*arguments)
        self.assertFalse(report["ok"], report)
        self.assertTrue(any(text in error for error in report["errors"]), report)

    def test_valid_candidate_and_local_reference(self):
        arguments = candidate()
        self.assertTrue(validate(*arguments)["ok"])
        document = arguments[2]
        schema = document["paths"]["/verify_identity"]["post"]["requestBody"]["content"]["application/json"]["schema"]
        document["components"] = {"schemas": {"Verify": schema}}
        document["paths"]["/verify_identity"]["post"]["requestBody"]["content"]["application/json"]["schema"] = {"$ref": "#/components/schemas/Verify"}
        self.assertTrue(validate(*arguments)["ok"])

    def test_gate_bypass_and_nested_conditions(self):
        arguments = candidate()
        arguments[0]["nodes"]["identity"]["transitions"][0]["condition"] = {"logic": "or", "conditions": [{"logic": "and", "conditions": [guard("bank_status", "verified")["conditions"][0], {"variable": "exception", "operator": "equals", "operand": "clear"}]}]}
        self.assertTrue(validate(*arguments)["ok"])
        arguments[0]["nodes"]["identity"]["transitions"][0]["condition"]["conditions"].append({"operator": "always"})
        self.assert_rejected(arguments, "bypasses trusted bank")
        arguments = candidate()
        arguments[0]["nodes"]["approval"]["passthrough_default_transition"] = "record"
        self.assert_rejected(arguments, "bypasses immutable authorization")

    def test_missing_gate_and_trusted_extraction(self):
        arguments = candidate()
        del arguments[1]["security"]["bank_gate"]
        self.assert_rejected(arguments, "security.bank_gate")
        arguments = candidate()
        arguments[0]["nodes"]["identity"]["extraction_schema"] = [{"name": "bank_status", "type": "string"}]
        self.assert_rejected(arguments, "extraction overwrites trusted")

    def test_model_tool_transitions_cannot_bypass_bank_action_guards(self):
        for source in ("identity", "approval"):
            with self.subTest(source=source):
                arguments = candidate()
                arguments[0]["nodes"][source]["transitions"][0]["is_tool_call"] = True
                self.assert_rejected(arguments, "model tool transition cannot enter a bank action")
        for name, defaults in (
            ("schedule_callback", {"customer_id": "{{customer_id}}", "date": "{{validated_date}}", "time": "{{callback_time}}"}),
            ("transfer_to_agent", {"customer_id": "{{customer_id}}", "queue": "support"}),
        ):
            with self.subTest(action=name):
                arguments = candidate()
                arguments[0]["nodes"][name] = {"name": name, "node_type": "api_request", "passthrough": True, "pre_actions": [api(name, defaults)], "transitions": [route("end")]}
                transition = route(name, guard("bank_status", "verified"))
                transition["is_tool_call"] = True
                arguments[0]["nodes"]["identity"]["transitions"].append(transition)
                self.assert_rejected(arguments, "model tool transition cannot enter a bank action")
        arguments = candidate()
        arguments[0]["nodes"]["identity"]["extraction_schema"] = [{"name": "customer_id", "type": "string"}]
        self.assert_rejected(arguments, "extraction overwrites trusted")

    def test_renamed_customer_binding(self):
        arguments = candidate()
        arguments[1]["security"].update(customer_id_field="call_secret", customer_id_variable="session_secret")
        for item in arguments[2]["paths"].values():
            schema = item["post"]["requestBody"]["content"]["application/json"]["schema"]
            schema["properties"]["call_secret"] = schema["properties"].pop("customer_id")
            schema["required"] = ["call_secret" if name == "customer_id" else name for name in schema["required"]]
        tools = arguments[0]["tools"][:]
        for node in arguments[0]["nodes"].values():
            tools.extend(node.get("tools", []))
            tools.extend(node.get("pre_actions", []))
        for tool in tools:
            if tool["function"]["handler"] == "__function__:api_call":
                body = tool["function"]["parameters"]["properties"]["body"]
                body["properties"]["call_secret"] = body["properties"].pop("customer_id")
                body["properties"]["call_secret"]["default"] = "{{session_secret}}"
                body["required"] = ["call_secret" if name == "customer_id" else name for name in body["required"]]
        self.assertTrue(validate(*arguments)["ok"])

    def test_schema_api_enum_and_body_binding(self):
        arguments = candidate()
        tool = arguments[0]["nodes"]["identity"]["tools"][0]
        tool["function"]["parameters"]["properties"]["body"]["properties"]["field"]["enum"] = ["invented"]
        self.assert_rejected(arguments, "enum")
        arguments = candidate()
        arguments[0]["nodes"]["account"]["pre_actions"][0]["function"]["parameters"]["properties"]["body"]["properties"]["customer_id"]["default"] = "c_fake"
        self.assert_rejected(arguments, "customer_id")
        arguments = candidate()
        arguments[0]["nodes"]["record"]["pre_actions"][0]["function"]["parameters"]["properties"]["body"]["properties"]["amount"]["type"] = "string"
        self.assert_rejected(arguments, "wrong type")
        arguments = candidate()
        arguments[0]["nodes"]["account"]["transitions"] = []
        self.assert_rejected(arguments, "final always")

    def test_invalid_snippet_and_forbidden_bank_writer(self):
        for code, reason in (("if !!!", "invalid Python"), ("import os", "allowlist"), ("vars['record_authorization'] = '{{bad}}'", "template braces"), ("vars['bank_status'] = 'verified'", "verification can only"), ("vars['bank_status'] = vars.get('speech')", "verification can only"), ("state = vars\nstate['bank_status'] = 'verified'", "alias")):
            arguments = candidate()
            arguments[0]["nodes"]["offer"]["pre_actions"][0]["function"]["parameters"]["properties"]["code"]["default"] = code
            self.assert_rejected(arguments, reason)

    def test_fake_checks_and_failed_expected_value(self):
        arguments = candidate()
        arguments[3][0]["node_id"] = "fictional"
        self.assert_rejected(arguments, "actual code node")
        arguments = candidate()
        arguments[3][0]["expected"] = {}
        self.assert_rejected(arguments, "nonempty expected")
        arguments = candidate()
        arguments[3][1]["expected"] = {"record_authorization": "denied"}
        self.assert_rejected(arguments, "expected 'denied'")
        arguments = candidate()
        arguments[3].pop()
        self.assert_rejected(arguments, "missing generated check")
        arguments = candidate()
        arguments[3][0].update(node_id="offer", vars={"amount": 1, "date": "2026-10-14"}, expected={"record_authorization": ""})
        self.assert_rejected(arguments, "must target a verification post-hook")
        arguments = candidate()
        arguments[3][1].update(node_id="approval", vars={"approval": "no"})
        self.assert_rejected(arguments, "must target the offer guard")
        arguments = candidate()
        arguments[3][-1].update(vars={"approval": "no", "recorded": False}, expected={"recorded": False})
        self.assert_rejected(arguments, "must assert cleared record authorization")
        arguments = candidate()
        arguments[3][4].update(node_id="identity:verify_identity:post", expected={"bank_status": "unverified"})
        self.assert_rejected(arguments, "must target a create_promise post-hook")

    def test_authorization_activation_and_mapping_have_one_owner(self):
        for code in (
            "vars['record_authorization'] = 'authorized'",
            "vars['record_authorization'] = vars.get('speech')",
            "vars.update({'record_authorization': 'authorized'})",
            "vars.setdefault('record_authorization', 'authorized')",
        ):
            with self.subTest(code=code):
                arguments = candidate()
                arguments[0]["nodes"]["offer"]["pre_actions"][0]["function"]["parameters"]["properties"]["code"]["default"] = code
                self.assert_rejected(arguments, "only the approval guard may activate")
        arguments = candidate()
        arguments[0]["nodes"]["identity"]["tools"][0]["response_mapping"] = [{"path": "data.all_verified", "variable": "record_authorization"}]
        self.assert_rejected(arguments, "response_mapping may not write record authorization")

    def test_lifecycle_hook_and_terminal_close(self):
        arguments = candidate()
        arguments[3].append({"name": "safe_close", "node_id": "workflow:close_call:pre", "vars": {"outcome": "promise"}, "config": {"body": {"outcome": "not_verified", "reason": "declined"}}, "expected": {"config.body": {"outcome": "promise"}}})
        self.assertTrue(validate(*arguments)["ok"])
        arguments[0]["tools"].append(copy.deepcopy(arguments[0]["tools"][0]))
        self.assert_rejected(arguments, "exactly once")

    def test_nulls_and_malformed_shapes_fail_without_crashing(self):
        arguments = candidate()
        arguments[0]["nodes"]["identity"]["max_turn_transition"] = None
        self.assert_rejected(arguments, "null value")
        arguments = candidate()
        arguments[0]["nodes"]["identity"]["tools"] = [None]
        self.assert_rejected(arguments, "malformed generated data")

    def test_json_number_equality_keeps_booleans_distinct(self):
        self.assertTrue(_json_equal(100.0, 100))
        self.assertTrue(_json_equal({"amounts": [100.0]}, {"amounts": [100]}))
        self.assertFalse(_json_equal(False, 0))
        self.assertFalse(_json_equal({"flag": [False]}, {"flag": [0]}))
        _run_check("vars['amount'] = 100.0", {"vars": {}, "expected": {"amount": 100}})
        with self.assertRaisesRegex(ValueError, "expected 0"):
            _run_check("vars['flag'] = False", {"vars": {}, "expected": {"flag": 0}})

    def test_datetime_internal_imports_do_not_grant_direct_time_import(self):
        code = "import datetime\nvars['time'] = datetime.time(19, 0).strftime('%H:%M')\nvars['date'] = datetime.datetime.strptime('14/10/2026', '%d/%m/%Y').date().isoformat()"
        _parse(code)
        _run_check(code, {"vars": {}, "expected": {"time": "19:00", "date": "2026-10-14"}})
        with self.assertRaisesRegex(ValueError, "allowlist"):
            _parse("import time")

    def test_identity_pre_hook_can_clear_but_cannot_verify(self):
        arguments = candidate()
        arguments[0]["nodes"]["identity"]["tools"][0]["pre_process_code"] = "vars['bank_status'] = 'unverified'"
        self.assertTrue(validate(*arguments)["ok"])
        arguments[0]["nodes"]["identity"]["tools"][0]["pre_process_code"] = "vars['bank_status'] = 'verified'"
        self.assert_rejected(arguments, "verification can only be activated")

    def test_lifecycle_and_model_tools_require_descriptions(self):
        for placement in ("lifecycle", "model"):
            with self.subTest(placement=placement):
                arguments = candidate()
                tool = arguments[0]["tools"][0] if placement == "lifecycle" else arguments[0]["nodes"]["identity"]["tools"][0]
                del tool["function"]["description"]
                self.assert_rejected(arguments, "function.description must be a nonempty string")


if __name__ == "__main__":
    unittest.main()
