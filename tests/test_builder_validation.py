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
        "type": "function", "function": {"name": "code_exec", "handler": "__function__:code_exec", "description": "Validate current state.", "parameters": {
            "type": "object", "properties": {"code": {"type": "string", "default": code}},
        }},
    }], "transitions": transitions}


def candidate():
    identity = "data = result.get('data', {})\nvars['bank_status'] = 'verified' if data.get('ok') is True and data.get('all_verified') is True else 'unverified'\nif vars['bank_status'] == 'verified':\n    vars['stage'] = 'account_pending'\n"
    decision = "event = vars.get('speech_event', '')\nvars['speech_event'] = ''\nvars['record_authorization'] = ''\nvars['route'] = 'verify'\nif vars.get('bank_status') == 'verified':\n    vars['stage'] = 'account_pending'\n    vars['route'] = 'account'\n"
    offer = """import datetime
vars['record_authorization'] = ''
vars['offer_fingerprint'] = ''
vars['readback_fingerprint'] = ''
vars['route'] = 'end'
try:
    day = datetime.date.fromisoformat(vars.get('date', ''))
    amount = float(vars.get('amount', 0))
    if 20 <= amount < float('inf') and '2026-10-14' <= day.isoformat() <= '2026-10-20':
        vars['validated_product'] = vars.get('bank_product', '')
        vars['validated_amount'] = amount
        vars['validated_date'] = day.isoformat()
        vars['offer_fingerprint'] = str(amount) + ':' + day.isoformat()
        vars['readback_fingerprint'] = vars['offer_fingerprint']
        vars['route'] = 'confirmation'
except Exception:
    pass
"""
    approval = """event = vars.get('approval', '')
correction = vars.get('correction', '')
vars['approval'] = ''
vars['correction'] = ''
vars['record_authorization'] = ''
vars['route'] = 'confirmation'
if event in ('human', 'plan', 'dispute'):
    vars['exception'] = event
    vars['route'] = 'transfer'
elif correction in ('yes', True):
    vars['readback_fingerprint'] = ''
    vars['route'] = 'offer'
elif not vars.get('recorded') and vars.get('offer_fingerprint') and vars.get('offer_fingerprint') == vars.get('readback_fingerprint') and vars.get('write_result') != 'unknown' and int(vars.get('write_attempts', 0)) < 2 and (event == 'yes' or vars.get('write_result') == 'failed'):
    vars['record_authorization'] = 'authorized'
    vars['write_attempts'] = int(vars.get('write_attempts', 0)) + 1
    vars['write_result'] = ''
    vars['route'] = 'record'
"""
    saved = "ok = result.get('data', {}).get('ok')\nvars['recorded'] = 'recorded' if ok is True else ''\nvars['write_result'] = 'ok' if ok is True else 'failed' if ok is False else 'unknown'\n"
    transfer_guard = "vars['transfer_authorization'] = ''\nif vars.get('exception') in ('human', 'plan', 'dispute'):\n    vars['transfer_queue'] = 'restructuring' if vars['exception'] == 'plan' else 'support'\n    vars['transfer_authorization'] = 'authorized'\n"
    closing = "body = config.get('body', {})\nbody['outcome'] = vars.get('outcome', 'not_verified')\nif body['outcome'] in ('promise', 'paid'):\n    body.pop('reason', None)\nelse:\n    body['reason'] = vars.get('reason', 'declined')\nconfig['body'] = body\n"
    workflow = {"initial_node": "identity", "nodes": {
        "identity": {"name": "identity", "node_type": "conversation", "on_enter": {"type": "tts", "text": "Am I speaking with the customer?"}, "extraction_schema": [{"name": "speech_event", "type": "string", "enum": ["", "yes", "question"], "min_confidence": 0, "max_retries": 1}], "transitions": [route("decision")]},
        "decision": code_node("decision", decision, [route("account", guard("bank_status", "verified")), route("verify", guard("route", "verify")), route("identity")]),
        "verify": {"name": "verify", "node_type": "api_request", "passthrough": True, "pre_actions": [api("verify_identity", {"customer_id": "{{customer_id}}", "field": "date_of_birth", "answer": "{{answer}}"}, post_process_code=identity)], "transitions": [route("decision")]},
        "account": {"name": "account", "node_type": "api_request", "passthrough": True, "pre_actions": [api("get_account", {"customer_id": "{{customer_id}}"})], "transitions": [route("offer")]},
        "offer": code_node("offer", offer, [route("confirmation", guard("route", "confirmation")), route("end")]),
        "confirmation": {"name": "confirmation", "node_type": "conversation", "on_enter": {"type": "tts", "text": "Do you confirm {{validated_amount}} on {{validated_date}}?"}, "extraction_schema": [{"name": "approval", "type": "string", "enum": ["", "yes", "no", "question", "human", "plan", "hardship", "dispute"], "min_confidence": 0, "max_retries": 1}, {"name": "correction", "type": "string", "enum": ["", "yes", "no"], "min_confidence": 0, "max_retries": 1}], "transitions": [route("approval")]},
        "approval": code_node("approval", approval, [route("record", guard("record_authorization", "authorized")), route("transfer_guard", guard("route", "transfer")), route("offer", guard("route", "offer")), route("confirmation")]),
        "record": {"name": "record", "node_type": "api_request", "passthrough": True, "pre_actions": [api("create_promise", {"customer_id": "{{customer_id}}", "product_id": "{{validated_product}}", "amount": "{{validated_amount:json}}", "date": "{{validated_date}}"}, post_process_code=saved)], "transitions": [route("end")]},
        "transfer_guard": code_node("transfer_guard", transfer_guard, [route("transfer", guard("transfer_authorization", "authorized")), route("end")]),
        "transfer": {"name": "transfer", "node_type": "api_request", "passthrough": True, "pre_actions": [api("transfer_to_agent", {"customer_id": "{{customer_id}}", "queue": "{{transfer_queue}}"})], "transitions": [route("end")]},
        "end": {"name": "end", "node_type": "end_call", "transitions": [], "terminal": {"type": "function", "function": {"name": "end_call", "handler": "__function__:end_call", "parameters": {"type": "object", "properties": {"message_mode": {"type": "string", "default": "custom"}, "spoken_message": {"type": "string", "default": "Thank you. Goodbye."}}}}}},
    }, "tools": [api("close_call", {"customer_id": "{{customer_id}}", "outcome": "not_verified", "reason": "declined"}, pre_process_code=closing)]}
    workflow["tools"][0]["config"]["alwaysRunsAt"] = ["end_of_call"]
    policy = {"security": {
        "customer_id_field": "customer_id", "customer_id_variable": "customer_id",
        "identity_nodes": ["identity"], "trusted_variables": ["bank_status", "record_authorization", "recorded", "validated_product", "validated_amount", "validated_date", "offer_fingerprint", "readback_fingerprint", "exception", "route", "stage", "write_attempts", "write_result", "transfer_authorization", "transfer_queue"],
        "bank_verification_variable": "bank_status", "bank_gate": {"node": "decision", "variable": "bank_status", "operand": "verified", "target": "account"},
        "account_nodes": ["account"], "offer_guard_node": "offer", "approval_guard_node": "approval", "confirmation_nodes": ["confirmation"], "record_nodes": ["record"], "close_nodes": ["end"],
        "decision_node": "decision", "write_attempt_limit": 2,
        "validation_state": {"proposed_amount": "amount", "proposed_date": "date", "approval_event": "approval", "correction": "correction", "recorded": "recorded", "offer_fingerprint": "offer_fingerprint", "readback_fingerprint": "readback_fingerprint", "exception": "exception", "route": "route", "stage": "stage", "write_attempts": "write_attempts", "write_result": "write_result"},
        "validation_events": {name: name for name in ("yes", "no", "question", "human", "plan", "hardship", "dispute")},
        "validation_routes": {name: name for name in ("account", "confirmation", "record", "offer", "transfer", "end")},
        "validation_fixture": {"customer_id": "c-fixture", "amount": "25", "date": "2026-10-14", "bank_product": "p1", "now": "2026-10-14T09:00:00", "bank_status": "verified"},
        "validation_confirmation_fixture": {"approval": "yes", "correction": ""},
        "validation_correction_fixture": {"approval": "yes", "correction": "yes"},
        "validation_identity_fixture": {"bank_status": "verified", "stage": "identity", "speech_event": "question"},
        "action_guards": {"transfer_to_agent": {"node": "transfer_guard", "variable": "transfer_authorization", "operand": "authorized"}},
    }, "source_rules": [{"id": "A1", "source": "brief.md", "line": 1, "text": "rule", "stage": "identity"}], "unsupported": []}
    checks = [
        {"name": "identity_unverified", "node_id": "verify:verify_identity:post", "vars": {"bank_status": "verified"}, "result": {"data": {"ok": True, "all_verified": False}}, "expected": {"bank_status": "unverified"}},
        {"name": "invalid_amount", "node_id": "offer", "vars": {"amount": 1, "date": "2026-10-14"}, "expected": {"record_authorization": ""}},
        {"name": "invalid_date", "node_id": "offer", "vars": {"amount": 25, "date": "2026-02-30"}, "expected": {"record_authorization": ""}},
        {"name": "correction_clears_confirmation", "node_id": "approval", "vars": {"record_authorization": "authorized", "approval": "yes", "correction": True}, "expected": {"record_authorization": ""}},
        {"name": "business_failure_not_success", "node_id": "record:create_promise:post", "vars": {"recorded": "recorded"}, "result": {"status": "success", "status_code": 200, "data": {"ok": False}}, "expected": {"recorded": ""}},
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
        arguments[0]["nodes"]["decision"]["transitions"][0]["condition"] = {"logic": "or", "conditions": [{"logic": "and", "conditions": [guard("bank_status", "verified")["conditions"][0], {"variable": "bank_status", "operator": "equals", "operand": "verified"}]}]}
        self.assertTrue(validate(*arguments)["ok"])
        arguments[0]["nodes"]["decision"]["transitions"][0]["condition"]["conditions"].append({"operator": "always"})
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
        for source in ("decision", "approval"):
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
        arguments[1]["security"]["validation_fixture"]["session_secret"] = arguments[1]["security"]["validation_fixture"].pop("customer_id")
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
        tool = arguments[0]["nodes"]["verify"]["pre_actions"][0]
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
        arguments[3][4].update(node_id="verify:verify_identity:post", expected={"bank_status": "unverified"})
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
        arguments[0]["nodes"]["verify"]["response_mapping"] = [{"path": "data.all_verified", "variable": "record_authorization"}]
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
        arguments[0]["nodes"]["verify"]["pre_actions"][0]["pre_process_code"] = "vars['bank_status'] = 'unverified'"
        self.assertTrue(validate(*arguments)["ok"])
        arguments[0]["nodes"]["verify"]["pre_actions"][0]["pre_process_code"] = "vars['bank_status'] = 'verified'"
        self.assert_rejected(arguments, "verification can only be activated")

    def test_lifecycle_and_engine_actions_require_descriptions(self):
        for placement in ("lifecycle", "engine"):
            with self.subTest(placement=placement):
                arguments = candidate()
                tool = arguments[0]["tools"][0] if placement == "lifecycle" else arguments[0]["nodes"]["verify"]["pre_actions"][0]
                del tool["function"]["description"]
                self.assert_rejected(arguments, "function.description must be a nonempty string")

    def test_next_and_format_preserve_failed_business_result(self):
        code = "product = next((p for p in vars.get('products', []) if p.get('product_id') == 'p1'), None)\nvars['display_amount'] = format(product['past_due'], '.2f')\nvars['recorded'] = result.get('data', {}).get('ok') is True\nvars['write_state'] = 'saved' if vars['recorded'] else 'failed'"
        _parse(code)
        _run_check(code, {
            "vars": {"products": [{"product_id": "p2", "past_due": 250}, {"product_id": "p1", "past_due": 100}], "recorded": True},
            "result": {"status": "success", "status_code": 200, "data": {"ok": False}},
            "expected": {"display_amount": "100.00", "recorded": False, "write_state": "failed"},
        })

    def test_independent_chains_reject_invalid_offer_resurrection_and_reject_all(self):
        arguments = candidate()
        properties = arguments[0]["nodes"]["approval"]["pre_actions"][0]["function"]["parameters"]["properties"]
        properties["code"]["default"] += "if event == 'yes' and not correction and not vars.get('recorded'):\n    vars['record_authorization'] = 'authorized'\n"
        report = validate(*arguments)
        self.assertTrue(all(check["ok"] for check in report["checks"] if not check["name"].startswith("independent_")), report)
        self.assert_rejected(arguments, "unsafe chain activated record authorization")
        arguments = candidate()
        properties = arguments[0]["nodes"]["approval"]["pre_actions"][0]["function"]["parameters"]["properties"]
        properties["code"]["default"] += "vars['record_authorization'] = ''\nvars['route'] = 'confirmation'\n"
        self.assert_rejected(arguments, "valid current yes")

    def test_graph_guard_domination_and_unconditional_action_loops(self):
        arguments = candidate()
        arguments[0]["nodes"]["account"]["transitions"] = [route("confirmation")]
        self.assert_rejected(arguments, "offer guard does not dominate")
        arguments = candidate()
        arguments[0]["nodes"]["offer"]["transitions"] = [route("offer")]
        self.assert_rejected(arguments, "unconditional action loop")
        arguments = candidate()
        arguments[0]["nodes"]["account"]["transitions"] = [route("approval")]
        self.assert_rejected(arguments, "confirmation readback does not dominate")

    def test_pre_hooks_cannot_mutate_url_customer_or_close_request_identity(self):
        for code in (
            "config['url'] = 'https://example.invalid/not-bank'",
            "request = config\nrequest['body']['customer_id'] = 'someone_else'",
            "config['body']['customer_id'] = vars.get('speech_event')",
        ):
            arguments = candidate()
            arguments[0]["nodes"]["verify"]["pre_actions"][0]["pre_process_code"] = code
            self.assert_rejected(arguments, "pre-hook may not")
        arguments = candidate()
        arguments[0]["tools"][0]["pre_process_code"] += "body['customer_id'] = 'someone_else'"
        self.assert_rejected(arguments, "outcome/reason only")
        arguments = candidate()
        arguments[0]["nodes"]["offer"]["pre_actions"][0]["function"]["parameters"]["properties"]["code"]["default"] = "vars['customer_id'] = 'someone_else'"
        self.assert_rejected(arguments, "overwrite the call customer identifier")

    def test_direct_closing_body_edits_preserve_request_and_customer(self):
        arguments = candidate()
        arguments[0]["tools"][0]["pre_process_code"] = "config['body']['outcome'] = vars.get('outcome', 'not_verified')\nif config['body']['outcome'] == 'promise':\n    config['body'].pop('reason', None)\nelse:\n    config['body']['reason'] = 'declined'\n"
        arguments[3].append({"name": "direct_safe_close", "node_id": "workflow:close_call:pre", "vars": {"outcome": "promise"}, "config": {"url": "https://bank.invalid/close_call", "body": {"customer_id": "c-fixture", "outcome": "not_verified", "reason": "declined"}}, "expected": {"config.body": {"customer_id": "c-fixture", "outcome": "promise"}, "config.url": "https://bank.invalid/close_call"}})
        self.assertTrue(validate(*arguments)["ok"])
        arguments[0]["tools"][0]["pre_process_code"] += "config['body']['customer_id'] = 'different'"
        self.assert_rejected(arguments, "outcome/reason only")
        arguments[0]["tools"][0]["pre_process_code"] = "config['url'] = 'https://example.invalid/not-bank'"
        self.assert_rejected(arguments, "replace body only")

    def test_variable_table_and_real_clock_aliases_are_rejected(self):
        for code in (
            "(state := vars)['bank_status'] = 'verified'",
            "def write(state):\n    state['bank_status'] = 'verified'\nwrite(state=vars)",
            "for state in [vars]:\n    state['bank_status'] = 'verified'",
            "writer = vars.update\nwriter({'bank_status': 'verified'})",
        ):
            arguments = candidate()
            arguments[0]["nodes"]["offer"]["pre_actions"][0]["function"]["parameters"]["properties"]["code"]["default"] = code
            self.assert_rejected(arguments, "invalid Python")
        with self.assertRaisesRegex(ValueError, "real-clock"):
            _parse("import datetime\nf = datetime.date.today\nvars['date'] = f().isoformat()")
        with self.assertRaisesRegex(ValueError, "unsafe callable"):
            _parse("runner = eval\nrunner('1 + 1')")

    def test_secondary_actions_need_trusted_bindings_and_a_real_guard(self):
        arguments = candidate()
        del arguments[1]["security"]["action_guards"]
        self.assert_rejected(arguments, "missing security.action_guards")
        arguments = candidate()
        tool = arguments[0]["nodes"]["transfer"]["pre_actions"][0]
        tool["function"]["parameters"]["properties"]["body"]["properties"]["queue"]["default"] = "{{approval}}"
        self.assert_rejected(arguments, "bind trusted validated state")
        arguments = candidate()
        arguments[0]["nodes"]["transfer_guard"]["pre_actions"][0]["function"]["parameters"]["properties"]["code"]["default"] += "vars['transfer_authorization'] = 'authorized'"
        self.assert_rejected(arguments, "authorized without caller intent")
        for operation, defaults in (
            ("schedule_callback", {"customer_id": "{{customer_id}}", "date": "{{approval}}", "time": "{{correction}}"}),
            ("add_note", {"customer_id": "{{customer_id}}", "product_id": "{{validated_product}}", "reason": "{{approval}}"}),
        ):
            with self.subTest(operation=operation):
                arguments = candidate()
                arguments[0]["nodes"][operation] = {"name": operation, "node_type": "api_request", "passthrough": True, "pre_actions": [api(operation, defaults)], "transitions": [route("end")]}
                arguments[0]["nodes"]["decision"]["transitions"].insert(0, route(operation, guard("route", operation)))
                self.assert_rejected(arguments, "bind trusted validated state")

    def test_consumed_speech_and_supported_schema_are_enforced(self):
        arguments = candidate()
        code = arguments[0]["nodes"]["approval"]["pre_actions"][0]["function"]["parameters"]["properties"]["code"]
        code["default"] = code["default"].replace("vars['approval'] = ''", "vars['approval'] = event")
        self.assert_rejected(arguments, "consumed extraction approval was not cleared")
        arguments = candidate()
        arguments[0]["nodes"]["confirmation"]["extraction_schema"][0]["type"] = "date"
        self.assert_rejected(arguments, "blankable string")
        arguments = candidate()
        arguments[1]["security"]["validation_state"]["proposed_amount"] = "unused"
        self.assert_rejected(arguments, "actual guard reads/writes")

    def test_verified_question_can_resume_after_one_fresh_reply(self):
        arguments = candidate()
        arguments[1]["security"]["validation_identity_resume_fixture"] = {"speech_event": "yes"}
        arguments[0]["nodes"]["identity"]["on_enter"]["text"] = "I will now check your account."
        arguments[0]["nodes"]["decision"]["pre_actions"][0]["function"]["parameters"]["properties"]["code"]["default"] = "event = vars.get('speech_event', '')\nvars['speech_event'] = ''\nvars['record_authorization'] = ''\nvars['route'] = 'verify'\nif vars.get('bank_status') == 'verified':\n    if vars.get('stage') == 'identity' and event == 'question':\n        vars['stage'] = 'account_resume'\n        vars['route'] = 'listen'\n    else:\n        vars['stage'] = 'account_pending'\n        vars['route'] = 'account'\n"
        arguments[0]["nodes"]["decision"]["transitions"][0]["condition"] = {"logic": "or", "conditions": [{"logic": "and", "conditions": [guard("bank_status", "verified")["conditions"][0], guard("route", "account")["conditions"][0]]}]}
        self.assertTrue(validate(*arguments)["ok"])
        del arguments[1]["security"]["validation_identity_resume_fixture"]
        self.assert_rejected(arguments, "fresh identity resume fixture")

    def test_independent_contract_reports_fixable_errors_together(self):
        arguments = candidate()
        arguments[1]["security"]["validation_confirmation_fixture"]["write_result"] = ""
        arguments[1]["security"]["validation_correction_fixture"] = {}
        arguments[1]["security"]["validation_state"]["approval_event"] = "unused_approval"
        report = validate(*arguments)
        for text in ("confirmation fixture may provide fresh speech only", "correction fixture must provide fresh speech inputs", "actual guard reads/writes"):
            self.assertTrue(any(text in error for error in report["errors"]), report)

    def test_additional_invalid_input_checks_do_not_replace_offer_guard_checks(self):
        for category in ("invalid_amount", "invalid_date"):
            with self.subTest(category=category):
                arguments = candidate()
                extra = {"name": category + "_handled_in_decision", "node_id": "decision", "vars": {"bank_status": "verified", "speech_event": "no"}, "expected": {"record_authorization": ""}}
                arguments[3].append(extra)
                self.assertTrue(validate(*arguments)["ok"])
                extra["expected"]["record_authorization"] = "authorized"
                self.assert_rejected(arguments, "expected 'authorized'")
                extra["expected"]["record_authorization"] = ""
                extra["node_id"] = "verify:verify_identity:post"
                extra["expected"] = {"bank_status": "unverified"}
                self.assert_rejected(arguments, "must target the offer guard")
                extra["node_id"] = "decision"
                extra["expected"] = {"record_authorization": ""}
                canonical = next(check for check in arguments[3] if check["name"] == category)
                canonical["node_id"] = "decision"
                self.assert_rejected(arguments, "must target the offer guard")
                canonical["node_id"] = "offer"
                arguments[3][:] = [check for check in arguments[3] if check["name"] != category]
                self.assert_rejected(arguments, "must target the offer guard")

    def test_completed_identity_does_not_wait_for_a_new_customer_reply(self):
        arguments = candidate()
        self.assertTrue(validate(*arguments)["ok"])
        code = arguments[0]["nodes"]["decision"]["pre_actions"][0]["function"]["parameters"]["properties"]["code"]
        code["default"] += "if vars.get('bank_status') == 'verified' and not event:\n    vars['route'] = 'listen'\n"
        arguments[0]["nodes"]["decision"]["transitions"][0]["condition"] = {"logic": "or", "conditions": [{"logic": "and", "conditions": [guard("bank_status", "verified")["conditions"][0], guard("route", "account")["conditions"][0]]}]}
        self.assert_rejected(arguments, "without a fresh caller reply")


if __name__ == "__main__":
    unittest.main()
