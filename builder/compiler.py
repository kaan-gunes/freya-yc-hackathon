"""Source-owned confirmation gates, embedded in the portable workflow."""
import ast
import copy
import inspect
import re


def _kaan_question_kind(text):
    import re
    text = str(text or '').lower().replace('’', "'")
    asked = '?' in text or bool(re.search(r'(?:^|[.!;]\s*)(?:what|when|where|why|how|who|am|are|is|do|does|can|could|would)\b', text))
    if not asked:
        return ''
    if re.search(r'\b(?:are you|is this|is it|am i (?:talking|speaking) (?:to|with))\s+(?:(?:actually|really)\s+)?(?:(?:a|an|the)\s+)?(?:ai|robot|bot|digital assistant|artificial intelligence)\b', text):
        return 'ai'
    if re.search(r'\b(?:scam|fraud|legitimate)\b', text):
        return 'scam'
    return ''


def _kaan_clear_confirmation(text):
    import re
    if '?' in str(text or ''):
        return False
    text = re.sub(r'\s+', ' ', str(text or '').lower().replace('’', "'")).strip(' .,!?;:')
    text = re.sub(r'^(?:no problem|okay|ok)[,.;: ]+', '', text)
    if re.search(r"\b(?:maybe|perhaps|possibly|unsure|uncertain|earlier|previously|already|might|but|i said|if|unless|only|except|wrong|incorrect|later)\b", text):
        return False
    if re.search(r"\b(?:do not|don't|cannot|can't|won't|will not|have not|haven't|not)\s+(?:confirm(?:ed)?|agree(?:d)?|approve(?:d)?|pay|accept|record)\b", text) or re.match(r'^no\b', text):
        return False
    thing = r'(?:payment promise|payment amount|payment|promise|amount|date|offer|terms|details|product)'
    objects = rf'(?:the|this|that|your|these|my) (?:exact |same )?{thing}(?: and (?:the |this |that )?{thing})*'
    assent = rf"(?:yes|i confirm|i agree|confirmed|agreed|that is correct|that's correct|that sounds right|that's right|i (?:confirm|agree)(?: to| with)? {objects})"
    action = rf'(?:please )?(?:go ahead and )?(?:record|save|register) (?:it|this|that|{objects})(?: for (?:that|this|the) amount and date)?'
    polite = r'(?:please|thanks|thank you(?: very much)?|go ahead|no problem)'
    # shortcut: unfamiliar consent wording asks again; expand only with observed safe replies.
    month = r'(?:january|february|march|april|may|june|july|august|september|october|november|december)'
    day = r'[0-9]{1,2}(?:st|nd|rd|th)?'
    year, short_year, day_number = r'[0-9]{4}', r'[0-9]{2,4}', r'[0-9]{1,2}'
    date = rf'(?:today|tomorrow|(?:next |this )?(?:monday|tuesday|wednesday|thursday|friday|saturday|sunday)|{month} {day}(?:,? {year})?|{day} (?:of )?{month}(?:,? {year})?|{year}-{day_number}-{day_number}|{day_number}/{day_number}(?:/{short_year})?)'
    numeric = rf'[0-9]+(?:[.,][0-9]+)?(?: dollars| euros| pounds)? on {date}'
    clause = rf'(?:{assent}|{action}|i can pay {objects}|use {objects}|{polite}|{numeric})'
    return bool(re.fullmatch(rf'{assent}(?:[,.!; ]+{clause})*', text))


def _answers(policy, code):
    answers = {}
    # Older drafts stored these sourced phrases in code, before the speech contract.
    patterns = {'ai': r'\bdigital assistant\b', 'scam': r'\bverify this call\b', 'unknown': r'\bdo not have that information\b'}
    for name, pattern in patterns.items():
        declared = policy.get('speech', {}).get(name + '_answer')
        if isinstance(declared, str) and declared.strip():
            answers[name] = declared
            continue
        values = {node.value.value for node in ast.walk(ast.parse(code))
                  if isinstance(node, ast.Assign) and isinstance(node.value, ast.Constant)
                  and isinstance(node.value.value, str) and re.search(pattern, node.value.value, re.I)}
        if len(values) == 1:
            answers[name] = values.pop()
    return answers


def _tts_variable(node, terminal=False):
    text = (node.get('terminal', {}).get('function', {}).get('parameters', {}).get('properties', {}).get('spoken_message', {}).get('default', '')
            if terminal else node.get('on_enter', {}).get('text', ''))
    match = re.match(r'^\{\{([\w.]+)\}\}', text)
    return match.group(1) if match else None


