"""Conversation regressions for the source compiler; no saved workflow or API calls."""
import copy
import re
import unittest

from builder.compiler import compile_candidate
from builder.validation import _condition, _graph_checks, _run_check
from tests.test_builder_validation import guard, route
from tests.test_focused_conversation import snippet
from tests.test_v7_conversation import conversation_candidate


def interrupted_candidate(shortcut=True):
    workflow, policy, _, checks = conversation_candidate()
    nodes = workflow["nodes"]
    nodes["offer"]["pre_actions"][0]["function"]["parameters"]["properties"]["code"]["default"] += "\nif vars.get('route') == 'confirmation':\n    vars['stage'] = 'confirmation'\n"
    # This describes the observed generated bug, including the missing-edge variant.
    nodes["decision"]["pre_actions"][0]["function"]["parameters"]["properties"]["code"]["default"] += """
if vars.get('bank_status') == 'verified' and vars.get('stage') == 'confirmation':
    vars['persuasion_attempts'] = prior_attempts
    if event in ('yes', 'no', 'offer'):
        vars['approval'] = event
        vars['approval_text'] = speech_text
        vars['approval_amount'] = current_amount
        vars['approval_date'] = current_date
        vars['correction'] = 'yes' if current_amount or current_date else ''
        vars['route'] = 'approval'
    else:
        vars['question_text'] = 'The minimum payment is 25 dollars.'
        vars['route'] = 'listen'
"""
    nodes["approval"]["pre_actions"][0]["function"]["parameters"]["properties"]["code"]["default"] += """
if event == 'question' and not current_amount and not current_date:
    vars['speech_event'] = event
    vars['speech_text'] = current_text
    vars['stage'] = 'confirmation'
    vars['route'] = 'decision'
"""
    nodes["approval"]["transitions"].insert(0, route("decision", guard("route", "decision")))
    if shortcut:
        nodes["decision"]["transitions"].insert(0, route("approval", guard("route", "approval")))
    return {"workflow": workflow, "policy": policy, "checks": checks,
            "uncertainties": [], "summary": "Small interrupted confirmation fixture."}


def advance(workflow, start, state):
    """Stop at a real speech or API boundary, so an early bank write is visible."""
    state = copy.deepcopy(state)
    for _ in range(len(workflow["nodes"]) + 1):
        node = workflow["nodes"][start]
        if node["node_type"] != "code":
            return state, start
        state = _run_check(snippet(workflow, start), {"vars": state, "expected": {}})["vars"]
        start = next((item["target_node"] for item in node["transitions"]
                      if _condition(item["condition"], state)), None)
        if start is None:
            raise AssertionError("Generated route has no outgoing transition")
    raise AssertionError("Action chain failed to return to speech")


def spoken(workflow, target, state):
    return re.sub(r"\{\{([\w.]+)\}\}", lambda match: str(state.get(match.group(1), "")),
                  workflow["nodes"][target]["on_enter"]["text"])


