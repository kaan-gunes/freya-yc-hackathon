"""Source-owned confirmation gates, embedded in the portable workflow."""
import ast
import copy
import inspect
import re

from builder.language import normalize_amount_input, normalize_date_input


def _kaan_question_kind(text):
    import re
    text = str(text or '').lower().replace('’', "'").replace('i̇', 'i').replace('â', 'a').translate(str.maketrans('çğıöşü', 'cgiosu'))
    asked = '?' in text or bool(re.search(r'(?:^|[.!;]\s*)(?:what|when|where|why|how|who|am|are|is|do|does|can|could|would|ne|neden|nasil|kim)\b|\b(?:mi|misiniz|musun|miyim)\b', text))
    if not asked:
        return ''
    if re.search(r'\b(?:are you|is this|is it|am i (?:talking|speaking) (?:to|with))\s+(?:(?:actually|really)\s+)?(?:(?:a|an|the)\s+)?(?:ai|robot|bot|digital assistant|artificial intelligence)\b', text):
        return 'ai'
    if re.search(r'\b(?:scam|fraud|legitimate)\b', text):
        return 'scam'
    if re.search(r'\b(?:(?:sen|siz|bu) (?:bir )?(?:robot|bot|yapay zeka|dijital asistan)|(?:yapay zeka|robot|bot) (?:ile )?mi konusuyorum)\b', text):
        return 'ai'
    if re.search(r'\b(?:dolandiricilik|dolandirici|sahte arama|guvenilir)\b', text):
        return 'scam'
    return ''


def _kaan_clear_confirmation(text):
    import re
    if '?' in str(text or ''):
        return False
    text = re.sub(r'\s+', ' ', str(text or '').lower().replace('’', "'").replace('i̇', 'i').translate(str.maketrans('çğıöşü', 'cgiosu'))).strip(' .,!?;:')
    text = re.sub(r'^(?:no problem|okay|ok)[,.;: ]+', '', text)
    if re.search(r"\b(?:maybe|perhaps|possibly|unsure|uncertain|earlier|previously|already|might|but|i said|if|unless|only|except|wrong|incorrect|later)\b", text):
        return False
    if re.search(r"\b(?:do not|don't|cannot|can't|won't|will not|have not|haven't|not)\s+(?:confirm(?:ed)?|agree(?:d)?|approve(?:d)?|pay|accept|record)\b", text) or re.match(r'^no\b', text):
        return False
    if re.search(r'\b(?:hayir|ama|fakat|ancak|yalniz|sadece|belki|eger|sonra|once|onceden|demistim|degil|yanlis|onaylamiyorum|onaylamadim|odemem|odeyemem|istemiyorum)\b', text):
        return False
    if bool(re.search(r'\bamount\b', text)) != bool(re.search(r'\bdate\b', text)) or bool(re.search(r'\btutari\b', text)) != bool(re.search(r'\btarihi\b', text)):
        return False
    tr_thing = r'(?:tutari|tarihi|odeme sozunu|odemeyi|teklifi|kosullari|bilgileri)'
    tr_objects = rf'(?:(?:bu|su|o|ayni) )?{tr_thing}(?: ve (?:bu |su |o )?{tr_thing})*'
    tr_assent = rf'(?:evet|tamam|onayliyorum|kabul ediyorum|dogru|{tr_objects} (?:onayliyorum|kabul ediyorum))'
    tr_month = r'(?:ocak|subat|mart|nisan|mayis|haziran|temmuz|agustos|eylul|ekim|kasim|aralik)'
    tr_day, tr_year = r'(?:[0-9]{1,2}|bir|iki|uc|dort|bes|alti|yedi|sekiz|dokuz|on(?: (?:bir|iki|uc|dort|bes|alti|yedi|sekiz|dokuz))?|yirmi(?: (?:bir|iki|uc|dort|bes|alti|yedi|sekiz|dokuz))?|otuz(?: bir)?)', r'[0-9]{4}'
    tr_date = rf'(?:bugun|yarin|(?:bu |gelecek |onumuzdeki )?(?:pazartesi|sali|carsamba|persembe|cuma|cumartesi|pazar)|{tr_day} {tr_month}(?: {tr_year})?|{tr_year}-{tr_day}-{tr_day}|{tr_day}[/.]{tr_day}(?:[/.]{tr_year})?)(?:\x27?(?:de|da|te|ta)| tarihinde| gunu)?'
    tr_money = r'(?:[0-9]+(?:[.,][0-9]+)?|[0-9]{1,3}(?:\.[0-9]{3})+,[0-9]{1,2})'
    tr_numeric = rf'{tr_money}(?: (?:tl|lira|turk lirasi)(?:\x27?(?:yi|i))?)?[ ,]+{tr_date}(?: (?:odeyecegim|odeyebilirim))?'
    tr_action = rf'(?:lutfen )?(?:kaydedin|kaydedebilirsiniz|{tr_objects} kaydedin)'
    tr_clause = rf'(?:{tr_assent}|{tr_action}|{tr_numeric}|tesekkurler|tesekkur ederim|lutfen|odeyecegim)'
    if re.fullmatch(rf'{tr_assent}(?:[,.!; ]+{tr_clause})*', text):
        return True
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


