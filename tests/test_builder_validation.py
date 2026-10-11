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
    decision = r"""import datetime
import re
event = vars.get('speech_event', '')
current_date = vars.get('speech_date', '')
current_amount = vars.get('speech_amount', '')
speech_text = vars.get('speech_text', '')
answer = vars.get('speech_answer', '') or current_date or speech_text
party = vars.get('party_confirmation', '')
vars['speech_event'] = ''
vars['speech_answer'] = ''
vars['speech_date'] = ''
vars['speech_amount'] = ''
vars['speech_text'] = ''
vars['record_authorization'] = ''
vars['persuasion_attempts'] = int(vars.get('persuasion_attempts', 0))
vars['route'] = 'listen'
if event == 'third_party':
    vars['party_confirmation'] = ''
elif vars.get('bank_status') == 'verified' and vars.get('stage') in ('identity', 'account_resume', 'account_pending'):
    vars['stage'] = 'account_pending'
    vars['route'] = 'account'
elif vars.get('bank_status') == 'verified' and event == 'no':
    vars['persuasion_attempts'] += 1
elif vars.get('bank_status') == 'verified' and vars.get('stage') == 'payment' and event == 'yes' and current_amount and current_date:
    vars['amount'] = vars.get('bank_full_amount') if current_amount.strip().lower() == 'full amount' else current_amount
    vars['date'] = current_date
    vars['route'] = 'offer'
elif event == 'yes' and party != 'confirmed':
    vars['party_confirmation'] = 'confirmed'
elif party == 'confirmed' and answer and event == 'yes':
    try:
        clean = re.sub(r'[._]+$', '', answer.strip().lower()).strip()
        if vars.get('stage') == 'identity_phone':
            clean = re.sub(r'^(my last four digits are|my verification code is)\s+', '', clean)
            if re.fullmatch(r'[0-9]{' + str(int(vars.get('code_length', 4))) + '}', clean):
                vars['verification_answer'] = clean
                vars['verification_question'] = 'phone_last4'
                vars['route'] = 'verify'
        else:
            clean = re.sub(r'^my date of birth is\s+', '', clean)
            try:
                day = datetime.date.fromisoformat(clean)
            except ValueError:
                words = re.sub(r'(\d)(st|nd|rd|th)\b', r'\1', clean).replace(',', '').split()
                months = 'january february march april may june july august september october november december'.split()
                if words[0].isdigit():
                    day = datetime.date(int(words[2]), months.index(words[1]) + 1, int(words[0]))
                else:
                    day = datetime.date(int(words[2]), months.index(words[0]) + 1, int(words[1]))
            vars['verification_answer'] = day.isoformat()
            vars['verification_question'] = 'date_of_birth'
            vars['route'] = 'verify'
    except (ValueError, IndexError):
        pass
"""
    offer = r"""import datetime
import re
vars['record_authorization'] = ''
vars['offer_fingerprint'] = ''
vars['readback_fingerprint'] = ''
vars['route'] = 'end'
try:
    day = datetime.date.fromisoformat(vars.get('date', ''))
    raw_amount = str(vars.get('amount', 0)).strip()
    currency = re.fullmatch(r'([+-]?(?:[0-9]+(?:\.[0-9]+)?|\.[0-9]+)(?:[eE][+-]?[0-9]+)?)\s+dollars', raw_amount)
    amount = float(currency.group(1) if currency else raw_amount)
    if 20 <= amount < float('inf') and '2026-10-14' <= day.isoformat() <= '2026-10-20':
        vars['amount'] = amount
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
        "identity": {"name": "identity", "node_type": "conversation", "on_enter": {"type": "tts", "text": "Am I speaking with the customer?"}, "extraction_schema": [{"name": "speech_event", "type": "string", "enum": ["", "yes", "no", "question", "third_party"], "min_confidence": 0, "max_retries": 1}, {"name": "speech_answer", "type": "string", "min_confidence": 0, "max_retries": 1}, {"name": "speech_date", "type": "string", "min_confidence": 0, "max_retries": 1}, {"name": "speech_amount", "type": "string", "min_confidence": 0, "max_retries": 1}, {"name": "speech_text", "type": "string", "min_confidence": 0, "max_retries": 1}], "transitions": [route("decision")]},
        "decision": code_node("decision", decision, [route("account", {"logic": "or", "conditions": [{"logic": "and", "conditions": [guard("bank_status", "verified"), guard("route", "account")]}]}), route("verify", guard("route", "verify")), route("offer", guard("route", "offer")), route("identity")]),
        "verify": {"name": "verify", "node_type": "api_request", "passthrough": True, "pre_actions": [api("verify_identity", {"customer_id": "{{customer_id}}", "field": "{{verification_question}}", "answer": "{{verification_answer}}"}, post_process_code=identity)], "transitions": [route("decision")]},
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
        "identity_nodes": ["identity"], "trusted_variables": ["bank_status", "bank_full_amount", "record_authorization", "recorded", "validated_product", "validated_amount", "validated_date", "offer_fingerprint", "readback_fingerprint", "exception", "route", "stage", "write_attempts", "write_result", "persuasion_attempts", "party_confirmation", "verification_answer", "verification_question", "code_length", "transfer_authorization", "transfer_queue"],
        "bank_verification_variable": "bank_status", "bank_gate": {"node": "decision", "variable": "bank_status", "operand": "verified", "target": "account"},
        "account_nodes": ["account"], "offer_guard_node": "offer", "approval_guard_node": "approval", "confirmation_nodes": ["confirmation"], "record_nodes": ["record"], "close_nodes": ["end"],
        "decision_node": "decision", "write_attempt_limit": 2, "party_confirmation_operand": "confirmed", "identity_answer_request_field": "answer", "validation_identity_request_context": {"field": "date_of_birth"}, "validation_identity_code_request_context": {"field": "phone_last4"},
        "validation_state": {"proposed_amount": "amount", "proposed_date": "date", "approval_event": "approval", "correction": "correction", "decision_event": "speech_event", "decision_date": "speech_date", "decision_amount": "speech_amount", "full_amount": "bank_full_amount", "identity_answer": "speech_answer", "speech_text": "speech_text", "persuasion_attempts": "persuasion_attempts", "party_confirmation": "party_confirmation", "recorded": "recorded", "offer_fingerprint": "offer_fingerprint", "readback_fingerprint": "readback_fingerprint", "exception": "exception", "route": "route", "stage": "stage", "write_attempts": "write_attempts", "write_result": "write_result"},
        "validation_events": {name: name for name in ("yes", "no", "question", "human", "plan", "hardship", "dispute", "third_party")},
        "validation_routes": {name: name for name in ("account", "confirmation", "record", "offer", "transfer", "end")},
        "validation_fixture": {"customer_id": "c-fixture", "amount": "25", "date": "2026-10-14", "bank_product": "p1", "bank_full_amount": 50, "now": "2026-10-14T09:00:00", "bank_status": "verified", "stage": "payment"},
        "validation_confirmation_fixture": {"approval": "yes", "correction": ""},
        "validation_correction_fixture": {"approval": "yes", "correction": "yes"},
        "validation_identity_fixture": {"bank_status": "verified", "stage": "identity", "speech_event": "question"},
        "validation_third_party_fixture": {"bank_status": "unverified", "stage": "identity", "party_confirmation": "confirmed", "speech_event": "third_party", "speech_answer": "tomorrow"},
        "validation_identity_answer_fixture": {"customer_id": "c-fixture", "bank_status": "unverified", "stage": "identity", "party_confirmation": "confirmed", "speech_event": "yes", "speech_answer": "1990-04-12"},
        "validation_identity_code_fixture": {"customer_id": "c-fixture", "bank_status": "unverified", "stage": "identity_phone", "party_confirmation": "confirmed", "speech_event": "yes", "speech_text": "0014", "code_length": 4},
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
        arguments[0]["nodes"]["decision"]["transitions"][0]["condition"] = {"logic": "or", "conditions": [{"logic": "and", "conditions": [guard("bank_status", "verified")["conditions"][0], {"variable": "bank_status", "operator": "equals", "operand": "verified"}, guard("route", "account")["conditions"][0]]}]}
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
        for fixture_name in ("validation_fixture", "validation_identity_answer_fixture", "validation_identity_code_fixture"):
            fixture = arguments[1]["security"][fixture_name]
            fixture["session_secret"] = fixture.pop("customer_id")
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
        arguments[0]["nodes"]["decision"]["pre_actions"][0]["function"]["parameters"]["properties"]["code"]["default"] += "if vars.get('bank_status') == 'verified' and vars.get('stage') == 'account_pending' and event == 'question':\n    vars['stage'] = 'account_resume'\n    vars['route'] = 'listen'\n"
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

    def test_missing_speech_does_not_use_persuasion_or_start_an_offer(self):
        arguments = candidate()
        report = validate(*arguments)
        self.assertTrue(report["ok"], report)
        code = arguments[0]["nodes"]["decision"]["pre_actions"][0]["function"]["parameters"]["properties"]["code"]["default"]
        _run_check(code, {"vars": {"bank_status": "verified", "stage": "payment", "speech_event": "no"}, "expected": {"persuasion_attempts": 1, "route": "listen"}})
        for fault, reason in (
            ("vars['persuasion_attempts'] += 1", "missing speech consumed a persuasion attempt"),
            ("vars['route'] = 'offer'", "unsafe chain entered offer"),
            ("vars['route'] = 'verify'", "missing speech must return to a real listener"),
        ):
            with self.subTest(fault=fault):
                arguments = candidate()
                properties = arguments[0]["nodes"]["decision"]["pre_actions"][0]["function"]["parameters"]["properties"]
                properties["code"]["default"] += "if vars.get('stage') == 'payment' and not event:\n    " + fault + "\n"
                report = validate(*arguments)
                self.assertTrue(all(check["ok"] for check in report["checks"] if not check["name"].startswith("independent_")), report)
                self.assert_rejected(arguments, reason)

    def test_latest_third_party_overrides_prior_party_confirmation_and_answer(self):
        arguments = candidate()
        self.assertTrue(validate(*arguments)["ok"])
        for fault, reason in (
            ("if party == 'confirmed' and answer:\n    vars['route'] = 'verify'\n", "unsafe chain entered verify"),
            ("if event == 'third_party':\n    vars['party_confirmation'] = 'confirmed'\n", "did not clear prior first-party confirmation"),
        ):
            with self.subTest(fault=fault):
                arguments = candidate()
                properties = arguments[0]["nodes"]["decision"]["pre_actions"][0]["function"]["parameters"]["properties"]
                properties["code"]["default"] += fault
                report = validate(*arguments)
                self.assertTrue(all(check["ok"] for check in report["checks"] if not check["name"].startswith("independent_")), report)
                self.assert_rejected(arguments, reason)

    def test_decision_controls_require_real_distinct_trusted_state(self):
        for role in ("decision_event", "decision_date", "decision_amount", "full_amount", "identity_answer", "speech_text", "persuasion_attempts", "party_confirmation"):
            with self.subTest(role=role):
                arguments = candidate()
                arguments[1]["security"]["validation_state"][role] = "unused_" + role
                if role not in ("decision_event", "decision_date", "decision_amount", "identity_answer", "speech_text"):
                    arguments[1]["security"]["trusted_variables"].append("unused_" + role)
                self.assert_rejected(arguments, "actual guard reads/writes")
        arguments = candidate()
        arguments[1]["security"]["validation_state"]["party_confirmation"] = "bank_status"
        self.assert_rejected(arguments, "separate from bank, record and customer")
        arguments = candidate()
        arguments[1]["security"]["trusted_variables"].remove("persuasion_attempts")
        self.assert_rejected(arguments, "control roles must be trusted")
        arguments = candidate()
        arguments[1]["security"]["validation_third_party_fixture"] = {}
        self.assert_rejected(arguments, "third-party fixture must provide current identity state")
        arguments = candidate()
        arguments[1]["security"]["party_confirmation_operand"] = ""
        self.assert_rejected(arguments, "party_confirmation_operand")

    def test_current_full_amount_reference_records_the_bank_value(self):
        arguments = candidate()
        report = validate(*arguments)
        self.assertTrue(report["ok"], report)
        names = {check["name"] for check in report["checks"]}
        self.assertIn("independent_current_full_amount_record", names)
        self.assertIn("independent_full_amount_empty_event_blocks_offer", names)
        self.assertIn("independent_full_amount_no_event_blocks_offer", names)
        code = arguments[0]["nodes"]["decision"]["pre_actions"][0]["function"]["parameters"]["properties"]["code"]["default"]
        state = dict(arguments[1]["security"]["validation_fixture"], speech_event="yes", speech_amount="full amount", speech_date="2026-10-14", amount="0")
        _run_check(code, {"vars": state, "expected": {"amount": 50, "date": "2026-10-14", "route": "offer", "speech_event": "", "speech_amount": "", "speech_date": ""}})
        arguments[1]["security"]["validation_fixture"]["bank_full_amount"] = 72.35
        self.assertTrue(validate(*arguments)["ok"])

    def test_full_amount_cannot_use_words_a_stale_offer_or_a_wrong_record_amount(self):
        correct = "vars['amount'] = vars.get('bank_full_amount') if current_amount.strip().lower() == 'full amount' else current_amount"
        for wrong in (
            "vars['amount'] = current_amount if current_amount.strip().lower() == 'full amount' else vars.get('bank_full_amount')",
            "vars['amount'] = vars.get('amount') if current_amount.strip().lower() == 'full amount' else vars.get('bank_full_amount')",
            "vars['amount'] = vars.get('bank_full_amount') / 2 if current_amount.strip().lower() == 'full amount' else current_amount",
        ):
            with self.subTest(wrong=wrong):
                arguments = candidate()
                code = arguments[0]["nodes"]["decision"]["pre_actions"][0]["function"]["parameters"]["properties"]["code"]
                code["default"] = code["default"].replace(correct, wrong)
                report = validate(*arguments)
                self.assertTrue(all(check["ok"] for check in report["checks"] if check["name"] != "independent_current_full_amount_record"), report)
                self.assert_rejected(arguments, "independent_current_full_amount_record")
        arguments = candidate()
        code = arguments[0]["nodes"]["offer"]["pre_actions"][0]["function"]["parameters"]["properties"]["code"]
        code["default"] = code["default"].replace("vars['validated_amount'] = amount", "vars['validated_amount'] = amount / 2")
        self.assert_rejected(arguments, "amount promise did not bind the original numeric amount")

    def test_full_amount_needs_a_current_acceptance_event(self):
        for event, name in (("", "empty"), ("no", "no")):
            with self.subTest(event=event):
                arguments = candidate()
                code = arguments[0]["nodes"]["decision"]["pre_actions"][0]["function"]["parameters"]["properties"]["code"]
                code["default"] += f"if vars.get('stage') == 'payment' and event == {event!r} and current_amount:\n    vars['amount'] = vars.get('bank_full_amount')\n    vars['date'] = current_date\n    vars['route'] = 'offer'\n"
                report = validate(*arguments)
                self.assertTrue(next(check["ok"] for check in report["checks"] if check["name"] == "independent_current_full_amount_record"), report)
                self.assert_rejected(arguments, f"independent_full_amount_{name}_event_blocks_offer")

    def test_full_amount_metadata_must_be_trusted_numeric_and_read_only_to_speech(self):
        for value in (None, "50", True, 0, -1, float("nan"), float("inf"), 10 ** 400):
            with self.subTest(value=value):
                arguments = candidate()
                arguments[1]["security"]["validation_fixture"]["bank_full_amount"] = value
                self.assert_rejected(arguments, "finite positive numeric full_amount")
        arguments = candidate()
        arguments[1]["security"]["trusted_variables"].remove("bank_full_amount")
        self.assert_rejected(arguments, "control roles must be trusted")
        arguments = candidate()
        code = arguments[0]["nodes"]["decision"]["pre_actions"][0]["function"]["parameters"]["properties"]["code"]
        code["default"] += "vars['bank_full_amount'] = current_amount\n"
        self.assert_rejected(arguments, "decision may not overwrite the trusted bank full_amount")
        arguments = candidate()
        code = arguments[0]["nodes"]["decision"]["pre_actions"][0]["function"]["parameters"]["properties"]["code"]
        code["default"] = code["default"].replace("vars['speech_amount'] = ''", "vars['speech_amount'] = current_amount")
        self.assert_rejected(arguments, "consumed extraction speech_amount was not cleared")

    def test_currency_amounts_reach_record_from_current_speech_and_shared_offer_guard(self):
        arguments = candidate()
        arguments[1]["security"]["validation_fixture"].update(bank_full_amount=72.35, amount="35.25")
        report = validate(*arguments)
        self.assertTrue(report["ok"], report)
        for name in ("independent_current_currency_amount_record", "independent_shared_currency_amount_record"):
            self.assertTrue(next(check["ok"] for check in report["checks"] if check["name"] == name), report)
        code = arguments[0]["nodes"]["offer"]["pre_actions"][0]["function"]["parameters"]["properties"]["code"]["default"]
        _run_check(code, {"vars": {"amount": "35.25 dollars", "date": "2026-10-14"}, "expected": {"amount": 35.25, "validated_amount": 35.25, "route": "confirmation"}})
        offer = arguments[0]["nodes"]["offer"]["pre_actions"][0]["function"]["parameters"]["properties"]["code"]
        offer["default"] = offer["default"].replace("        vars['amount'] = amount\n", "")
        self.assertTrue(validate(*arguments)["ok"])

    def test_currency_normalization_cannot_live_only_in_main_decision(self):
        arguments = candidate()
        decision = arguments[0]["nodes"]["decision"]["pre_actions"][0]["function"]["parameters"]["properties"]["code"]
        decision["default"] = decision["default"].replace("current_amount = vars.get('speech_amount', '')", "current_amount = vars.get('speech_amount', '')\nif current_amount.endswith(' dollars'):\n    current_amount = current_amount[:-8]")
        offer = arguments[0]["nodes"]["offer"]["pre_actions"][0]["function"]["parameters"]["properties"]["code"]
        offer["default"] = offer["default"].replace("amount = float(currency.group(1) if currency else raw_amount)", "amount = float(raw_amount)")
        report = validate(*arguments)
        self.assertTrue(next(check["ok"] for check in report["checks"] if check["name"] == "independent_current_currency_amount_record"), report)
        self.assert_rejected(arguments, "independent_shared_currency_amount_record")

    def test_currency_amounts_reject_arbitrary_digits_and_non_finite_fallbacks(self):
        arguments = candidate()
        offer = arguments[0]["nodes"]["offer"]["pre_actions"][0]["function"]["parameters"]["properties"]["code"]
        offer["default"] = offer["default"].replace("currency = re.fullmatch(", "currency = re.search(")
        for label in ("trailing_prose", "date_digits"):
            self.assert_rejected(arguments, "independent_invalid_currency_amount_" + label)
        arguments = candidate()
        offer = arguments[0]["nodes"]["offer"]["pre_actions"][0]["function"]["parameters"]["properties"]["code"]
        offer["default"] = offer["default"].replace("raw_amount = str(vars.get('amount', 0)).strip()", "raw_amount = str(vars.get('amount', 0)).strip()\n    if raw_amount in ('NaN dollars', 'Infinity dollars'):\n        raw_amount = str(vars.get('bank_full_amount'))")
        for label in ("nan", "infinity"):
            self.assert_rejected(arguments, "independent_invalid_currency_amount_" + label)

    def test_spoken_identity_dates_reach_verify_with_the_original_iso_answer(self):
        arguments = candidate()
        report = validate(*arguments)
        self.assertTrue(report["ok"], report)
        date_checks = [check for check in report["checks"] if check["name"].startswith("independent_identity_date_words_")]
        self.assertEqual(len(date_checks), 6)
        self.assertTrue(all(check["ok"] for check in date_checks), report)
        code = arguments[0]["nodes"]["decision"]["pre_actions"][0]["function"]["parameters"]["properties"]["code"]["default"]
        _run_check(code, {"vars": arguments[1]["security"]["validation_identity_answer_fixture"], "expected": {"verification_answer": "1990-04-12", "route": "verify", "speech_answer": ""}})
        for fault, reason in (
            ("if answer and not re.fullmatch(r'[0-9]{4}-[0-9]{2}-[0-9]{2}', answer):\n    vars['route'] = 'listen'\n", "spoken identity date did not reach a verification API"),
            ("if vars.get('route') == 'verify':\n    vars['verification_answer'] = '2001-01-01'\n", "not bound as the canonical ISO verification answer"),
        ):
            with self.subTest(fault=fault):
                arguments = candidate()
                properties = arguments[0]["nodes"]["decision"]["pre_actions"][0]["function"]["parameters"]["properties"]
                properties["code"]["default"] += fault
                report = validate(*arguments)
                self.assertTrue(all(check["ok"] for check in report["checks"] if not check["name"].startswith("independent_")), report)
                self.assert_rejected(arguments, reason)
        arguments = candidate()
        body = arguments[0]["nodes"]["verify"]["pre_actions"][0]["function"]["parameters"]["properties"]["body"]
        body["properties"]["answer"]["default"] = "{{speech_answer}}"
        self.assert_rejected(arguments, "no bound answer")

    def test_identity_date_fixture_and_request_field_are_real(self):
        for invalid in ({}, {"stage": "identity", "speech_answer": "12 April 1990"}, {"stage": "identity", "speech_answer": "1990-02-30"}):
            with self.subTest(fixture=invalid):
                arguments = candidate()
                arguments[1]["security"]["validation_identity_answer_fixture"] = invalid
                self.assert_rejected(arguments, "validation_identity_answer_fixture")
        for invalid in ("not_a_request_field", "customer_id", ""):
            with self.subTest(request_field=invalid):
                arguments = candidate()
                arguments[1]["security"]["identity_answer_request_field"] = invalid
                self.assert_rejected(arguments, "actual verification request property")
        arguments = candidate()
        arguments[1]["security"]["validation_third_party_fixture"] = {"stage": "identity", "speech_event": "third_party"}
        self.assert_rejected(arguments, "nonempty actual speech field besides decision_event")

    def test_identity_date_in_main_date_reaches_verify_and_still_blocks_third_party(self):
        arguments = candidate()
        arguments[1]["security"]["validation_third_party_fixture"].update(speech_answer="", speech_date="12 April 1990")
        report = validate(*arguments)
        self.assertTrue(report["ok"], report)
        for name in ("independent_identity_date_in_main_date", "independent_missing_decision_speech", "independent_latest_third_party_blocks_identity"):
            self.assertTrue(next(check for check in report["checks"] if check["name"] == name)["ok"], report)
        arguments = candidate()
        code = arguments[0]["nodes"]["decision"]["pre_actions"][0]["function"]["parameters"]["properties"]["code"]
        code["default"] = code["default"].replace("answer = vars.get('speech_answer', '') or current_date", "answer = vars.get('speech_answer', '')")
        report = validate(*arguments)
        self.assertTrue(all(check["ok"] for check in report["checks"] if check["name"].startswith("independent_identity_date_words_")), report)
        self.assertTrue(all(check["ok"] for check in report["checks"] if not check["name"].startswith("independent_")), report)
        self.assert_rejected(arguments, "independent_identity_date_in_main_date")
        arguments = candidate()
        code = arguments[0]["nodes"]["decision"]["pre_actions"][0]["function"]["parameters"]["properties"]["code"]
        code["default"] = code["default"].replace("vars['speech_date'] = ''", "vars['speech_date'] = current_date")
        self.assert_rejected(arguments, "consumed extraction speech_date was not cleared")

    def test_missing_identity_speech_does_not_reuse_a_cached_answer(self):
        arguments = candidate()
        report = validate(*arguments)
        self.assertTrue(report["ok"], report)
        self.assertTrue(next(check for check in report["checks"] if check["name"] == "independent_missing_identity_speech")["ok"], report)
        code = arguments[0]["nodes"]["decision"]["pre_actions"][0]["function"]["parameters"]["properties"]["code"]
        code["default"] += "if vars.get('bank_status') != 'verified' and party == 'confirmed' and not event and not answer and vars.get('verification_answer'):\n    vars['route'] = 'verify'\n"
        report = validate(*arguments)
        self.assertTrue(all(check["ok"] for check in report["checks"] if check["name"].startswith("independent_identity_date_words_") or check["name"] == "independent_identity_date_in_main_date"), report)
        self.assert_rejected(arguments, "independent_missing_identity_speech: unsafe chain entered verify")

    def test_full_text_identity_paths_preserve_dates_and_leading_zero_codes(self):
        arguments = candidate()
        report = validate(*arguments)
        self.assertTrue(report["ok"], report)
        text_checks = [check for check in report["checks"] if "_in_speech_text_" in check["name"]]
        self.assertEqual(len(text_checks), 5)
        self.assertTrue(all(check["ok"] for check in text_checks), report)
        state = dict(arguments[1]["security"]["validation_identity_code_fixture"], speech_text="My last four digits are 0014.")
        code = arguments[0]["nodes"]["decision"]["pre_actions"][0]["function"]["parameters"]["properties"]["code"]["default"]
        _run_check(code, {"vars": state, "expected": {"verification_answer": "0014", "verification_question": "phone_last4", "bank_status": "unverified", "route": "verify", "speech_text": ""}})

    def test_full_text_identity_mutations_cannot_pass_older_date_checks(self):
        for original, replacement, reason in (
            ("answer = vars.get('speech_answer', '') or current_date or speech_text", "answer = vars.get('speech_answer', '') or current_date", "independent_identity_date_in_speech_text_period"),
            ("clean = re.sub(r'[._]+$', '', answer.strip().lower()).strip()", "clean = answer.strip().lower()", "independent_identity_date_in_speech_text_period"),
            ("vars['verification_answer'] = clean", "vars['verification_answer'] = str(int(clean))", "unchanged canonical code verification answer"),
            ("vars['verification_question'] = 'phone_last4'", "vars['verification_question'] = 'date_of_birth'", "spoken identity code request did not match"),
            ("vars['speech_text'] = ''", "vars['speech_text'] = speech_text", "consumed extraction speech_text was not cleared"),
        ):
            with self.subTest(reason=reason):
                arguments = candidate()
                code = arguments[0]["nodes"]["decision"]["pre_actions"][0]["function"]["parameters"]["properties"]["code"]
                self.assertIn(original, code["default"])
                code["default"] = code["default"].replace(original, replacement)
                report = validate(*arguments)
                self.assertTrue(all(check["ok"] for check in report["checks"] if check["name"].startswith("independent_identity_date_words_") or check["name"] == "independent_identity_date_in_main_date"), report)
                self.assert_rejected(arguments, reason)

    def test_full_text_identity_still_needs_an_answer_event_and_no_stale_code(self):
        for fault, reason in (
            ("if vars.get('stage') == 'identity_phone' and not event and not answer and vars.get('verification_answer'):\n    vars['route'] = 'verify'\n", "independent_missing_identity_code_speech: unsafe chain entered verify"),
            ("if vars.get('stage') == 'identity_phone' and event == 'third_party':\n    vars['route'] = 'verify'\n", "independent_latest_third_party_blocks_identity_code: unsafe chain entered verify"),
        ):
            with self.subTest(reason=reason):
                arguments = candidate()
                code = arguments[0]["nodes"]["decision"]["pre_actions"][0]["function"]["parameters"]["properties"]["code"]
                code["default"] += fault
                report = validate(*arguments)
                self.assertTrue(all(check["ok"] for check in report["checks"] if "_in_speech_text_" in check["name"]), report)
                self.assert_rejected(arguments, reason)
        arguments = candidate()
        code = arguments[0]["nodes"]["decision"]["pre_actions"][0]["function"]["parameters"]["properties"]["code"]
        code["default"] = code["default"].replace("elif party == 'confirmed' and answer and event == 'yes':", "elif party == 'confirmed' and answer:")
        report = validate(*arguments)
        self.assertTrue(all(check["ok"] for check in report["checks"] if "_in_speech_text_" in check["name"]), report)
        for kind in ("date", "code"):
            for event in ("empty", "unknown", "question"):
                name = f"independent_identity_{kind}_{event}_event_blocks_verification"
                self.assertFalse(next(check for check in report["checks"] if check["name"] == name)["ok"], report)

    def test_identity_code_fixture_and_context_cannot_be_fake(self):
        for value in ("", "0014.", 14, "1234", "0"):
            with self.subTest(code=value):
                arguments = candidate()
                arguments[1]["security"]["validation_identity_code_fixture"]["speech_text"] = value
                self.assert_rejected(arguments, "canonical numeric string in speech_text")
        for context in ({}, {"unknown": "phone_last4"}, {"field": "unknown"}, {"answer": "0014"}):
            with self.subTest(context=context):
                arguments = candidate()
                arguments[1]["security"]["validation_identity_code_request_context"] = context
                self.assert_rejected(arguments, "validation_identity_code_request_context")

    def test_word_date_checks_cannot_fall_back_to_other_fresh_fixture_fields(self):
        arguments = candidate()
        arguments[1]["security"]["validation_identity_answer_fixture"].update(speech_date="1990-04-12", speech_text="1990-04-12")
        code = arguments[0]["nodes"]["decision"]["pre_actions"][0]["function"]["parameters"]["properties"]["code"]
        code["default"] = code["default"].replace("answer = vars.get('speech_answer', '') or current_date or speech_text", "answer = vars.get('speech_answer', '')\nif not re.fullmatch(r'[0-9]{4}-[0-9]{2}-[0-9]{2}', answer):\n    answer = current_date or speech_text")
        report = validate(*arguments)
        word_checks = [check for check in report["checks"] if check["name"].startswith("independent_identity_date_words_")]
        self.assertEqual(len(word_checks), 6)
        self.assertTrue(all(not check["ok"] for check in word_checks), report)
        self.assert_rejected(arguments, "independent_identity_date_words_day_first")

    def test_identity_code_length_is_not_fixed_by_the_validator(self):
        arguments = candidate()
        fixture = arguments[1]["security"]["validation_identity_code_fixture"]
        fixture.update(speech_text="000014", code_length=6)
        arguments[1]["security"]["validation_identity_code_request_context"] = {"field": "security_code"}
        schema = arguments[2]["paths"]["/verify_identity"]["post"]["requestBody"]["content"]["application/json"]["schema"]
        schema["properties"]["field"]["enum"] = ["date_of_birth", "security_code"]
        body = arguments[0]["nodes"]["verify"]["pre_actions"][0]["function"]["parameters"]["properties"]["body"]
        body["properties"]["field"]["enum"] = ["date_of_birth", "security_code"]
        code = arguments[0]["nodes"]["decision"]["pre_actions"][0]["function"]["parameters"]["properties"]["code"]
        code["default"] = code["default"].replace("vars['verification_question'] = 'phone_last4'", "vars['verification_question'] = 'security_code'")
        report = validate(*arguments)
        self.assertTrue(report["ok"], report)

    def test_spoken_identity_date_requires_the_declared_request_question(self):
        arguments = candidate()
        body = arguments[0]["nodes"]["verify"]["pre_actions"][0]["function"]["parameters"]["properties"]["body"]
        body["properties"]["field"]["default"] = "phone_last4"
        report = validate(*arguments)
        self.assertTrue(all(check["ok"] for check in report["checks"] if not check["name"].startswith("independent_")), report)
        self.assert_rejected(arguments, "did not match the declared pending-question context")
        for context, reason in (
            ({}, "must declare the pending question"),
            ({"not_a_request_field": "date_of_birth"}, "real verification request property types and enums"),
            ({"field": "unknown_question"}, "real verification request property types and enums"),
            ({"field": False}, "real verification request property types and enums"),
            ({"customer_id": "c-fixture"}, "cannot include customer or answer fields"),
            ({"answer": "1990-04-12"}, "cannot include customer or answer fields"),
            ({"field": "{{question}}"}, "needs literal values"),
        ):
            with self.subTest(context=context):
                arguments = candidate()
                arguments[1]["security"]["validation_identity_request_context"] = context
                self.assert_rejected(arguments, reason)

    def test_identity_request_context_uses_supplied_property_and_operand_names(self):
        arguments = candidate()
        schema = arguments[2]["paths"]["/verify_identity"]["post"]["requestBody"]["content"]["application/json"]["schema"]
        schema["properties"]["question_kind"] = schema["properties"].pop("field")
        schema["properties"]["question_kind"]["enum"] = ["birthdate", "phone_last4"]
        schema["required"] = ["question_kind" if name == "field" else name for name in schema["required"]]
        body = arguments[0]["nodes"]["verify"]["pre_actions"][0]["function"]["parameters"]["properties"]["body"]
        body["properties"]["question_kind"] = body["properties"].pop("field")
        body["properties"]["question_kind"].update(enum=["birthdate", "phone_last4"])
        body["required"] = ["question_kind" if name == "field" else name for name in body["required"]]
        arguments[1]["security"]["validation_identity_request_context"] = {"question_kind": "birthdate"}
        arguments[1]["security"]["validation_identity_code_request_context"] = {"question_kind": "phone_last4"}
        code = arguments[0]["nodes"]["decision"]["pre_actions"][0]["function"]["parameters"]["properties"]["code"]
        code["default"] = code["default"].replace("vars['verification_question'] = 'date_of_birth'", "vars['verification_question'] = 'birthdate'")
        report = validate(*arguments)
        self.assertTrue(report["ok"], report)


if __name__ == "__main__":
    unittest.main()