def _section(code, name, body):
    start, end = f"# BEGIN KAAN {name}\n", f"# END KAAN {name}\n"
    if start in code:
        before, _, tail = code.partition(start)
        _, marker, after = tail.partition(end)
        if not marker or start in after:
            raise ValueError("Invalid compiler section: " + name)
        code = before + after
    elif end in code:
        raise ValueError("Invalid compiler section: " + name)
    return code, start + body + "\n" + end


def _snippet(node):
    actions = node.get("pre_actions", [])
    if len(actions) != 1 or actions[0].get("function", {}).get("handler") != "__function__:code_exec":
        raise ValueError("Compiler needs one code_exec in each declared guard")
    return actions[0]["function"]["parameters"]["properties"]["code"]


def _route_operand(condition, variable):
    while isinstance(condition, dict) and condition.get("logic") in ("and", "or"):
        children = condition.get("conditions", [])
        if len(children) != 1:
            raise ValueError("Confirmation return needs one exact route condition")
        condition = children[0]
    if condition.get("operator") != "equals" or condition.get("variable") != variable or not isinstance(condition.get("operand"), str):
        raise ValueError("Confirmation return needs an exact route operand")
    return condition["operand"]


def _return_operands(code, roles):
    """Find a declared handoff even when its transition was omitted."""
    operands = set()
    for branch in ast.walk(ast.parse(code)):
        if not isinstance(branch, ast.If):
            continue
        assignments = {}
        for statement in branch.body:
            if not isinstance(statement, ast.Assign) or len(statement.targets) != 1:
                continue
            target = statement.targets[0]
            if isinstance(target, ast.Subscript) and isinstance(target.value, ast.Name) and target.value.id == "vars" and isinstance(target.slice, ast.Constant):
                assignments[target.slice.value] = statement.value
        value = assignments.get(roles["route"])
        if {roles["approval_event"], roles["approval_text"]} <= assignments.keys() and isinstance(value, ast.Constant) and isinstance(value.value, str):
            operands.add(value.value)
    return operands