def _service_value(raw, path):
    import json
    value = raw
    for part in path.split('.') if path else []:
        if isinstance(value, str):
            try:
                value = json.loads(value)
            except Exception:
                return None
        if not isinstance(value, dict) or part not in value:
            return None
        value = value[part]
    return value


def _service_request_text(text):
    import re
    text = str(text or '').lower().replace('i̇', 'i').translate(str.maketrans('çğıöşü', 'cgiosu')).strip()
    return bool(text) and not bool(re.search(r"\b(?:no|don't|do not|not now|maybe|perhaps|if|unless|hayir|istemiyorum|onaylamiyorum|gondermeyin|degistirmeyin|belki|eger|vazgectim)\b", text))


def _service_matches_schema(value, schema):
    if value is None and schema.get('nullable'):
        return True
    if not all(_service_matches_schema(value, choice) for choice in schema.get('allOf', [])):
        return False
    for key in ('anyOf', 'oneOf'):
        if schema.get(key) and not any(_service_matches_schema(value, choice) for choice in schema[key]):
            return False
    actual = ('boolean' if isinstance(value, bool) else 'object' if isinstance(value, dict) else 'array' if isinstance(value, list)
              else 'string' if isinstance(value, str) else 'integer' if isinstance(value, int) else 'number' if isinstance(value, float) else 'null')
    allowed = schema.get('type')
    if allowed and actual != allowed and not (actual == 'integer' and allowed == 'number'):
        return False
    if 'enum' in schema and not any(value == expected and isinstance(value, bool) == isinstance(expected, bool) for expected in schema['enum']):
        return False
    if isinstance(value, dict):
        if not all(field in value for field in schema.get('required', [])):
            return False
        for field, child in schema.get('properties', {}).items():
            if field in value and not _service_matches_schema(value[field], child):
                return False
    if isinstance(value, list):
        if not all(_service_matches_schema(item, schema.get('items', {})) for item in value):
            return False
    if actual in ('integer', 'number'):
        if not -float('inf') < value < float('inf'):
            return False
        if 'minimum' in schema and value < schema['minimum'] or 'maximum' in schema and value > schema['maximum']:
            return False
    return True


def _service_schema_definition(value, document, seen=()):
    if isinstance(value, dict) and '$ref' in value:
        from builder.validation import _resolve
        ref = value['$ref']
        if ref in seen:
            raise ValueError('Recursive service response schemas are unsupported')
        value = _resolve(value, document, seen)
        seen = (*seen, ref)
    if isinstance(value, dict):
        return {key: _service_schema_definition(child, document, seen) for key, child in value.items() if key != 'description'}
    if isinstance(value, list):
        return [_service_schema_definition(child, document, seen) for child in value]
    return value


def _service_clear_confirmation(text, phrases):
    import re
    def fold(value):
        return re.sub(r'\s+', ' ', str(value or '').lower().replace('i̇', 'i').translate(str.maketrans('çğıöşü', 'cgiosu'))).strip(' .,!?;:')
    raw = str(text or '')
    text = fold(raw)
    if '?' in raw or re.search(r"\b(?:no|not|don't|do not|cannot|can't|maybe|perhaps|if|unless|but|earlier|previously|already|hayir|degil|istemiyorum|onaylamiyorum|belki|eger|ama|fakat|ancak|once|onceden|demistim|yanlis|vazgectim)\b", text):
        return False
    assent = r'(?:yes|i confirm|i agree|confirmed|agreed|evet|tamam|onayliyorum|kabul ediyorum|dogru)'
    actions = '|'.join(re.escape(fold(phrase)) for phrase in phrases if fold(phrase))
    positive = assent + ('|(?:' + actions + ')' if actions else '')
    polite = r'(?:please|thanks|thank you|lutfen|tesekkurler|tesekkur ederim)'
    return bool(re.fullmatch('(?:' + positive + r')(?:[ ,.!;:]+(?:' + positive + '|' + polite + '))*', text))


