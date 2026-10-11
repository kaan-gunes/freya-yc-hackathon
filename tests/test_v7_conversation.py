"""Small synthetic conversations and mutants; no saved workflow or live access."""
import copy
import unittest

from builder.validation import _run_check, validate
from tests.test_builder_validation import candidate, guard, route
from tests.test_focused_conversation import snippet


def conversation_candidate():
    args = candidate()
    workflow, policy, _, _ = args
    nodes, security = workflow["nodes"], policy["security"]
    security["trusted_variables"] += ["bank_floor", "floor_offered", "support_offered", "question_text", "answer_text"]
    base = dict(security["validation_fixture"], bank_floor=25, floor_offered="yes", support_offered="yes", persuasion_attempts=0)
    security["validation_conversation"] = {
        "state": {"minimum_amount": "bank_floor", "floor_offered": "floor_offered", "support_offered": "support_offered"},
        "minimum_fixture": base, "support_fixture": dict(base, stage="support")}
    decision = nodes["decision"]["pre_actions"][0]["function"]["parameters"]["properties"]["code"]
    decision["default"] = "prior_attempts = vars.get('persuasion_attempts', 0)\n" + decision["default"] + r'''
vars['question_text'] = 'Please repeat your question.'
vars['answer_text'] = 'Here is your payment.'
text = speech_text.lower()
if vars.get('recorded') == 'recorded' and event == 'no':
    vars['route'] = 'end'
plan_requested = bool(re.search(r'\b(need|want|request) (?:lower instalments|a new payment plan)\b', text)) and not re.search(r'\b(do not|don.t) want\b', text)
if vars.get('bank_status') == 'verified' and vars.get('stage') in ('payment', 'support'):
    if vars.get('stage') == 'support' and ('do not want a transfer' in text or text.startswith('no, thanks')):
        vars['persuasion_attempts'] = prior_attempts
        vars['question_text'] = 'I cannot offer a discount.'
        vars['outcome'] = 'no_promise'
        vars['reason'] = 'hardship'
        vars['route'] = 'end'
    elif plan_requested:
        vars['persuasion_attempts'] = prior_attempts
        vars['exception'] = 'plan'
        vars['route'] = 'transfer'
    elif 'minimum payment' in text:
        vars['persuasion_attempts'] = prior_attempts
        vars['question_text'] = 'The minimum payment is ' + str(vars.get('bank_floor')) + ' dollars.'
        vars['route'] = 'listen'
    elif 'i can pay' in text and 'robot' in text and current_date and current_amount:
        vars['persuasion_attempts'] = prior_attempts
        vars['answer_text'] = 'I am the bank digital assistant.'
        vars['amount'] = current_amount
        vars['date'] = current_date
        vars['route'] = 'offer'
'''
    listener = copy.deepcopy(nodes["identity"])
    nodes["payment_listen"] = dict(listener, name="payment_listen", on_enter={"type": "tts", "text": "{{question_text}}"})
    nodes["safe_retry"] = dict(copy.deepcopy(listener), name="safe_retry", on_enter={"type": "tts", "text": "Please repeat your last answer."})
    nodes["decision"]["transitions"][-1:-1] = [route("end", guard("route", "end")), route("payment_listen", guard("route", "listen"))]
    nodes["confirmation"]["on_enter"]["text"] = "{{answer_text}} Do you confirm {{validated_amount}} on {{validated_date}}?"
    offer_code = nodes["offer"]["pre_actions"][0]["function"]["parameters"]["properties"]["code"]
    offer_code["default"] += "\nif not vars.get('answer_text'):\n    vars['answer_text'] = 'Here is your payment.'\n"
    security["code_failure_node"] = "safe_retry"
    for node in nodes.values():
        if node.get("node_type") == "code":
            final = node["transitions"][-1]
            # Keep the ordinary route explicitly; reserve unconditional edges for skipped code.
            node["transitions"][-1] = route(final["target_node"], guard("route", "end" if final["target_node"] == "end" else "confirmation" if final["target_node"] == "confirmation" else "unused"))
            node["transitions"].append(route("safe_retry"))
            node["passthrough_default_transition"] = "safe_retry"
    return args