class ConfirmationReturnTests(unittest.TestCase):
    def readback(self, compiled):
        security = compiled["policy"]["security"]
        state, target = advance(compiled["workflow"], security["offer_guard_node"],
                                dict(security["validation_fixture"], write_attempts=0, write_result=""))
        self.assertIn(target, security["confirmation_nodes"])
        self.assertEqual(state["record_authorization"], "")
        return state

    def interrupted(self, compiled):
        state = self.readback(compiled)
        state.update(approval="question", approval_text="What is the minimum payment?",
                     approval_amount="", approval_date="", correction="")
        state, target = advance(compiled["workflow"], "approval", state)
        self.assertEqual(target, "payment_listen")
        self.assertEqual(state["record_authorization"], "")
        return state

    def test_graph_and_deadend_variants_require_a_fresh_readback(self):
        for shortcut in (True, False):
            with self.subTest(shortcut=shortcut):
                original = interrupted_candidate(shortcut)
                before = copy.deepcopy(original)
                compiled, changes = compile_candidate(original)
                self.assertEqual(original, before, "Compilation must not alter its source input")
                self.assertTrue(changes)
                security = compiled["policy"]["security"]
                self.assertEqual(_graph_checks(compiled["workflow"], compiled["workflow"]["nodes"], security), [])
                state = self.interrupted(compiled)
                state.update(speech_event="yes", speech_text="Yes, I confirm.",
                             speech_amount="", speech_date="")
                state, target = advance(compiled["workflow"], "decision", state)
                self.assertIn(target, security["confirmation_nodes"])
                self.assertEqual(state["record_authorization"], "")
                self.assertEqual(state["write_attempts"], 0)
                state.update(security["validation_confirmation_fixture"])
                state, target = advance(compiled["workflow"], "approval", state)
                self.assertIn(target, security["record_nodes"])
                self.assertEqual(state["record_authorization"], "authorized")

    def test_current_correction_replaces_the_old_offer_and_clears_authorization(self):
        compiled, _ = compile_candidate(interrupted_candidate())
        for amount, date, expected_amount, expected_date in (
            ("35", "", 35.0, "2026-10-14"),
            ("", "2026-10-16", 25.0, "2026-10-16"),
            ("40", "2026-10-16", 40.0, "2026-10-16"),
        ):
            with self.subTest(amount=amount, date=date):
                state = self.interrupted(compiled)
                state.update(speech_event="yes", speech_text="Yes, but change the payment.",
                             speech_amount=amount, speech_date=date, record_authorization="authorized",
                             approval="yes", approval_amount="49", approval_date="2026-10-20",
                             approval_text="Old approval", correction="yes")
                old_fingerprint = state["offer_fingerprint"]
                state, target = advance(compiled["workflow"], "decision", state)
                self.assertEqual(target, "confirmation")
                self.assertEqual(state["validated_amount"], expected_amount)
                self.assertEqual(state["validated_date"], expected_date)
                self.assertNotEqual(state["offer_fingerprint"], old_fingerprint)
                self.assertEqual(state["readback_fingerprint"], state["offer_fingerprint"])
                self.assertEqual(state["record_authorization"], "")
                for field in ("speech_event", "speech_text", "speech_amount", "speech_date",
                              "approval", "approval_text", "approval_amount", "approval_date", "correction"):
                    self.assertEqual(state[field], "", field)

    def test_no_after_an_answer_uses_the_sourced_payment_refusal(self):
        compiled, _ = compile_candidate(interrupted_candidate())
        state = self.interrupted(compiled)
        before = state["persuasion_attempts"]
        state.update(speech_event="no", speech_text="No, I cannot pay that.",
                     speech_amount="", speech_date="")
        state, target = advance(compiled["workflow"], "decision", state)
        self.assertEqual(state["stage"], "payment")
        self.assertEqual(state["persuasion_attempts"], before + 1)
        self.assertEqual(target, "payment_listen")
        self.assertEqual(state["record_authorization"], "")

    def test_a_current_question_cannot_be_an_approval_under_a_wrong_yes_label(self):
        compiled, _ = compile_candidate(interrupted_candidate())
        state = self.readback(compiled)
        state.update(approval="yes", approval_text="What is the minimum payment?",
                     approval_amount="", approval_date="", correction="")
        state, target = advance(compiled["workflow"], "approval", state)
        self.assertEqual(target, "payment_listen")
        self.assertEqual(state["record_authorization"], "")
        self.assertEqual(state.get("write_attempts", 0), 0)

    def test_negated_plan_at_readback_never_enters_the_transfer_api(self):
        compiled, _ = compile_candidate(interrupted_candidate())
        state = self.readback(compiled)
        state.update(approval="plan", approval_text="I do not want lower instalments.",
                     approval_amount="", approval_date="", correction="")
        state, target = advance(compiled["workflow"], "approval", state)
        self.assertEqual(compiled["workflow"]["nodes"][target]["node_type"], "conversation")
        self.assertEqual(state["record_authorization"], "")
        self.assertEqual(state.get("transfer_authorization", ""), "")

    def test_positive_plan_request_keeps_its_restructuring_transfer(self):
        compiled, _ = compile_candidate(interrupted_candidate())
        state = self.readback(compiled)
        state.update(approval="plan", approval_text="I cannot pay that amount. I need lower instalments.",
                     approval_amount="", approval_date="", correction="")
        state, target = advance(compiled["workflow"], "approval", state)
        self.assertEqual(target, "transfer")
        self.assertEqual(state["transfer_queue"], "restructuring")
        self.assertEqual(state["record_authorization"], "")

    def test_compiling_a_portable_workflow_twice_keeps_the_same_result(self):
        compiled, _ = compile_candidate(interrupted_candidate())
        repeated, _ = compile_candidate(compiled)
        self.assertEqual(repeated, compiled)

    def test_a_wrong_yes_label_needs_current_explicit_consent(self):
        compiled, _ = compile_candidate(interrupted_candidate())
        for text in ("", "No, I do not confirm.", "Could you change the interest rate?"):
            with self.subTest(text=text):
                state = self.readback(compiled)
                state.update(approval="yes", approval_text=text,
                             approval_amount="", approval_date="", correction="")
                state, target = advance(compiled["workflow"], "approval", state)
                self.assertEqual(compiled["workflow"]["nodes"][target]["node_type"], "conversation")
                self.assertEqual(state["record_authorization"], "")
                self.assertEqual(state.get("write_attempts", 0), 0)

    def test_sourced_ai_answer_is_spoken_with_offer_and_clarification(self):
        original = interrupted_candidate()
        answer = "This is Willow Bank's automated assistant."
        original["policy"]["speech"] = {"ai_answer": answer}
        # The source handles invalid proposals by asking for a new amount/date.
        code = original["workflow"]["nodes"]["offer"]["pre_actions"][0]["function"]["parameters"]["properties"]["code"]
        code["default"] += "\nif vars.get('route') != 'confirmation':\n    vars['route'] = 'listen'\n    vars['question_text'] = 'Please state an exact valid amount and date.'\n"
        original["workflow"]["nodes"]["offer"]["transitions"].insert(0, route("payment_listen", guard("route", "listen")))
        compiled, _ = compile_candidate(original)
        for amount, date, expected in (("35", "2026-10-16", "confirmation"),
                                       ("35", "not a date", "payment_listen"),
                                       ("1", "2026-10-16", "payment_listen")):
            with self.subTest(amount=amount, date=date):
                state = dict(compiled["policy"]["security"]["validation_fixture"],
                             speech_event="yes", speech_text="I can pay that. Am I talking to a robot?",
                             speech_amount=amount, speech_date=date)
                state, target = advance(compiled["workflow"], "decision", state)
                self.assertEqual(target, expected)
                text = spoken(compiled["workflow"], target, state)
                self.assertIn(answer, text)
                self.assertEqual(text.count(answer), 1)
                self.assertEqual(state["record_authorization"], "")
                if expected == "confirmation":
                    self.assertIn("35.0", text)
                    self.assertIn("2026-10-16", text)
                else:
                    self.assertIn("exact valid amount and date", text)

    def test_unknown_entry_and_unguarded_fallback_to_approval_are_rejected(self):
        for fault in ("unknown_source", "default", "unconditional"):
            with self.subTest(fault=fault):
                original = interrupted_candidate()
                nodes = original["workflow"]["nodes"]
                if fault == "unknown_source":
                    nodes["payment_listen"]["transitions"] = [route("approval")]
                elif fault == "default":
                    nodes["decision"]["passthrough_default_transition"] = "approval"
                else:
                    nodes["decision"]["transitions"].insert(0, route("approval"))
                with self.assertRaises(ValueError):
                    compile_candidate(original)

    def test_renamed_policy_variables_keep_the_same_confirmation_boundaries(self):
        original = interrupted_candidate()
        names = {"speech_event": "utterance_kind", "speech_text": "utterance_words",
                 "speech_amount": "utterance_amount", "speech_date": "utterance_date",
                 "approval": "confirm_kind", "approval_text": "confirm_words",
                 "approval_amount": "confirm_amount", "approval_date": "confirm_date",
                 "correction": "confirm_change", "amount": "offer_value", "date": "offer_day",
                 "route": "next_node", "stage": "current_stage",
                 "record_authorization": "bank_write_permit",
                 "offer_fingerprint": "proposal_token", "readback_fingerprint": "spoken_token"}
        security = original["policy"]["security"]
        security["record_authorization_variable"] = names["record_authorization"]
        security["validation_state"] = {role: names.get(value, value) for role, value in security["validation_state"].items()}
        security["trusted_variables"] = [names.get(value, value) for value in security["trusted_variables"]]
        for key, value in security.items():
            if key.startswith("validation_") and key.endswith("fixture"):
                security[key] = {names.get(field, field): value for field, value in value.items()}
        def rename_condition(condition):
            if "variable" in condition:
                condition["variable"] = names.get(condition["variable"], condition["variable"])
                if condition["variable"] == "next_node" and condition.get("operand") == "approval":
                    condition["operand"] = "confirm_kind"
            for child in condition.get("conditions", []):
                rename_condition(child)
        for node in original["workflow"]["nodes"].values():
            for field in node.get("extraction_schema", []):
                field["name"] = names.get(field["name"], field["name"])
            for transition in node["transitions"]:
                rename_condition(transition["condition"])
            if node["node_type"] == "code":
                code = node["pre_actions"][0]["function"]["parameters"]["properties"]["code"]
                code["default"] = re.sub(r"(['\"])([\w.]+)\1",
                    lambda match: match.group(1) + names.get(match.group(2), match.group(2)) + match.group(1), code["default"])
        compiled, _ = compile_candidate(original)
        state = dict(security["validation_fixture"], write_attempts=0, write_result="")
        state, target = advance(compiled["workflow"], "offer", state)
        self.assertEqual(target, "confirmation")
        state.update(confirm_kind="question", confirm_words="What is the minimum payment?",
                     confirm_amount="", confirm_date="", confirm_change="")
        state, target = advance(compiled["workflow"], "approval", state)
        self.assertEqual(target, "payment_listen")
        state.update(utterance_kind="yes", utterance_words="Yes, I confirm.",
                     utterance_amount="35", utterance_date="2026-10-16")
        state, target = advance(compiled["workflow"], "decision", state)
        self.assertEqual(target, "confirmation")
        self.assertEqual(state["validated_amount"], 35.0)
        self.assertEqual(state["validated_date"], "2026-10-16")
        self.assertEqual(state["bank_write_permit"], "")
        state.update(confirm_kind="yes", confirm_words="Yes, I confirm.")
        state, target = advance(compiled["workflow"], "approval", state)
        self.assertEqual(target, "record")
        self.assertEqual(state["bank_write_permit"], "authorized")


if __name__ == "__main__":
    unittest.main()