def _compile_service(compiled, openapi=None):
    security = compiled['policy']['security']
    workflow = compiled['workflow']
    nodes = {**workflow.get('nodes', {}), **workflow.get('global_nodes', {})}
    operations = {}
    if openapi:
        from builder.validation import _resolve
        for path, item in openapi['paths'].items():
            for method, operation in _resolve(item, openapi).items():
                if method.lower() in ('get', 'post', 'put', 'patch', 'delete'):
                    operation = _resolve(operation, openapi)
                    operations[operation.get('operationId', path.strip('/').replace('/', '_'))] = operation
    changes = []
    for name, gate in security.get('action_guards', {}).items():
        code = _snippet(nodes[gate['node']])
        authorization = gate['variable']
        consent = gate.get('consent_required', True)
        text_field, event_field = gate.get('text_field'), gate.get('event_field')
        prefix = f"vars[{authorization!r}] = ''"
        if consent:
            prefix += f"\n_service_current_text = str(vars.get({text_field!r}) or '')\n_service_current_event = str(vars.get({event_field!r}) or '')"
            prefix += f"\n_service_changed_fields = {bool(gate.get('value_fields'))!r} and any(str(vars.get(name) or '').strip() for name in {gate.get('value_fields', [])!r})"
        original, head = _section(code['default'], 'SERVICE INPUT ' + name, prefix)
        suffix = ''
        if consent:
            helpers = inspect.getsource(_service_clear_confirmation) if gate.get('confirmation_required') else inspect.getsource(_service_request_text)
            call = f"_service_clear_confirmation(_service_current_text, {gate.get('consent_phrases', [])!r})" if gate.get('confirmation_required') else '_service_request_text(_service_current_text)'
            suffix = helpers + f"\nif not _service_current_event or not {call}" + (' or _service_changed_fields' if gate.get('confirmation_required') else '') + f":\n    vars[{authorization!r}] = ''"
            for field in sorted({text_field, event_field, *gate.get('value_fields', [])}):
                suffix += f"\nvars[{field!r}] = ''"
        if gate.get('confirmation_required'):
            fingerprint, readback = gate['fingerprint_variable'], gate['readback_fingerprint_variable']
            suffix += f"\nif not vars.get({fingerprint!r}) or vars.get({fingerprint!r}) != vars.get({readback!r}):\n    vars[{authorization!r}] = ''"
        original, tail = _section(original, 'SERVICE OUTPUT ' + name, suffix)
        code['default'] = head + original.rstrip() + '\n' + tail
        changes.append(name + ': current consent and authorization are consumed before the guarded action')

    for api_node, result in security.get('api_results', {}).items():
        prefix = result.get('response_prefix', api_node + '_response')
        success = result['success_variable']
        fields = {prefix, prefix + '.status', prefix + '.status_code', prefix + '.data'}
        fields.update(prefix + '.' + path for path in result.get('required_response_fields', []))
        fields.update(prefix + '.' + error['path'] for error in result.get('error_outcomes', []))
        business = result.get('business_success')
        if business:
            fields.add(prefix + '.' + business['path'])
        entry = _snippet(nodes[result['entry_node']])
        reset = '\n'.join(f"vars[{field!r}] = ''" for field in sorted(fields | {success}))
        original, head = _section(entry['default'], 'SERVICE RESET ' + api_node, reset)
        entry['default'] = head + original
        code = _snippet(nodes[result['result_node']])
        snapshot_paths = sorted({*result.get('required_response_fields', []),
                                 *([business['path']] if business else []),
                                 *(error['path'] for error in result.get('error_outcomes', []))})
        snapshot = (f"import copy\nvars[{success!r}] = ''\n"
                    f"_service_current_status = str(vars.get({(prefix + '.status_code')!r}) or '')\n"
                    f"_service_current_body = copy.deepcopy(vars.get({(prefix + '.data')!r}))\n"
                    f"_service_current_values = " + '{path: copy.deepcopy(vars.get(' + repr(prefix + '.') + ' + path)) for path in ' + repr(snapshot_paths) + '}')
        original, head = _section(code['default'], 'SERVICE RESULT INPUT ' + api_node, snapshot)
        body = inspect.getsource(_service_value)
        body += f"\n_service_status = _service_current_status\n_service_body = _service_current_body\n_service_result_valid = _service_status in {[str(status) for status in result['success_statuses']]!r}"
        operation_name = nodes[api_node]['pre_actions'][0]['function']['name']
        operation = operations.get(operation_name)
        if operation:
            import json
            schemas = {}
            for status in result['success_statuses']:
                response = _resolve(operation['responses'].get(str(status), {}), openapi)
                schemas[str(status)] = _service_schema_definition(response.get('content', {}).get('application/json', {}).get('schema', {}), openapi)
            encoded = repr(json.dumps(schemas)).replace('{', r'\x7b').replace('}', r'\x7d')
            body += '\n' + inspect.getsource(_service_matches_schema)
            body += (f"\nimport json\n_service_schemas = json.loads({encoded})"
                     "\n_service_body_now = _service_body"
                     "\nif isinstance(_service_body_now, str):\n    try:\n        _service_body_now = json.loads(_service_body_now)\n    except Exception:\n        _service_body_now = None"
                     "\nif not _service_matches_schema(_service_body_now, _service_schemas.get(_service_status, {})):\n    _service_result_valid = False")
            marker = operation.get('x-business-success')
            if marker:
                body += (f"\n_service_source_flag = _service_value(_service_body, {marker['path']!r})"
                         f"\nif _service_source_flag != {marker['operand']!r} or isinstance(_service_source_flag, bool) != {isinstance(marker['operand'], bool)!r}:\n    _service_result_valid = False")
        for path in result.get('required_response_fields', []):
            field = prefix + '.' + path
            relative = path[5:] if path.startswith('data.') else path
            body += f"\n_service_value_now = _service_current_values.get({path!r})\nif _service_value_now is None or _service_value_now == '':\n    _service_value_now = _service_value(_service_body, {relative!r})\nif _service_value_now is None:\n    _service_result_valid = False"
        if business:
            path, expected = business['path'], business['operand']
            field, relative = prefix + '.' + path, path[5:] if path.startswith('data.') else path
            body += f"\n_service_value_now = _service_current_values.get({path!r})\nif _service_value_now is None or _service_value_now == '':\n    _service_value_now = _service_value(_service_body, {relative!r})\nif _service_value_now != {expected!r} or isinstance(_service_value_now, bool) != {isinstance(expected, bool)!r}:\n    _service_result_valid = False"
        body += f"\n_service_failure_route = {result['failure_route']!r}\n_service_failure_text = {result['failure_text']!r}"
        for error in result.get('error_outcomes', []):
            path = error['path']
            relative = path[5:] if path.startswith('data.') else path
            body += (f"\n_service_error_value = _service_current_values.get({path!r})"
                     f"\nif _service_error_value is None or _service_error_value == '':\n    _service_error_value = _service_value(_service_body, {relative!r})"
                     f"\nif _service_status == {str(error['status'])!r} and _service_error_value == {error['operand']!r}:"
                     f"\n    _service_failure_route = {error['route']!r}\n    _service_failure_text = {error['speech']!r}")
        body += (f"\nif not _service_result_valid:\n    vars[{success!r}] = ''"
                 f"\n    vars[{result['route_variable']!r}] = _service_failure_route"
                 f"\n    vars[{result['speech_variable']!r}] = _service_failure_text")
        original, tail = _section(original, 'SERVICE RESULT OUTPUT ' + api_node, body)
        code['default'] = head + original.rstrip() + '\n' + tail
        changes.append(api_node + ': response evidence is reset before entry and success requires the current sourced response')

    language = security.get('language_input', {})
    date_fields, amount_fields = language.get('date_fields', {}), language.get('amount_fields', {})
    if not isinstance(date_fields, dict) or not isinstance(amount_fields, dict):
        raise ValueError('Service language fields must map code nodes to raw input field lists')
    helpers = inspect.getsource(normalize_amount_input) + '\n' + inspect.getsource(normalize_date_input)
    for node_id in sorted(set(date_fields) | set(amount_fields)):
        body = helpers
        for field in date_fields.get(node_id, []):
            body += f"\n_service_date = normalize_date_input(vars.get({field!r}), vars.get({language['now_variable']!r}))\nif _service_date:\n    vars[{field!r}] = _service_date"
        for field in amount_fields.get(node_id, []):
            body += f"\nvars[{field!r}] = normalize_amount_input(vars.get({field!r}))"
        code = _snippet(nodes[node_id])
        original, head = _section(code['default'], 'SERVICE LANGUAGE INPUT', body)
        code['default'] = head + original
    return compiled, changes