def compile_candidate(candidate):
    """Keep business policy; compile safe return and raw confirmation boundaries."""
    compiled = copy.deepcopy(candidate)
    security = compiled.get("policy", {}).get("security")
    if not isinstance(security, dict):
        # The ordinary validator rejects missing policy; it remains the final gate.
        return compiled, []
    workflow, roles = compiled["workflow"], security["validation_state"]
    nodes = {**workflow.get("nodes", {}), **workflow.get("global_nodes", {})}
    decision, approval, offer = (security[key] for key in ("decision_node", "approval_guard_node", "offer_guard_node"))
    events, routes = security["validation_events"], security["validation_routes"]
    route = roles["route"]
    authorization = security.get("record_authorization_variable", "record_authorization")
    allowed = {*security["confirmation_nodes"], security["record_result_node"]}
    declared = set(security.get("confirmation_return_routes", []))
    aliases = _return_operands(_snippet(nodes[decision])["default"], roles)
    if any(not isinstance(value, str) or not value for value in declared):
        raise ValueError("Invalid confirmation return operands")
    changes = []
    for name, node in nodes.items():
        for key in ("passthrough_default_transition", "max_turn_transition"):
            if node.get(key) == approval and name not in allowed:
                raise ValueError(f"{name}: fallback cannot enter approval")
        for transition in node.get("transitions", []):
            if transition.get("target_node") != approval or name in allowed:
                continue
            if name != decision:
                raise ValueError(f"{name}: only readback or guarded record retry may enter approval")
            aliases.add(_route_operand(transition["condition"], route))
            transition["target_node"] = offer
            changes.append(f"{name}: confirmation return now reaches offer guard and fresh readback")

    if declared - aliases or aliases & set(routes.values()):
        raise ValueError("Confirmation return operands must match the code and remain separate from action routes")

    if aliases:
        security["confirmation_return_routes"] = sorted(aliases)
        for alias in sorted(aliases):
            matches = [row for row in nodes[decision]["transitions"] if row.get("target_node") == offer and row.get("condition") == {"logic": "or", "conditions": [{"variable": route, "operator": "equals", "operand": alias}]}]
            if not matches:
                nodes[decision]["transitions"].insert(-1, {"target_node": offer,
                    "description": "Revalidate the resumed offer and speak a fresh readback.",
                    "condition": {"logic": "or", "conditions": [{"variable": route, "operator": "equals", "operand": alias}]}})
        code = _snippet(nodes[decision])
        capture = "\n".join(f"_kaan_{name} = str(vars.get({roles[key]!r}) or '')" for name, key in (
            ("event", "decision_event"), ("text", "speech_text"), ("amount", "decision_amount"), ("date", "decision_date")))
        original, prefix = _section(code["default"], "CURRENT REPLY", capture)
        # Fresh approval copies are consumed by the offer guard, never by approval.
        clear = "\n".join(f"    vars[{roles[key]!r}] = ''" for key in (
            "offer_fingerprint", "readback_fingerprint", "write_result"))
        body = f"""if vars.get({route!r}) in {sorted(aliases)!r}:
{clear}
    vars[{authorization!r}] = ''
    if _kaan_amount or _kaan_date:
        if _kaan_amount:
            vars[{roles['proposed_amount']!r}] = _kaan_amount
        if _kaan_date:
            vars[{roles['proposed_date']!r}] = _kaan_date
    elif _kaan_event == {events['no']!r}:
        vars[{roles['decision_event']!r}] = {events['no']!r}
        vars[{roles['speech_text']!r}] = _kaan_text
        vars[{roles['stage']!r}] = 'payment'
        vars[{route!r}] = '__kaan_confirmation_declined'
"""
        original, suffix = _section(original, "CONFIRMATION RETURN", body.rstrip())
        code["default"] = prefix + original.rstrip() + "\n" + suffix
        decline = {"target_node": decision, "description": "Apply the sourced refusal policy to a declined resumed confirmation.",
                   "condition": {"logic": "or", "conditions": [{"variable": route, "operator": "equals", "operand": "__kaan_confirmation_declined"}]}}
        transitions = nodes[decision]["transitions"]
        if decline not in transitions:
            transitions.insert(0, decline)

    # A model event label cannot turn a current question or plan rejection into consent.
    code = _snippet(nodes[approval])
    event, text = roles["approval_event"], roles["approval_text"]
    body = f"""import re
_kaan_confirmation_text = str(vars.get({text!r}) or '').lower().replace('’', "'")
_kaan_question = bool(_kaan_confirmation_text.strip()) and ('?' in _kaan_confirmation_text or bool(re.search(r'(?:^|[.!;]\\s*)(?:what|when|where|why|how|who|can|could|would|will|am|are|is|do|does)\\b', _kaan_confirmation_text)))
_kaan_plan_declined = bool(re.search(r"\\b(?:(?:do not|don't|never)\\s+(?:want|need|request)\\s+(?:(?:a|any|the|new|another)\\s+)*(?:payment\\s+plan|plan|(?:lower|reduced)\\s+instalments)|no\\s+(?:(?:new|another)\\s+)?(?:payment\\s+plan|plan|(?:lower|reduced)\\s+instalments))\\b", _kaan_confirmation_text))
_kaan_approval_stage = vars.get({roles['stage']!r})
_kaan_approval_amount = str(vars.get({roles['approval_amount']!r}) or '')
_kaan_approval_date = str(vars.get({roles['approval_date']!r}) or '')
if vars.get({event!r}) == {events['plan']!r} and _kaan_plan_declined:
    vars[{event!r}] = {events['question']!r} if _kaan_question else ''
if _kaan_question and vars.get({event!r}) in ['', {events['yes']!r}, {events['no']!r}]:
    vars[{event!r}] = {events['question']!r}
elif vars.get({event!r}) == {events['yes']!r}:
    if re.match(r'^\\s*no\\b(?!\\s+problem\\b)', _kaan_confirmation_text) or re.search(r"\\b(?:do not|don't|cannot|can't)\\s+(?:confirm|agree|approve)\\b", _kaan_confirmation_text):
        vars[{event!r}] = {events['no']!r}
    elif not _kaan_clear_confirmation(_kaan_confirmation_text):
        vars[{event!r}] = {events['question']!r} if _kaan_approval_amount or _kaan_approval_date or vars.get({roles['correction']!r}) == 'yes' else ''
"""
    original, prefix = _section(code["default"], "CONFIRMATION INPUT", inspect.getsource(_kaan_clear_confirmation) + '\n' + body.rstrip())
    body = f"""if _kaan_plan_declined and vars.get({roles['exception']!r}) == {events['plan']!r}:
    vars[{authorization!r}] = ''
    vars[{roles['exception']!r}] = ''
    vars[{roles['stage']!r}] = _kaan_approval_stage
    vars[{roles['decision_event']!r}] = ''
    vars[{roles['speech_text']!r}] = _kaan_confirmation_text
    vars[{roles['decision_amount']!r}] = _kaan_approval_amount
    vars[{roles['decision_date']!r}] = _kaan_approval_date
    vars[{route!r}] = '__kaan_confirmation_rejected_plan'
"""
    original, suffix = _section(original, "CONFIRMATION EXCEPTIONS", body.rstrip())
    code["default"] = prefix + original.rstrip() + "\n" + suffix
    transition = {"target_node": decision, "description": "A declined plan is handled in its current stage.",
                  "condition": {"logic": "or", "conditions": [{"variable": route, "operator": "equals", "operand": "__kaan_confirmation_rejected_plan"}]}}
    if transition not in nodes[approval]["transitions"]:
        nodes[approval]["transitions"].insert(0, transition)
    changes.append("approval: current question and plan rejection are checked before event consent")

    code = _snippet(nodes[offer])
    body = '\n'.join(f"vars[{roles[key]!r}] = ''" for key in (
        'approval_event', 'approval_text', 'approval_amount', 'approval_date', 'correction'))
    original, prefix = _section(code['default'], 'FRESH READBACK', body)
    code['default'] = prefix + original

    answers = _answers(compiled['policy'], _snippet(nodes[decision])['default'])
    question_fields = {_tts_variable(nodes[row['target_node']]) for row in nodes[decision]['transitions']
                       if nodes[row['target_node']]['node_type'] == 'conversation'
                       and row['target_node'] not in security['confirmation_nodes']}
    question_fields.discard(None)
    if answers and len(question_fields) == 1:
        question_field = question_fields.pop()
        readback_fields = {_tts_variable(nodes[name]) for name in security['confirmation_nodes']}
        readback_fields.discard(None)
        terminal_fields = {_tts_variable(nodes[name], True) for name in security['close_nodes'] if nodes[name]['node_type'] == 'end_call'}
        terminal_fields.discard(None)
        code = _snippet(nodes[decision])
        body = 'import re\n' + inspect.getsource(_kaan_question_kind) + f"\n_kaan_question_answer = {answers!r}.get(_kaan_question_kind(vars.get({roles['speech_text']!r})), '')"
        original, prefix = _section(code['default'], 'CURRENT QUESTION', body)
        body = f"""if _kaan_question_answer:
    if vars.get({route!r}) in {sorted(aliases | {routes['offer'], routes['confirmation']})!r}:
        vars[{question_field!r}] = _kaan_question_answer
    elif vars.get({route!r}) == {routes.get('listen', 'listen')!r}:
        _kaan_question_speech = str(vars.get({question_field!r}) or '')
        if _kaan_question_speech.startswith({answers.get('unknown', '')!r}) and {bool(answers.get('unknown'))!r}:
            _kaan_question_speech = _kaan_question_speech[len({answers.get('unknown', '')!r}):].lstrip()
        if _kaan_question_answer not in _kaan_question_speech:
            vars[{question_field!r}] = (_kaan_question_answer + ' ' + _kaan_question_speech).strip()
"""
        if len(terminal_fields) == 1:
            terminal_field = next(iter(terminal_fields))
            body += f"""    elif vars.get({route!r}) == {routes['end']!r} and _kaan_question_answer not in str(vars.get({terminal_field!r}) or ''):
        vars[{terminal_field!r}] = (_kaan_question_answer + ' ' + str(vars.get({terminal_field!r}) or '')).strip()
"""
        original, suffix = _section(original, 'QUESTION ANSWER', body.rstrip())
        code['default'] = prefix + original.rstrip() + '\n' + suffix
        code = _snippet(nodes[offer])
        body = f"_kaan_offer_answer = next((answer for answer in {list(answers.values())!r} if str(vars.get({question_field!r}) or '').startswith(answer)), '')"
        original, prefix = _section(code['default'], 'OFFER ANSWER INPUT', body)
        body = f"""if _kaan_offer_answer:
    if vars.get({route!r}) == {routes.get('listen', 'listen')!r} and _kaan_offer_answer not in str(vars.get({question_field!r}) or ''):
        vars[{question_field!r}] = (_kaan_offer_answer + ' ' + str(vars.get({question_field!r}) or '')).strip()
"""
        if len(readback_fields) == 1:
            readback_field = next(iter(readback_fields))
            body += f"""    elif vars.get({route!r}) == {routes['confirmation']!r} and _kaan_offer_answer not in str(vars.get({readback_field!r}) or ''):
        vars[{readback_field!r}] = (_kaan_offer_answer + ' ' + str(vars.get({readback_field!r}) or '')).strip()
"""
        if len(terminal_fields) == 1:
            body += f"""    elif vars.get({route!r}) == {routes['end']!r} and _kaan_offer_answer not in str(vars.get({terminal_field!r}) or ''):
        vars[{terminal_field!r}] = (_kaan_offer_answer + ' ' + str(vars.get({terminal_field!r}) or '')).strip()
"""
        original, suffix = _section(original, 'OFFER ANSWER OUTPUT', body.rstrip())
        code['default'] = prefix + original.rstrip() + '\n' + suffix
        changes.append('current AI/scam answers survive offer validation on readback, clarification and close speech')
    return compiled, changes