class V7ConversationChecks(unittest.TestCase):
    def test_small_correct_conversation_passes_independent_checks(self):
        report = validate(*conversation_candidate())
        self.assertTrue(report["ok"], report["errors"])

    def test_broken_conversation_mutants_are_rejected(self):
        for fault, check in (
            ("\nif 'minimum payment' in text:\n    vars['question_text'] += ' Can you pay the minimum?'\n", "independent_minimum_answer"),
            ("\nif event == 'question':\n    vars['route'] = 'listen'\n", "independent_support_decline_question"),
            ("\nif event != 'plan' and plan_requested:\n    vars['route'] = 'listen'\n", "independent_mixed_plan"),
            ("\nif event == 'plan' and vars.get('bank_status') == 'verified':\n    vars['exception'] = 'plan'\n    vars['route'] = 'transfer'\n", "independent_plan_negated"),
            ("\nif 'robot' in text:\n    vars['answer_text'] = 'Here is your payment.'\n", "independent_ai_with_current_offer"),
        ):
            with self.subTest(check=check):
                args = conversation_candidate()
                code = args[0]["nodes"]["decision"]["pre_actions"][0]["function"]["parameters"]["properties"]["code"]
                code["default"] += fault
                report = validate(*args)
                self.assertTrue(any(row["name"].startswith(check) and not row["ok"] for row in report["checks"]), report)

    def test_empty_close_and_skipped_code_cannot_speak_templates(self):
        for kind, check in (("close", "independent_success_close_resolves"), ("timeout", "independent_first_code_timeout")):
            args = conversation_candidate()
            if kind == "close":
                args[0]["nodes"]["end"]["terminal"]["function"]["parameters"]["properties"]["spoken_message"]["default"] = "{{terminal_text}} Thank you. Goodbye."
            else:
                args[0]["nodes"]["safe_retry"]["on_enter"]["text"] = "{{question_text}}"
            report = validate(*args)
            self.assertTrue(any(row["name"] == check and not row["ok"] for row in report["checks"]), report)

    def test_delayed_normal_close_is_checked_after_the_success_listener(self):
        args = conversation_candidate()
        node = args[0]["nodes"]["record_result"]
        node["pre_actions"][0]["function"]["parameters"]["properties"]["code"]["default"] += "\nif vars.get('recorded') == 'recorded':\n    vars['question_text'] = 'Your promise is recorded. Can I help further?'\n    vars['route'] = 'listen'\n"
        node["transitions"].insert(0, route("payment_listen", guard("route", "listen")))
        report = validate(*args)
        self.assertTrue(report["ok"], report["errors"])
        args[0]["nodes"]["end"]["terminal"]["function"]["parameters"]["properties"]["spoken_message"]["default"] = "{{terminal_text}} Thank you. Goodbye."
        report = validate(*args)
        self.assertTrue(any(row["name"] == "independent_success_close_resolves" and not row["ok"] for row in report["checks"]), report)

    def test_word_payment_parser_real_raw_paths_and_negative_forms(self):
        args = candidate()
        code = snippet(args[0], "offer")
        base = args[1]["security"]["validation_fixture"]
        for raw, today, expected, deadline in (
            ("the ninth of March", "2027-03-08", "2027-03-09", "2027-03-19"),
            ("Friday the twenty-second", "2028-09-18", "2028-09-22", "2028-09-29"),
            ("January four", "2026-12-31", "2027-01-04", "2027-01-11"),
        ):
            # The small test guard has a fixed acceptance window; vary that test-only window.
            probe = code.replace("'2026-10-14' <= day.isoformat() <= vars.get('deadline', '2026-10-20')", "vars['now'][:10] <= day.isoformat() <= vars['deadline']")
            _run_check(probe, {"vars": dict(base, date=raw, now=today + "T09:00:00", deadline=deadline),
                               "expected": {"validated_date": expected, "route": "confirmation", "record_authorization": ""}})
        for raw in ("the thirty-first of February", "Wednesday the fourteenth after dinner", "Please pay the fourteenth of October", "Thursday the fourteenth"):
            state = _run_check(code, {"vars": dict(base, date=raw), "expected": {}})["vars"]
            self.assertNotEqual(state["route"], "confirmation")
            self.assertEqual(state["record_authorization"], "")
        args[0]["nodes"]["offer"]["pre_actions"][0]["function"]["parameters"]["properties"]["code"]["default"] = code.replace("raw = raw.lower().strip().replace('-', ' ')", "raw = raw.lower().strip()\n        day_names = {}")
        report = validate(*args)
        self.assertTrue(any("payment_month_day_word" in row["name"] and not row["ok"] for row in report["checks"]), report)


if __name__ == "__main__":
    unittest.main()