def compile_candidate(candidate, openapi=None):
    """Keep business policy; compile safe return and raw confirmation boundaries."""
    compiled = copy.deepcopy(candidate)
    if compiled.get('policy', {}).get('workflow_kind') == 'service':
        return _compile_service(compiled, openapi)
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
_kaan_confirmation_text = str(vars.get({text!r}) or '').lower().replace('’', "'").replace('i̇', 'i').translate(str.maketrans('çğıöşü', 'cgiosu'))
_kaan_question = bool(_kaan_confirmation_text.strip()) and ('?' in _kaan_confirmation_text or bool(re.search(r'(?:^|[.!;]\\s*)(?:what|when|where|why|how|who|can|could|would|will|am|are|is|do|does|ne|neden|nasil|kim)\\b|\\b(?:mi|misiniz|musun|miyim)\\b', _kaan_confirmation_text)))
_kaan_plan_declined = bool(re.search(r"\\b(?:(?:do not|don't|never)\\s+(?:want|need|request)\\s+(?:(?:a|any|the|new|another)\\s+)*(?:payment\\s+plan|plan|(?:lower|reduced)\\s+instalments)|no\\s+(?:(?:new|another)\\s+)?(?:payment\\s+plan|plan|(?:lower|reduced)\\s+instalments)|(?:yeni )?odeme plani istemiyorum|taksit(?:leri)? (?:dusurmek|azaltmak) istemiyorum)\\b", _kaan_confirmation_text))
_kaan_approval_stage = vars.get({roles['stage']!r})
_kaan_approval_amount = str(vars.get({roles['approval_amount']!r}) or '')
_kaan_approval_date = str(vars.get({roles['approval_date']!r}) or '')
if vars.get({event!r}) == {events['plan']!r} and _kaan_plan_declined:
    vars[{event!r}] = {events['question']!r} if _kaan_question else ''
if _kaan_question and vars.get({event!r}) in ['', {events['yes']!r}, {events['no']!r}]:
    vars[{event!r}] = {events['question']!r}
elif vars.get({event!r}) == {events['yes']!r}:
    if re.match(r'^\\s*(?:no\\b(?!\\s+problem\\b)|hayir\\b)', _kaan_confirmation_text) or re.search(r"\\b(?:(?:do not|don't|cannot|can't)\\s+(?:confirm|agree|approve)|onaylamiyorum|kabul etmiyorum)\\b", _kaan_confirmation_text):
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
    question_field = next(iter(question_fields)) if len(question_fields) == 1 else None
    if question_field:
        # Missing extraction is not evidence of refusal; keep the current proposal.
        conversation = security.get('validation_conversation', {})
        payment_stage = conversation.get('minimum_fixture', {}).get(roles['stage'], 'payment')
        listener_routes = {_route_operand(row['condition'], route) for row in nodes[decision]['transitions']
                           if nodes[row['target_node']]['node_type'] == 'conversation'
                           and row['target_node'] not in security['confirmation_nodes']
                           and _tts_variable(nodes[row['target_node']]) == question_field}
        if len(listener_routes) != 1:
            raise ValueError('Missing payment text needs one declared listener route')
        listener_route = next(iter(listener_routes))
        preserved = {roles[key] for key in ('proposed_amount', 'proposed_date', 'persuasion_attempts',
                     'offer_fingerprint', 'readback_fingerprint', 'write_result', 'stage')}
        preserved.update(conversation.get('state', {}).values())
        code = _snippet(nodes[decision])
        body = f"""_kaan_missing_payment_text = vars.get({roles['stage']!r}) == {payment_stage!r} and vars.get({security['bank_verification_variable']!r}) == {security['bank_gate']['operand']!r} and vars.get({roles['decision_event']!r}) == {events.get('non_answer', 'non_answer')!r} and not str(vars.get({roles['speech_text']!r}) or '').strip() and not vars.get({roles['decision_amount']!r}) and not vars.get({roles['decision_date']!r})
_kaan_missing_payment_state = vars.copy() if _kaan_missing_payment_text else {{}}
if _kaan_missing_payment_text:
    vars[{roles['decision_event']!r}] = ''
    vars[{roles['speech_text']!r}] = ''
"""
        original, prefix = _section(code['default'], 'MISSING PAYMENT INPUT', body.rstrip())
        restore = '\n'.join(f"    if {name!r} in _kaan_missing_payment_state:\n        vars[{name!r}] = _kaan_missing_payment_state[{name!r}]" for name in sorted(preserved))
        body = f"""if _kaan_missing_payment_text:
{restore}
    vars[{authorization!r}] = ''
    vars[{roles['decision_event']!r}] = ''
    vars[{roles['speech_text']!r}] = ''
    vars[{question_field!r}] = {compiled['policy'].get('speech', {}).get('repeat_answer', 'Please repeat your answer.')!r}
    vars[{route!r}] = {listener_route!r}
"""
        original, suffix = _section(original, 'MISSING PAYMENT OUTPUT', body.rstrip())
        code['default'] = prefix + original.rstrip() + '\n' + suffix
        changes.append('decision: missing current non-answer text asks again without changing the proposal or persuasion count')
    if answers and question_field:
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
    language = security.get('language_input', {})
    if not isinstance(language, dict):
        raise ValueError('language_input must declare variable bindings')
    anchor_field = language.get('now_variable', 'now')
    deadline_field = language.get('deadline_variable')
    identity_fields = language.get('identity_date_fields', [roles['identity_answer']] if any(item.get('kind') == 'date' for item in security.get('identity_questions', [])) else [])
    identity_stage = security.get('validation_identity_answer_fixture', {}).get(roles['stage'], 'identity')
    if not isinstance(anchor_field, str) or not anchor_field or (deadline_field is not None and (not isinstance(deadline_field, str) or not deadline_field)) or not isinstance(identity_fields, list) or any(not isinstance(name, str) or not name for name in identity_fields):
        raise ValueError('language_input needs literal input variable names')
    helpers = inspect.getsource(normalize_amount_input) + '\n' + inspect.getsource(normalize_date_input)
    for node_id, date_field, amount_field in ((decision, roles['decision_date'], roles['decision_amount']),
                                             (offer, roles['proposed_date'], roles['proposed_amount']),
                                             (approval, roles['approval_date'], roles['approval_amount'])):
        end = f'vars.get({deadline_field!r})' if deadline_field else "''"
        identity = f'vars.get({roles["stage"]!r}) == {identity_stage!r}' if node_id == decision else 'False'
        body = helpers + f"\n_kaan_normalized_date = normalize_date_input(vars.get({date_field!r}), vars.get({anchor_field!r}), {end}, {identity})\nif _kaan_normalized_date:\n    vars[{date_field!r}] = _kaan_normalized_date\nvars[{amount_field!r}] = normalize_amount_input(vars.get({amount_field!r}))"
        if node_id == decision:
            for name in sorted(set(identity_fields) - {date_field}):
                body += f"\n_kaan_identity_date = normalize_date_input(vars.get({name!r}), identity=True)\nif _kaan_identity_date:\n    vars[{name!r}] = _kaan_identity_date"
                if name == roles['identity_answer']:
                    body += f"\nif vars.get({roles['stage']!r}) == {identity_stage!r} and not str(vars.get({name!r}) or '').strip():\n    _kaan_identity_date = normalize_date_input(vars.get({roles['speech_text']!r}), identity=True)\n    if _kaan_identity_date:\n        vars[{name!r}] = _kaan_identity_date"
        code = _snippet(nodes[node_id])
        original, prefix = _section(code['default'], 'LANGUAGE INPUT', body)
        code['default'] = prefix + original
    changes.append('raw Turkish/English dates and Turkish decimal amounts are normalized before the sourced guards')
    return compiled, changes
