"""Local checks for generated Freya workflows, before any bank call is allowed."""

import ast
import builtins
import copy
import datetime
import importlib
import multiprocessing
import re
import types


REQUIRED_CHECKS = (
    "identity_unverified", "invalid_amount", "invalid_date",
    "correction_clears_confirmation", "business_failure_not_success",
    "duplicate_promise_blocked", "negative_confirmation",
)
SAFE_MODULES = {
    "json": ("loads", "dumps", "JSONDecodeError"),
    "datetime": ("date", "datetime", "timedelta", "timezone", "time"),
    "decimal": ("Decimal", "InvalidOperation", "ROUND_HALF_UP", "ROUND_DOWN"),
    "calendar": ("weekday", "monthrange", "day_name", "day_abbr", "month_name", "month_abbr"),
    "math": None,
    "re": ("compile", "match", "fullmatch", "search", "findall", "sub", "split", "escape", "IGNORECASE", "I"),
    "copy": ("copy", "deepcopy"),
}
SAFE_BUILTINS = {name: getattr(builtins, name) for name in (
    "abs", "all", "any", "bool", "dict", "enumerate", "float", "format", "int", "isinstance",
    "len", "list", "max", "min", "next", "range", "reversed", "round", "set", "sorted",
    "str", "sum", "tuple", "zip", "Exception", "ValueError", "TypeError",
    "KeyError", "IndexError", "ZeroDivisionError", "OverflowError", "AssertionError",
)}
UNSAFE_CALLS = {"open", "eval", "exec", "compile", "input", "globals", "locals", "getattr", "setattr", "delattr", "breakpoint", "help", "exit", "quit", "now", "today", "utcnow"}
UNSAFE_ATTRIBUTES = {"f_back", "f_globals", "f_locals", "gi_frame", "cr_frame", "ag_frame", "tb_frame"}
PLACEHOLDER = re.compile(r"^\{\{([\w.]+)(?::json)?\}\}$")


def _resolve(value, document, seen=()):
    if isinstance(value, dict) and "$ref" in value:
        ref = value["$ref"]
        if not ref.startswith("#/") or ref in seen:
            raise ValueError("only non-cyclic local OpenAPI references are supported")
        target = document
        for part in ref[2:].split("/"):
            target = target[part.replace("~1", "/").replace("~0", "~")]
        return _resolve(target, document, (*seen, ref))
    return value


def _null_paths(value, path="workflow"):
    if value is None:
        yield path
    elif isinstance(value, dict):
        for key, item in value.items():
            yield from _null_paths(item, f"{path}.{key}")
    elif isinstance(value, list):
        for index, item in enumerate(value):
            yield from _null_paths(item, f"{path}[{index}]")


def _parse(code):
    if not isinstance(code, str) or not code.strip():
        raise ValueError("snippet must be a nonempty string")
    if "{{" in code or "}}" in code:
        raise ValueError("template braces in Python snippet")
    tree = ast.parse(code)
    for node in ast.walk(tree):
        if isinstance(node, (ast.ClassDef, ast.Global, ast.Nonlocal, ast.NamedExpr)):
            raise ValueError(f"unsupported Python statement {type(node).__name__}")
        if isinstance(node, ast.Name) and node.id.startswith("__"):
            raise ValueError("private names are unavailable")
        if isinstance(node, ast.Name) and node.id in UNSAFE_CALLS - {"now", "today", "utcnow"}:
            raise ValueError(f"unsafe callable and aliases are unavailable: {node.id}")
        if isinstance(node, ast.Attribute) and (node.attr.startswith("_") or node.attr in UNSAFE_ATTRIBUTES):
            raise ValueError("private/runtime attributes are unavailable")
        if isinstance(node, ast.Attribute) and node.attr in ("now", "today", "utcnow"):
            raise ValueError("real-clock attributes and aliases are unavailable")
        if isinstance(node, ast.Import):
            if any(item.name not in SAFE_MODULES for item in node.names):
                raise ValueError("import outside the standard-library allowlist")
        if isinstance(node, ast.ImportFrom):
            if node.level or node.module not in SAFE_MODULES or any(item.name == "*" or item.name.startswith("_") for item in node.names):
                raise ValueError("import outside the standard-library allowlist")
            allowed = SAFE_MODULES[node.module]
            if allowed is not None and any(item.name not in allowed for item in node.names):
                raise ValueError("module member outside the allowlist")
        if isinstance(node, ast.Call):
            name = node.func.id if isinstance(node.func, ast.Name) else node.func.attr if isinstance(node.func, ast.Attribute) else ""
            if name in UNSAFE_CALLS and not (name == "compile" and isinstance(node.func, ast.Attribute) and isinstance(node.func.value, ast.Name) and node.func.value.id == "re"):
                raise ValueError(f"unsafe or real-clock call: {name}")
    compile(tree, "<generated-workflow>", "exec")
    return tree


def _writes(tree):
    writes = set()
    parents = {child: node for node in ast.walk(tree) for child in ast.iter_child_nodes(node)}
    for node in ast.walk(tree):
        if isinstance(node, ast.arg) and node.arg == "vars":
            raise ValueError("do not shadow the workflow variable table")
        if isinstance(node, ast.Name) and node.id == "vars":
            parent = parents.get(node)
            direct_index = isinstance(parent, ast.Subscript) and parent.value is node
            direct_method = isinstance(parent, ast.Attribute) and parent.value is node and isinstance(parents.get(parent), ast.Call) and parents[parent].func is parent
            if not isinstance(node.ctx, ast.Load) or not (direct_index or direct_method):
                raise ValueError("do not replace, alias or pass the workflow variable table")
        if isinstance(node, (ast.Assign, ast.AnnAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            if any(isinstance(target, ast.Name) and target.id == "vars" for target in targets) or isinstance(node.value, ast.Name) and node.value.id == "vars":
                raise ValueError("do not replace or alias the workflow variable table")
        if isinstance(node, ast.Return) and isinstance(node.value, ast.Name) and node.value.id == "vars":
            raise ValueError("do not return the workflow variable table")
        if isinstance(node, ast.Call) and any(isinstance(argument, ast.Name) and argument.id == "vars" for argument in node.args + [item.value for item in node.keywords]):
            raise ValueError("do not pass the workflow variable table to helpers")
        if isinstance(node, ast.Subscript) and isinstance(node.ctx, (ast.Store, ast.Del)) and isinstance(node.value, ast.Name) and node.value.id == "vars":
            if not isinstance(node.slice, ast.Constant) or not isinstance(node.slice.value, str):
                raise ValueError("workflow variable writes need literal names")
            writes.add(node.slice.value)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and isinstance(node.func.value, ast.Name) and node.func.value.id == "vars":
            if node.func.attr == "update":
                if len(node.args) != 1 or not isinstance(node.args[0], ast.Dict) or node.keywords:
                    raise ValueError("vars.update requires one literal dictionary")
                for key in node.args[0].keys:
                    if not isinstance(key, ast.Constant) or not isinstance(key.value, str):
                        raise ValueError("workflow variable writes need literal names")
                    writes.add(key.value)
            elif node.func.attr in ("pop", "setdefault"):
                if not node.args or not isinstance(node.args[0], ast.Constant):
                    raise ValueError("workflow variable writes need literal names")
                writes.add(node.args[0].value)
            elif node.func.attr not in ("get", "keys", "values", "items", "copy"):
                raise ValueError("unsupported workflow variable mutation")
    return writes


def _pre_hook_request(tree, lifecycle):
    # Request hooks may edit closing outcome/reason only; other requests are immutable.
    parents = {child: node for node in ast.walk(tree) for child in ast.iter_child_nodes(node)}
    body_aliases = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and isinstance(node.value, ast.Call) and isinstance(node.value.func, ast.Attribute) and isinstance(node.value.func.value, ast.Name) and node.value.func.value.id == "config" and node.value.func.attr == "get" and node.value.args and isinstance(node.value.args[0], ast.Constant) and node.value.args[0].value == "body":
            body_aliases.update(target.id for target in node.targets if isinstance(target, ast.Name))
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and node.id == "config":
            parent = parents.get(node)
            if not lifecycle:
                raise ValueError("pre-hook may not access or mutate request config")
            if isinstance(parent, ast.Subscript) and parent.value is node:
                if not isinstance(parent.slice, ast.Constant) or parent.slice.value != "body":
                    raise ValueError("closing pre-hook may replace body only")
                usage = parents.get(parent)
                if isinstance(parent.ctx, ast.Store):
                    if not isinstance(usage, ast.Assign) or not isinstance(usage.value, ast.Name) or usage.value.id not in body_aliases:
                        raise ValueError("closing pre-hook must preserve the original request body")
                elif isinstance(usage, ast.Subscript) and usage.value is parent:
                    if not isinstance(usage.slice, ast.Constant) or usage.slice.value not in ("outcome", "reason"):
                        raise ValueError("closing pre-hook may edit outcome/reason only")
                elif isinstance(usage, ast.Attribute) and usage.value is parent:
                    call = parents.get(usage)
                    if usage.attr not in ("get", "pop") or not isinstance(call, ast.Call) or not call.args or not isinstance(call.args[0], ast.Constant) or call.args[0].value not in ("outcome", "reason"):
                        raise ValueError("closing pre-hook may edit outcome/reason only")
                else:
                    raise ValueError("do not alias or pass closing request body")
            elif isinstance(parent, ast.Attribute) and parent.value is node:
                call = parents.get(parent)
                if parent.attr != "get" or not isinstance(call, ast.Call) or not call.args or not isinstance(call.args[0], ast.Constant) or call.args[0].value != "body":
                    raise ValueError("closing pre-hook may read body only")
            else:
                raise ValueError("do not alias or pass request config")
        if isinstance(node, ast.Name) and node.id in body_aliases:
            parent = parents.get(node)
            if isinstance(node.ctx, ast.Store):
                assignment = parents.get(node)
                if not isinstance(assignment, ast.Assign) or not isinstance(assignment.value, ast.Call) or not isinstance(assignment.value.func, ast.Attribute) or not isinstance(assignment.value.func.value, ast.Name) or assignment.value.func.value.id != "config":
                    raise ValueError("closing request body may not be replaced or aliased")
            elif isinstance(parent, ast.Subscript) and parent.value is node:
                if not isinstance(parent.slice, ast.Constant) or parent.slice.value not in ("outcome", "reason"):
                    raise ValueError("closing pre-hook may edit outcome/reason only")
            elif isinstance(parent, ast.Attribute) and parent.value is node:
                call = parents.get(parent)
                if parent.attr not in ("get", "pop") or not isinstance(call, ast.Call) or not call.args or not isinstance(call.args[0], ast.Constant) or call.args[0].value not in ("outcome", "reason"):
                    raise ValueError("closing pre-hook may edit outcome/reason only")
            elif not (isinstance(parent, ast.Assign) and parent.value is node and any(isinstance(target, ast.Subscript) and isinstance(target.value, ast.Name) and target.value.id == "config" for target in parent.targets)):
                raise ValueError("do not alias or pass closing request body")


def _safe_import(name, globals=None, locals=None, fromlist=(), level=0):
    if name in ("_strptime", "time") and not level:
        return importlib.import_module(name)
    if level or name not in SAFE_MODULES:
        raise ImportError("module unavailable")
    module = importlib.import_module(name)
    proxy = types.ModuleType(name)
    for member in SAFE_MODULES[name] or tuple(key for key in dir(module) if not key.startswith("_")):
        setattr(proxy, member, getattr(module, member))
    return proxy


def _authorization_values(tree, variable):
    for node in ast.walk(tree):
        targets = node.targets if isinstance(node, ast.Assign) else [node.target] if isinstance(node, (ast.AnnAssign, ast.AugAssign)) else []
        for target in targets:
            if isinstance(target, ast.Subscript) and isinstance(target.value, ast.Name) and target.value.id == "vars" and isinstance(target.slice, ast.Constant) and target.slice.value == variable:
                yield node.value if not isinstance(node, ast.AugAssign) else None
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and isinstance(node.func.value, ast.Name) and node.func.value.id == "vars":
            if node.func.attr == "update" and node.args and isinstance(node.args[0], ast.Dict):
                for key, value in zip(node.args[0].keys, node.args[0].values):
                    if isinstance(key, ast.Constant) and key.value == variable:
                        yield value
            elif node.func.attr == "setdefault" and node.args and isinstance(node.args[0], ast.Constant) and node.args[0].value == variable:
                yield node.args[1] if len(node.args) > 1 else ast.Constant(value=None)


def _reads(tree):
    fields = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Subscript) and isinstance(node.ctx, ast.Load) and isinstance(node.value, ast.Name) and node.value.id == "vars" and isinstance(node.slice, ast.Constant):
            fields.add(node.slice.value)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and isinstance(node.func.value, ast.Name) and node.func.value.id == "vars" and node.func.attr == "get" and node.args and isinstance(node.args[0], ast.Constant):
            fields.add(node.args[0].value)
    return fields


def _execute(code, check, connection):
    try:
        namespace = {
            "__builtins__": dict(SAFE_BUILTINS, __import__=_safe_import),
            "vars": copy.deepcopy(check.get("vars", {})),
            "config": copy.deepcopy(check.get("config", {})),
            "result": copy.deepcopy(check.get("result", {})),
        }
        exec(compile(code, "<generated-workflow>", "exec"), namespace, namespace)
        connection.send({key: namespace[key] for key in ("vars", "config", "result")})
    except BaseException as exc:
        connection.send({"error": f"{type(exc).__name__}: {exc}"})
    finally:
        connection.close()


def _json_equal(actual, expected):
    if isinstance(actual, bool) or isinstance(expected, bool):
        return type(actual) is type(expected) and actual == expected
    if isinstance(actual, (int, float)) and isinstance(expected, (int, float)):
        return actual == expected
    if isinstance(actual, dict) and isinstance(expected, dict):
        return actual.keys() == expected.keys() and all(_json_equal(value, expected[key]) for key, value in actual.items())
    if isinstance(actual, list) and isinstance(expected, list):
        return len(actual) == len(expected) and all(_json_equal(left, right) for left, right in zip(actual, expected))
    return type(actual) is type(expected) and actual == expected


def _run_check(code, check):
    # shortcut: subprocess isolation is for generated checks, use an OS sandbox for hostile code.
    context = multiprocessing.get_context("fork")
    parent, child = context.Pipe(duplex=False)
    process = context.Process(target=_execute, args=(code, check, child))
    process.start()
    child.close()
    try:
        if not parent.poll(2):
            raise ValueError("snippet exceeded the two-second check limit")
        output = parent.recv()
        if "error" in output:
            raise ValueError(output["error"])
        for key, expected in check["expected"].items():
            if key.startswith(("result.", "config.")):
                parts = key.split(".")
                actual = output[parts.pop(0)]
                for part in parts:
                    if not isinstance(actual, dict) or part not in actual:
                        raise ValueError(f"expected output {key} was not produced")
                    actual = actual[part]
            else:
                if key not in output["vars"]:
                    raise ValueError(f"expected variable {key} was not produced")
                actual = output["vars"][key]
            if not _json_equal(actual, expected):
                raise ValueError(f"{key}: expected {expected!r}, got {actual!r}")
        if check.get("forbid_api") and output["config"] != check.get("config", {}):
            raise ValueError("forbid_api check changed the HTTP request")
        return output
    finally:
        if process.is_alive():
            process.terminate()
        process.join(1)
        parent.close()


def _exact_guard(condition, variable, operand):
    def implies(item):
        if not isinstance(item, dict):
            return False
        if item.get("operator") == "equals":
            return item.get("variable") == variable and item.get("operand") == operand
        children = item.get("conditions", [])
        if not isinstance(children, list) or not children:
            return False
        if item.get("logic") == "and":
            return any(implies(child) for child in children)
        return item.get("logic") == "or" and all(implies(child) for child in children)
    return isinstance(condition, dict) and condition.get("logic") == "or" and implies(condition)


def _reachable(edges, starts, removed=()):
    visited, pending = set(), list(starts)
    while pending:
        node = pending.pop()
        if node in visited or node in removed:
            continue
        visited.add(node)
        pending.extend(edges.get(node, ()))
    return visited


def _graph_checks(workflow, nodes, security):
    errors, edges, always = [], {}, {}
    for name, node in nodes.items():
        edges[name] = set()
        always[name] = set()
        for transition in node.get("transitions", []):
            target = transition.get("target_node")
            if target in nodes:
                edges[name].add(target)
                if transition.get("condition") == {"operator": "always"}:
                    always[name].add(target)
        for key in ("passthrough_default_transition", "max_turn_transition"):
            if node.get(key) in nodes:
                edges[name].add(node[key])
                if node.get("passthrough"):
                    always[name].add(node[key])
    initial = workflow.get("initial_node")
    reachable = _reachable(edges, [initial])
    required = set(security.get("account_nodes", []) + security.get("record_nodes", []) + security.get("confirmation_nodes", []) + [security.get("offer_guard_node"), security.get("approval_guard_node")])
    required.update(name for name, node in nodes.items() if node.get("node_type") == "api_request")
    required.update(gate.get("node") for gate in security.get("action_guards", {}).values() if isinstance(gate, dict))
    for name in required - reachable:
        errors.append(f"{name}: required guard/action is unreachable from initial_node")
    roots = [initial, *workflow.get("global_nodes", {})]
    before_offer = _reachable(edges, roots, [security.get("offer_guard_node")])
    for name in set(security.get("confirmation_nodes", []) + security.get("record_nodes", [])) & before_offer:
        errors.append(f"{name}: offer guard does not dominate readback/record")
    before_readback = _reachable(edges, roots, security.get("confirmation_nodes", []))
    for name in {security.get("approval_guard_node"), *security.get("record_nodes", [])} & before_readback:
        errors.append(f"{name}: confirmation readback does not dominate approval/record")
    terminals = {name for name, node in nodes.items() if node.get("node_type") == "end_call"}
    reverse = {name: set() for name in nodes}
    for source, targets in edges.items():
        for target in targets:
            reverse[target].add(source)
    for name in reachable - _reachable(reverse, terminals):
        errors.append(f"{name}: no path reaches an end_call terminal")
    actions = {name for name, node in nodes.items() if node.get("node_type") in ("code", "api_request") and node.get("passthrough")}
    for name in actions:
        action_edges = {source: targets & actions for source, targets in always.items() if source in actions}
        if name in _reachable(action_edges, action_edges.get(name, ())):
            errors.append(f"{name}: unconditional action loop without user input")
    return errors


def _condition(condition, state):
    if "logic" in condition:
        values = [_condition(item, state) for item in condition.get("conditions", [])]
        if not values or condition["logic"] not in ("and", "or"):
            raise ValueError("unsupported grouped transition")
        return all(values) if condition["logic"] == "and" else any(values)
    operator = condition.get("operator")
    value, operand = state.get(condition.get("variable"), ""), condition.get("operand", "")
    if operator == "always":
        return True
    if operator in ("equals", "not_equals"):
        equal = str(value) == str(operand)
        return equal if operator == "equals" else not equal
    if operator in ("greater_than", "less_than"):
        return float(value) > float(operand) if operator == "greater_than" else float(value) < float(operand)
    if operator == "contains":
        return str(operand).lower() in str(value).lower()
    if operator in ("is_set", "is_not_set"):
        return bool(value) if operator == "is_set" else not bool(value)
    raise ValueError(f"unsupported transition in independent chain: {operator}")


def _identity_requirements(policy, brief_lines):
    rules = {rule["id"]: rule for rule in policy.get("source_rules", []) if isinstance(rule, dict) and isinstance(rule.get("id"), str)}
    if len(rules) != len(policy.get("source_rules", [])):
        raise ValueError("identity source rules need unique IDs")
    sources = {name: rule.get("text", "") for name, rule in rules.items()}
    if brief_lines is not None:
        sources = {}
        for name, rule in rules.items():
            lines = brief_lines.get(rule.get("source"), [])
            line = rule.get("line")
            if type(line) is int and 1 <= line <= len(lines):
                end = next((index for index in range(line, len(lines)) if re.match(r"^\s*(?:\d+\.\s|#{1,6}\s)", lines[index])), len(lines))
                sources[name] = "\n".join(lines[line - 1:end])
    superseded = set()
    priority = {source: index for index, source in enumerate(brief_lines or {})}
    for name, rule in rules.items():
        for relation in ("replaces", "replaced_by"):
            links = rule.get(relation, [])
            links = [links] if isinstance(links, str) else links
            if not isinstance(links, list) or any(not isinstance(link, str) or link not in rules for link in links):
                raise ValueError("identity replacement must reference known source rule IDs")
            for link in links:
                old, new = (link, name) if relation == "replaces" else (name, link)
                old_source, new_source = rules[old].get("source"), rules[new].get("source")
                if (old not in sources or new not in sources or old_source not in priority or
                        new_source not in priority or priority[new_source] <= priority[old_source]):
                    raise ValueError("identity replacement needs original sources and higher input priority")
                number = re.match(r"^\s*(\d+)\.\s", sources[old])
                # shortcut: explicit numbered-rule replacements, extend for a new supplied memo format.
                reference = re.search(r"\b(?:replace[sd]?|supersede[sd]?|override[sd]?)\s+(?:(brief\s+\w+)\s+)?rule\s+(\d+)\b", sources[new], re.I)
                if not number or not reference or reference[2] != number[1]:
                    raise ValueError("identity replacement lacks an explicit original-source rule reference")
                if reference[1] and not any(re.match(r"^#+\s+" + re.escape(reference[1]) + r"\b", line, re.I) for line in brief_lines[old_source]):
                    raise ValueError("identity replacement references a different source brief")
                earlier_matches = [key for key, text in sources.items()
                                   if priority.get(rules[key].get("source"), len(priority)) < priority[new_source]
                                   and re.match(r"^\s*" + number[1] + r"\.\s", text)]
                if not reference[1] and len(earlier_matches) != 1:
                    raise ValueError("identity replacement has an ambiguous source rule reference")
                superseded.add(old)
    patterns = {
        "date": r"\b(?:date of birth|birth date|birthdate|dob|(?:doğum|dogum) tarih(?:i|ini|iniz|inizi))\b",
        "numeric_code": r"\b(?:last (?:\w+|[0-9]+) digits|numeric (?:code|answer)|(?:[0-9]+|four|six)[ -]digit (?:code|pin)|pin code|son (?:[0-9]+|iki|üç|uc|dört|dort|altı|alti) (?:hane(?:si|sini)?|rakam(?:ı|i|ları|lari|larını|larini)?)|(?:sayısal|sayisal) kod|pin kodu)\b",
    }
    required = set()
    counts = {}
    # shortcut: explicit English/Turkish question counts; prose-only counts need a sourced format.
    count_pattern = r"\b(?:ask\s+)?(one|two|three|four|bir|iki|üç|uc|dört|dort|[0-9]+)\s+(?:adet\s+)?(?:security questions?|güvenlik sorusu|guvenlik sorusu|güvenlik soruları|guvenlik sorulari)\b"
    numbers = {"one": 1, "two": 2, "three": 3, "four": 4, "bir": 1, "iki": 2, "üç": 3, "uc": 3, "dört": 4, "dort": 4}
    for name, text in sources.items():
        if name in superseded:
            continue
        if rules[name].get("stage") != "identity" and not re.search(count_pattern, text, re.I):
            continue
        required_text = re.sub(r"\b(?:never|do not|don't)\s+ask[^.!?]*(?:[.!?]|$)", "", text, flags=re.I)
        required_text = re.sub(r"[^.!?]*\b(?:sorma|sormayın|sormayin|sorulmaz|sorulmamalıdır|sorulmamalidir)\b[^.!?]*(?:[.!?]|$)", "", required_text, flags=re.I)
        required.update(kind for kind, pattern in patterns.items() if re.search(pattern, required_text, re.I))
        count = re.search(count_pattern, text, re.I)
        if count:
            word = count[1].lower().replace("\u0307", "")
            counts[name] = numbers.get(word, int(word) if word.isdigit() else 0)
    if brief_lines is not None:
        for lines in brief_lines.values():
            for text in lines:
                if re.search(count_pattern, text, re.I) and not any(text in source for source in sources.values()):
                    raise ValueError("identity_questions omitted a required identity source rule")
    return {name: text for name, text in sources.items() if name not in superseded}, required, counts, patterns


def _independent_checks(nodes, snippets, security, checks, policy=None, openapi=None, brief_lines=None, close_tool=None):
    """Use declared synthetic inputs, but keep every expected invariant in the builder."""
    reports = []
    roles = security.get("validation_state", {})
    events = security.get("validation_events", {})
    routes = security.get("validation_routes", {})
    fixture = security.get("validation_fixture", {})
    confirmation = security.get("validation_confirmation_fixture", {})
    correction_fixture = security.get("validation_correction_fixture", {})
    identity = security.get("validation_identity_fixture", {})
    identity_resume = security.get("validation_identity_resume_fixture", {})
    third_party_fixture = security.get("validation_third_party_fixture", {})
    identity_answer_fixture = security.get("validation_identity_answer_fixture", {})
    identity_code_fixture = security.get("validation_identity_code_fixture", {})
    required_roles = ("proposed_amount", "proposed_date", "approval_event", "approval_amount", "approval_date", "approval_text", "correction", "decision_event", "decision_date", "decision_amount", "full_amount", "identity_answer", "speech_text", "persuasion_attempts", "party_confirmation", "recorded", "offer_fingerprint", "readback_fingerprint", "exception", "route", "stage", "write_attempts", "write_result")
    for label, data, names in (("validation_state", roles, required_roles), ("validation_events", events, ("yes", "no", "question", "human", "plan", "hardship", "dispute", "third_party")), ("validation_routes", routes, ("account", "confirmation", "record", "offer", "transfer", "end"))):
        if not isinstance(data, dict) or any(not isinstance(data.get(name), str) or not data[name] for name in names):
            return [{"name": "independent_contract", "ok": False, "error": f"security.{label} needs every declared string role"}]
    if len(set(roles.values())) != len(roles):
        return [{"name": "independent_contract", "ok": False, "error": "validation_state roles must name different variables"}]
    if not all(isinstance(data, dict) and data for data in (fixture, confirmation, identity)):
        return [{"name": "independent_contract", "ok": False, "error": "independent checks need offer, confirmation and identity input fixtures"}]
    trusted = set(security.get("trusted_variables", []))
    contract_errors = []
    source_texts = [line for lines in brief_lines.values() for line in lines] if brief_lines is not None else [rule.get("text", "") for rule in (policy or {}).get("source_rules", [])]
    def has_ai_answer(text):
        answer = (policy or {}).get("speech", {}).get("ai_answer")
        return (answer.lower() in text.lower() if isinstance(answer, str) and answer.strip()
                else "digital assistant" in text.lower())
    if any(re.search(r"\bif it fails\s*,\s*try once more\b", text, re.I) for text in source_texts) and security.get("write_attempt_limit") != 2:
        contract_errors.append("write_attempt_limit must preserve the source-required second attempt")
    promise_fields = security.get("promise_request_fields", {})
    if not isinstance(promise_fields, dict) or set(promise_fields) != {"amount", "date"} or any(not isinstance(value, str) or not value for value in promise_fields.values()) or len(set(promise_fields.values())) != 2:
        contract_errors.append("promise_request_fields must map amount/date to distinct actual API properties")
    questions = security.get("identity_questions", [])
    identity_kinds = set()
    try:
        sources, required_kinds, required_counts, kind_patterns = _identity_requirements(policy or {}, brief_lines)
        if not isinstance(questions, list) or not questions:
            raise ValueError("identity_questions must explicitly declare every source-required question")
        contexts = []
        for question in questions:
            if not isinstance(question, dict) or question.get("kind") not in (*kind_patterns, "text"):
                raise ValueError("identity_questions need a date, numeric_code or text kind")
            kind, source = question["kind"], question.get("source_rule")
            text = question.get("source_text")
            if not isinstance(text, str) or not text.strip() or text not in sources.get(source, ""):
                raise ValueError("identity_questions must quote the actual source rule for each required question")
            if kind in kind_patterns and not re.search(kind_patterns[kind], text, re.I):
                raise ValueError("identity_questions kind must match its source question text")
            context = question.get("request_context")
            if not isinstance(context, dict) or not context or context in contexts:
                raise ValueError("identity_questions need distinct actual pending-question request contexts")
            contexts.append(context)
            identity_kinds.add(kind)
        if not required_kinds <= identity_kinds:
            raise ValueError("identity_questions omitted a required identity question type")
        for source, count in required_counts.items():
            if sum(question.get("source_rule") == source for question in questions) != count:
                raise ValueError("identity_questions omitted or added a question required by the source count")
        for kind, context in (("date", security.get("validation_identity_request_context")), ("numeric_code", security.get("validation_identity_code_request_context"))):
            if kind in identity_kinds and [question["request_context"] for question in questions if question["kind"] == kind] != [context]:
                raise ValueError(f"identity_questions {kind} must match the actual validation request context")
    except (ValueError, TypeError, KeyError) as exc:
        contract_errors.append(str(exc))
    for label, data, required in (("confirmation", confirmation, True), ("correction", correction_fixture, True), ("identity resume", identity_resume, False)):
        if not isinstance(data, dict) or required and not data:
            contract_errors.append(f"{label} fixture must provide fresh speech inputs")
        elif set(data) & (trusted | {security.get("customer_id_variable")}):
            contract_errors.append(f"{label} fixture may provide fresh speech only")
    if not {roles[name] for name in ("recorded", "offer_fingerprint", "readback_fingerprint", "exception", "route", "stage", "write_attempts", "write_result", "persuasion_attempts", "party_confirmation", "full_amount")} <= trusted:
        contract_errors.append("validation_state control roles must be trusted")
    authorization = security.get("record_authorization_variable", "record_authorization")
    authorized = security.get("record_authorization_operand", "authorized")
    party_confirmed = security.get("party_confirmation_operand")
    if not isinstance(party_confirmed, str) or not party_confirmed:
        contract_errors.append("security.party_confirmation_operand must be a nonempty string")
    if not isinstance(third_party_fixture, dict) or not third_party_fixture or not third_party_fixture.get(roles["stage"]):
        contract_errors.append("third-party fixture must provide current identity state and fresh speech inputs")
    reserved = {security.get("bank_verification_variable"), authorization, security.get("customer_id_variable")}
    if {roles[name] for name in ("decision_event", "decision_date", "decision_amount", "full_amount", "identity_answer", "speech_text", "persuasion_attempts", "party_confirmation")} & reserved:
        contract_errors.append("decision controls must be separate from bank, record and customer controls")
    decision = security.get("decision_node")
    decision_inputs = {field.get("name") for node in nodes.values() if any(item.get("target_node") == decision for item in node.get("transitions", [])) for field in node.get("extraction_schema", [])}
    if roles["decision_event"] not in decision_inputs or roles["decision_event"] in trusted:
        contract_errors.append("decision_event must name fresh speech consumed by the decision node")
    if roles["identity_answer"] not in decision_inputs or roles["identity_answer"] in trusted:
        contract_errors.append("identity_answer must name fresh speech consumed by the decision node")
    if roles["decision_date"] not in decision_inputs or roles["decision_date"] in trusted:
        contract_errors.append("decision_date must name fresh speech consumed by the decision node")
    if roles["speech_text"] not in decision_inputs or roles["speech_text"] in trusted:
        contract_errors.append("speech_text must name fresh speech consumed by the decision node")
    if roles["decision_amount"] not in decision_inputs or roles["decision_amount"] in trusted:
        contract_errors.append("decision_amount must name fresh speech consumed by the decision node")
    full_amount = fixture.get(roles["full_amount"])
    try:
        if type(full_amount) not in (int, float) or not 0 < float(full_amount) < float("inf"):
            raise ValueError("invalid bank amount")
    except (TypeError, ValueError, OverflowError):
        contract_errors.append("validation_fixture must provide a finite positive numeric full_amount")
    proposal_day = None
    try:
        proposal_day = datetime.date.fromisoformat(fixture.get(roles["proposed_date"]))
        if proposal_day.isoformat() != fixture[roles["proposed_date"]]:
            raise ValueError("noncanonical fixture date")
    except (TypeError, ValueError):
        contract_errors.append("validation_fixture must provide a canonical ISO proposed_date")
    if isinstance(third_party_fixture, dict) and not any(third_party_fixture.get(name) for name in decision_inputs - {roles["decision_event"]}):
        contract_errors.append("third-party fixture needs a nonempty actual speech field besides decision_event")
    canonical_identity_answer = None
    if "date" in identity_kinds:
        try:
            if not isinstance(identity_answer_fixture, dict) or not identity_answer_fixture.get(roles["stage"]):
                raise ValueError("identity answer fixture needs current pre-verification state")
            canonical_identity_answer = identity_answer_fixture.get(roles["identity_answer"])
            if not isinstance(canonical_identity_answer, str) or datetime.date.fromisoformat(canonical_identity_answer).isoformat() != canonical_identity_answer:
                raise ValueError("identity answer fixture needs a valid canonical ISO raw answer")
        except (TypeError, ValueError) as exc:
            contract_errors.append(f"validation_identity_answer_fixture: {exc}")
    canonical_identity_code = None
    if "numeric_code" in identity_kinds:
        if not isinstance(identity_code_fixture, dict) or not identity_code_fixture.get(roles["stage"]):
            contract_errors.append("validation_identity_code_fixture needs current pending-code identity state")
        else:
            canonical_identity_code = identity_code_fixture.get(roles["speech_text"])
            if not isinstance(canonical_identity_code, str) or not re.fullmatch(r"0[0-9]+", canonical_identity_code):
                contract_errors.append("validation_identity_code_fixture needs a canonical numeric string in speech_text with a leading zero")
    verification_requests = [(identifier, tool) for identifier, node in nodes.items() for tool in node.get("pre_actions", []) if tool.get("function", {}).get("name") in security.get("verification_tools", ["verify_identity"])]
    answer_request_field = security.get("identity_answer_request_field")
    if not isinstance(answer_request_field, str) or not answer_request_field or answer_request_field == security.get("customer_id_field") or not any(answer_request_field in tool.get("function", {}).get("parameters", {}).get("properties", {}).get("body", {}).get("properties", {}) for _, tool in verification_requests):
        contract_errors.append("identity_answer_request_field must name an actual verification request property")
    identity_request_context = security.get("validation_identity_request_context")
    identity_code_context = security.get("validation_identity_code_request_context")
    def context_schema_matches(tool, context):
        properties = tool.get("function", {}).get("parameters", {}).get("properties", {}).get("body", {}).get("properties", {})
        if answer_request_field not in properties or not set(context) <= set(properties):
            return False
        for name, value in context.items():
            field = properties[name]
            expected_type = {"string": str, "number": (int, float), "integer": int, "boolean": bool}.get(field.get("type"))
            if not expected_type or not isinstance(value, expected_type):
                return False
            if field.get("type") in ("number", "integer") and (isinstance(value, bool) or not -float("inf") < value < float("inf")):
                return False
            if "enum" in field and not any(_json_equal(value, operand) for operand in field["enum"]):
                return False
        return True
    contexts_to_check = [("identity_questions", question.get("request_context")) for question in questions]
    if "date" in identity_kinds:
        contexts_to_check.append(("validation_identity_request_context", identity_request_context))
    if "numeric_code" in identity_kinds:
        contexts_to_check.append(("validation_identity_code_request_context", identity_code_context))
    for label, context in contexts_to_check:
        if not isinstance(context, dict) or not context:
            contract_errors.append(f"{label} must declare the pending question's request properties")
        elif any(not isinstance(name, str) or not name or name in (security.get("customer_id_field"), answer_request_field) or not isinstance(value, (str, int, float, bool)) or isinstance(value, str) and "{{" in value for name, value in context.items()):
            contract_errors.append(f"{label} needs literal values and cannot include customer or answer fields")
        elif not any(context_schema_matches(tool, context) for _, tool in verification_requests):
            contract_errors.append(f"{label} must match real verification request property types and enums")
    for question in questions:
        if question.get("kind") == "text":
            question_fixture = question.get("fixture", {})
            if not isinstance(question_fixture, dict) or not question_fixture.get(roles["stage"]) or not isinstance(question_fixture.get(roles["identity_answer"]), str) or not question_fixture[roles["identity_answer"]].strip():
                contract_errors.append("identity_questions text fixture needs a pending question and a nonempty synthetic raw answer")
    offer, approval = security.get("offer_guard_node"), security.get("approval_guard_node")
    record_nodes = security.get("record_nodes", [])
    readbacks = security.get("confirmation_nodes", [])
    approval_inputs = {field.get("name") for name in readbacks for field in nodes.get(name, {}).get("extraction_schema", [])}
    if not {roles[name] for name in ("approval_event", "approval_amount", "approval_date", "approval_text", "correction")} <= approval_inputs - trusted:
        contract_errors.append("approval roles must name fresh confirmation extraction fields")
    result_node = security.get("record_result_node")
    if nodes.get(result_node, {}).get("node_type") != "code" or nodes[result_node].get("passthrough") is not True:
        contract_errors.append("record_result_node must name the shared passthrough result-processing code node")
    for name in record_nodes:
        transitions = nodes.get(name, {}).get("transitions", [])
        if len(transitions) != 1 or transitions[0].get("target_node") != result_node or transitions[0].get("condition") != {"operator": "always"}:
            contract_errors.append(f"{name}: success and error must always reach record_result_node")
        if any(nodes[name].get(key, result_node) != result_node for key in ("passthrough_default_transition", "max_turn_transition")):
            contract_errors.append(f"{name}: record fallback must also reach record_result_node")
    for identifier, required_reads, required_writes in (
        (offer, ("proposed_amount", "proposed_date"), ("offer_fingerprint", "readback_fingerprint")),
        (approval, ("approval_event", "approval_amount", "approval_date", "approval_text", "correction", "recorded", "offer_fingerprint", "readback_fingerprint", "write_attempts", "write_result"), ("route", "write_attempts", "approval_event", "approval_amount", "approval_date", "approval_text", "correction")),
        (decision, ("decision_event", "decision_date", "decision_amount", "full_amount", "identity_answer", "speech_text", "persuasion_attempts", "party_confirmation"), ("decision_event", "decision_date", "decision_amount", "identity_answer", "speech_text", "persuasion_attempts", "party_confirmation")),
    ):
        if identifier not in snippets:
            contract_errors.append(f"missing guard snippet {identifier}")
            continue
        try:
            tree = _parse(snippets[identifier][0])
            if not {roles[name] for name in required_reads} <= _reads(tree) or not {roles[name] for name in required_writes} <= _writes(tree):
                raise ValueError(f"{identifier}: validation roles must be the actual guard reads/writes")
            if identifier == decision and roles["full_amount"] in _writes(tree):
                raise ValueError("decision may not overwrite the trusted bank full_amount")
        except (ValueError, SyntaxError) as exc:
            contract_errors.append(str(exc))
    if contract_errors:
        return [{"name": "independent_contract", "ok": False, "error": error} for error in contract_errors]

    def step(identifier, state, result=None):
        if identifier not in snippets:
            raise ValueError(f"independent chain needs snippet {identifier}")
        _writes(_parse(snippets[identifier][0]))
        output = _run_check(snippets[identifier][0], {"vars": state, "result": result or {}, "expected": {}})["vars"]
        for node in nodes.values():
            if any(item.get("target_node") == identifier for item in node.get("transitions", [])):
                for field in node.get("extraction_schema", []):
                    if output.get(field.get("name")) != "":
                        raise ValueError(f"consumed extraction {field.get('name')} was not cleared")
        return output

    def advance(identifier, state, forbidden=()):
        for _ in range(len(nodes) + 1):
            if identifier in forbidden:
                raise ValueError(f"unsafe chain entered {identifier}")
            node = nodes[identifier]
            if node.get("node_type") != "code":
                return state, identifier
            state = step(identifier, state)
            identifier = next((item["target_node"] for item in node.get("transitions", []) if _condition(item.get("condition", {}), state)), None)
            if identifier not in nodes:
                raise ValueError("independent chain has no deterministic next node")
        raise ValueError("independent chain exceeded graph length without user input")

    def assert_denied(state):
        if state.get(authorization) == authorized:
            raise ValueError("unsafe chain activated record authorization")

    def valid_readback(input_state=None, start=offer):
        state = copy.deepcopy(fixture if input_state is None else input_state)
        for field in (authorization, roles["recorded"], roles["offer_fingerprint"], roles["readback_fingerprint"]):
            state[field] = ""
        state[roles["write_attempts"]] = 0
        state[roles["write_result"]] = ""
        state, target = advance(start, state)
        if target not in readbacks or not state.get(roles["offer_fingerprint"]) or state.get(roles["readback_fingerprint"]) != state[roles["offer_fingerprint"]]:
            raise ValueError("valid offer did not reach a matching current readback")
        assert_denied(state)
        return state

    def confirm(state):
        state.update(copy.deepcopy(confirmation))
        state[roles["approval_event"]] = events["yes"]
        return advance(approval, state)

    def next_node(identifier, state):
        target = next((item["target_node"] for item in nodes[identifier].get("transitions", []) if _condition(item.get("condition", {}), state)), None)
        if target not in nodes:
            raise ValueError("record result has no deterministic next node")
        return target

    def complete_record(target, state, result, skip_post=False):
        # The platform exposes node response keys even when its error path skips the hook.
        state = copy.deepcopy(state)
        prefix = target + "_response."
        for name in ("status", "status_code", "message"):
            if name in result:
                state[prefix + name] = str(result[name])
        for name, value in result.get("data", {}).items() if isinstance(result.get("data"), dict) else ():
            state[prefix + "data." + name] = str(value).lower() if isinstance(value, bool) else value
        counter = target + ("_failure_count" if result.get("status") == "error" else "_success_count")
        state[counter] = int(state.get(counter, 0)) + 1
        hook = f"{target}:create_promise:post"
        if not skip_post and hook in snippets:
            state = step(hook, state, result)
        return advance(next_node(target, state), state)

    def bound_request(target, state, tools=None):
        bodies = []
        for tool in nodes[target].get("pre_actions", []) if tools is None else tools:
            body = tool.get("function", {}).get("parameters", {}).get("properties", {}).get("body", {})
            values = {}
            for name, field in body.get("properties", {}).items():
                value = field.get("default")
                placeholder = PLACEHOLDER.fullmatch(value) if isinstance(value, str) else None
                if placeholder:
                    value = state.get(placeholder.group(1))
                if name in body.get("required", []) and value in (None, ""):
                    raise ValueError(f"authorized request has no bound {name}")
                expected_type = {"string": str, "number": (int, float), "integer": int, "boolean": bool, "object": dict, "array": list}.get(field.get("type"))
                if expected_type and not isinstance(value, expected_type):
                    raise ValueError(f"authorized request has wrong runtime type for {name}")
                if field.get("type") in ("number", "integer") and (isinstance(value, bool) or not -float("inf") < value < float("inf")):
                    raise ValueError(f"authorized request has non-finite/boolean {name}")
                if "enum" in field and value not in field["enum"]:
                    raise ValueError(f"authorized request has invalid {name} enum")
                values[name] = value
            bodies.append((tool.get("function", {}).get("name"), values))
        return bodies

    def run(name, function):
        report = {"name": name, "ok": False}
        try:
            function()
            report["ok"] = True
        except (ValueError, KeyError, TypeError, EOFError, SyntaxError) as exc:
            report["error"] = str(exc)
        reports.append(report)

    def invalid_chain(field, value):
        state = copy.deepcopy(fixture)
        state[roles[field]] = value
        state = step(offer, state)
        state.update(copy.deepcopy(confirmation))
        state[roles["approval_event"]] = events["yes"]
        state = step(approval, state)
        assert_denied(state)

    for value in ("-1", "0", "NaN", "Infinity"):
        run(f"independent_invalid_amount_{value}", lambda value=value: invalid_chain("proposed_amount", value))
    for label, value in (
        ("nan", "NaN dollars"), ("infinity", "Infinity dollars"),
        ("negative", "-1 dollars"), ("zero", "0 dollars"),
        ("trailing_prose", f"{full_amount} dollars on {fixture[roles['proposed_date']]}"),
        ("date_digits", f"{fixture[roles['proposed_date']]} {full_amount} dollars"),
    ):
        run(f"independent_invalid_currency_amount_{label}", lambda value=value: invalid_chain("proposed_amount", value))
    run("independent_invalid_date", lambda: invalid_chain("proposed_date", "2026-02-30"))
    for check in checks:
        if isinstance(check, dict) and check.get("node_id") == offer and any(check.get("name", "").startswith(category) for category in ("invalid_amount", "invalid_date")):
            def invalid_boundary(check=check):
                state = copy.deepcopy(fixture)
                state.update(copy.deepcopy(check.get("vars", {})))
                state = step(offer, state)
                state.update(copy.deepcopy(confirmation))
                state[roles["approval_event"]] = events["yes"]
                assert_denied(step(approval, state))
            run("independent_boundary_" + check["name"], invalid_boundary)

    def positive():
        state, target = confirm(valid_readback())
        if target not in record_nodes or state.get(authorization) != authorized:
            raise ValueError("valid current yes did not reach an authorized record action")
        bound_request(target, state)
        state, _ = complete_record(target, state, {"status": "success", "status_code": 200, "data": {"ok": True}})
        if state.get(roles["recorded"]) != "recorded":
            raise ValueError("successful business result did not mark the current product recorded")
        state, target = confirm(state)
        assert_denied(state)
        if target in record_nodes:
            raise ValueError("recorded product reached a second record action")
    run("independent_valid_record_and_duplicate", positive)

    def full_amount_state(event, raw_amount="full amount"):
        state = copy.deepcopy(fixture)
        for name in decision_inputs:
            state[name] = ""
        state[roles["decision_event"]] = event
        state[roles["decision_amount"]] = raw_amount
        state[roles["decision_date"]] = fixture[roles["proposed_date"]]
        state[roles["proposed_amount"]] = "0"
        for name in (authorization, roles["recorded"], roles["offer_fingerprint"], roles["readback_fingerprint"]):
            state[name] = ""
        return state

    def record_amount(state, expected_amount, expected_date=None):
        state, target = confirm(state)
        if target not in record_nodes or state.get(authorization) != authorized:
            raise ValueError("amount readback and current yes did not authorize a record action")
        requests = bound_request(target, state)
        matching_amounts = [body for name, body in requests if name == "create_promise" and _json_equal(body.get(promise_fields["amount"]), expected_amount)]
        if not matching_amounts:
            raise ValueError("amount promise did not bind the original numeric amount")
        if expected_date is not None and not any(body.get(promise_fields["date"]) == expected_date for body in matching_amounts):
            raise ValueError("promise did not bind the original canonical date")
        state, _ = complete_record(target, state, {"status": "success", "status_code": 200, "data": {"ok": True}})
        if state.get(roles["recorded"]) != "recorded":
            raise ValueError("successful amount result did not mark the product recorded")

    def explicit_full_amount(raw_amount="full amount"):
        state = valid_readback(full_amount_state(events["yes"], raw_amount), decision)
        if not _json_equal(state.get(roles["full_amount"]), full_amount) or raw_amount == "full amount" and float(state.get(roles["proposed_amount"], 0)) != full_amount:
            raise ValueError("current full amount reference did not resolve the trusted bank full_amount")
        record_amount(state, full_amount)
    run("independent_current_full_amount_record", explicit_full_amount)
    run("independent_current_currency_amount_record", lambda: explicit_full_amount(f"{full_amount} dollars"))

    def shared_currency_amount():
        state = copy.deepcopy(fixture)
        expected_amount = float(state[roles["proposed_amount"]])
        state[roles["proposed_amount"]] = f"{state[roles['proposed_amount']]} dollars"
        record_amount(valid_readback(state), expected_amount)
    run("independent_shared_currency_amount_record", shared_currency_amount)

    weekdays = "Monday Tuesday Wednesday Thursday Friday Saturday Sunday".split()
    proposal_suffix = "th" if 11 <= proposal_day.day % 100 <= 13 else {1: "st", 2: "nd", 3: "rd"}.get(proposal_day.day % 10, "th")

    def weekday_ordinal_state(current, mismatch=False):
        state = full_amount_state(events["yes"], str(full_amount)) if current else copy.deepcopy(fixture)
        weekday = weekdays[(proposal_day.weekday() + (1 if mismatch else 0)) % 7]
        state[roles["decision_date"] if current else roles["proposed_date"]] = f"{weekday} the {proposal_day.day}{proposal_suffix}"
        return state

    def weekday_ordinal_record(current):
        expected_amount = full_amount if current else float(fixture[roles["proposed_amount"]])
        state = valid_readback(weekday_ordinal_state(current), decision if current else offer)
        record_amount(state, expected_amount, proposal_day.isoformat())

    def mismatched_weekday(current):
        state = weekday_ordinal_state(current, True)
        for name in (authorization, roles["recorded"], roles["offer_fingerprint"], roles["readback_fingerprint"]):
            state[name] = ""
        state, target = advance(decision if current else offer, state, (*readbacks, *record_nodes, *security.get("account_nodes", [])))
        assert_denied(state)
        if target not in security.get("close_nodes", []) and (nodes[target].get("node_type") != "conversation" or not nodes[target].get("extraction_schema")):
            raise ValueError("mismatched weekday must return to a real listener or end safely")
        state.update(copy.deepcopy(confirmation))
        state[roles["approval_event"]] = events["yes"]
        assert_denied(step(approval, state))

    for current, label in ((True, "current"), (False, "shared")):
        run(f"independent_{label}_weekday_ordinal_record", lambda current=current: weekday_ordinal_record(current))
        run(f"independent_{label}_mismatched_weekday_denied", lambda current=current: mismatched_weekday(current))

    payment_month = ("January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December")[proposal_day.month - 1]
    day_words = "zero first second third fourth fifth sixth seventh eighth ninth tenth eleventh twelfth thirteenth fourteenth fifteenth sixteenth seventeenth eighteenth nineteenth twentieth".split()
    payment_ordinal_day = day_words[proposal_day.day] if proposal_day.day <= 20 else (
        "thirtieth" if proposal_day.day == 30 else
        ("twenty-" if proposal_day.day < 30 else "thirty-") + day_words[proposal_day.day % 10])
    cardinal_words = "zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen seventeen eighteen nineteen".split()
    cardinal_day = cardinal_words[proposal_day.day] if proposal_day.day < 20 else (
        ("twenty" if proposal_day.day < 30 else "thirty") +
        (" " + cardinal_words[proposal_day.day % 10] if proposal_day.day % 10 else ""))

    def month_day_record(raw, current):
        state = full_amount_state(events["yes"], str(full_amount)) if current else copy.deepcopy(fixture)
        state[roles["decision_date"] if current else roles["proposed_date"]] = raw
        expected_amount = full_amount if current else float(fixture[roles["proposed_amount"]])
        state = valid_readback(state, decision if current else offer)
        record_amount(state, expected_amount, proposal_day.isoformat())

    for current, label in ((True, "current"), (False, "shared")):
        for form, raw in (("day_first", f"{proposal_day.day} {payment_month}"),
                          ("month_first", f"{payment_month} {proposal_day.day}{proposal_suffix}"),
                          ("of_month", f"the {proposal_day.day}{proposal_suffix} of {payment_month}"),
                          ("word_ordinal", f"the {payment_ordinal_day} of {payment_month}"),
                          ("word_cardinal", f"{payment_month} {cardinal_day}"),
                          ("word_weekday", f"{weekdays[proposal_day.weekday()]} the {payment_ordinal_day}")):
            run(f"independent_{label}_payment_month_day_{form}", lambda raw=raw, current=current: month_day_record(raw, current))

    def inactive_full_amount(event):
        state, target = advance(decision, full_amount_state(event), (offer, *readbacks, *record_nodes, *security.get("account_nodes", [])))
        assert_denied(state)
        if target not in security.get("close_nodes", []) and (nodes[target].get("node_type") != "conversation" or not nodes[target].get("extraction_schema")):
            raise ValueError("inactive full amount event must return to a real listener or end safely")
    for label, event in (("empty", ""), ("no", events["no"])):
        run(f"independent_full_amount_{label}_event_blocks_offer", lambda event=event: inactive_full_amount(event))

    def changed_readback():
        state = valid_readback()
        state[roles["offer_fingerprint"]] += ":changed"
        state, _ = confirm(state)
        assert_denied(state)
    run("independent_stale_readback", changed_readback)

    def corrected():
        state = valid_readback()
        state.update(copy.deepcopy(confirmation))
        state[roles["approval_event"]] = events["yes"]
        state[roles["correction"]] = "yes"
        state = step(approval, state)
        assert_denied(state)
        state = valid_readback()
        state.update(copy.deepcopy(correction_fixture))
        state[roles["correction"]] = "yes"
        state = step(approval, state)
        assert_denied(state)
        next_node = next((item["target_node"] for item in nodes[approval].get("transitions", []) if _condition(item.get("condition", {}), state)), None)
        state, target = advance(next_node, state)
        if target not in readbacks or state.get(roles["offer_fingerprint"]) != state.get(roles["readback_fingerprint"]) or not state.get(roles["readback_fingerprint"]):
            raise ValueError("correction did not return through offer validation and fresh readback")
        state, target = confirm(state)
        if target not in record_nodes or state.get(authorization) != authorized:
            raise ValueError("fresh explicit yes after correction could not record")
    run("independent_correction_requires_readback", corrected)

    def unmarked_correction(field, marker):
        state = valid_readback()
        original_fingerprint = state[roles["offer_fingerprint"]]
        original, original_target = confirm(copy.deepcopy(state))
        if original_target not in record_nodes or original.get(authorization) != authorized:
            raise ValueError("original readback could not authorize a valid request")
        original_request = bound_request(original_target, original)
        changed_amount = full_amount if float(fixture[roles["proposed_amount"]]) != float(full_amount) else float(full_amount) + 1
        value = str(changed_amount) if field == "amount" else (proposal_day + datetime.timedelta(days=1)).isoformat()
        state[authorization] = authorized
        state.update(copy.deepcopy(confirmation))
        state[roles["approval_event"]] = events["yes"]
        state[roles["correction"]] = marker
        state[roles["approval_" + field]] = value
        state[roles["approval_text"]] = f"Yes, use {value}."
        state = step(approval, state)
        assert_denied(state)
        if state.get(roles["readback_fingerprint"]) or state.get(roles["offer_fingerprint"]):
            raise ValueError("changed current approval retained the old readback authorization")
        proposed = state.get(roles["proposed_" + field])
        if (field == "amount" and float(proposed) != float(value)) or (field == "date" and proposed != value):
            raise ValueError("changed current approval did not carry its new value to offer validation")
        target = next_node(approval, state)
        if target != offer:
            raise ValueError("changed current approval did not reach the shared offer guard")
        state, target = advance(target, state)
        assert_denied(state)
        if target in readbacks:
            fingerprint = state.get(roles["readback_fingerprint"])
            # Revalidation may offer the same deadline; freshness comes from the cleared state and graph.
            if not fingerprint or fingerprint != state.get(roles["offer_fingerprint"]):
                raise ValueError("changed current approval did not produce a fresh matching readback")
            waiting, target = advance(approval, copy.deepcopy(state))
            assert_denied(waiting)
            if target in record_nodes:
                raise ValueError("corrected readback reached recording without a new explicit yes")
            state, target = confirm(state)
            if target not in record_nodes or state.get(authorization) != authorized:
                raise ValueError("fresh explicit yes after corrected readback could not record")
            request = bound_request(target, state)
            if request != original_request and fingerprint == original_fingerprint:
                raise ValueError("changed accepted offer reused the old readback fingerprint")
        else:
            if state.get(roles["readback_fingerprint"]):
                raise ValueError("changed current approval skipped the actual readback node")
            if target not in security.get("close_nodes", []) and (nodes[target].get("node_type") != "conversation" or not nodes[target].get("extraction_schema")):
                raise ValueError("invalid changed approval did not stop for clarification or safe closure")
    for field in ("amount", "date"):
        for marker, label in (("", "missing"), ("no", "wrong")):
            run(f"independent_approval_{field}_{label}_correction_marker", lambda field=field, marker=marker: unmarked_correction(field, marker))

    def rejected(event):
        state = valid_readback()
        state.update(copy.deepcopy(confirmation))
        state[roles["approval_event"]] = events[event]
        state[authorization] = authorized
        state = step(approval, state)
        assert_denied(state)
    for event in ("no", "question"):
        run(f"independent_{event}_clears_authorization", lambda event=event: rejected(event))

    def exception(event):
        state = valid_readback()
        state.update(copy.deepcopy(confirmation))
        state[roles["approval_event"]] = events[event]
        state[roles["correction"]] = "yes"
        state[roles["proposed_amount"]] = "100"
        state = step(approval, state)
        assert_denied(state)
        if state.get(roles["exception"]) != events[event] and state.get(roles["route"]) in (routes["confirmation"], routes["offer"], routes["record"]):
            raise ValueError("exception was lost before its safe decision")
        next_node = next((item["target_node"] for item in nodes[approval].get("transitions", []) if _condition(item.get("condition", {}), state)), None)
        state, target = advance(next_node, state)
        assert_denied(state)
        if target in record_nodes + readbacks or state.get(roles["route"]) in (routes["confirmation"], routes["offer"]):
            raise ValueError("exception with correction became an ordinary offer/readback")
        if nodes[target].get("node_type") == "api_request":
            bound_request(target, state)
    for event in ("human", "plan", "dispute"):
        run(f"independent_{event}_with_correction", lambda event=event: exception(event))

    def record_result(result, unknown=False, skip_post=False, stale=False):
        state = valid_readback()
        if stale:
            for name in record_nodes:
                state.update({name + "_response.status": "error", name + "_response.status_code": "500", name + "_response.data.ok": "true", name + "_response.message": "Nothing was recorded. The call may be repeated.", name + "_failure_count": 8})
        state, target = confirm(state)
        if target not in record_nodes:
            raise ValueError("failure check could not reach record action")
        state, target = complete_record(target, state, result, skip_post)
        if state.get(roles["recorded"]) == "recorded":
            raise ValueError("failed/unknown business result marked current product recorded")
        if unknown:
            assert_denied(state)
            if (target in record_nodes or
                    nodes[target].get("node_type") == "api_request" and target not in security.get("close_nodes", []) or
                    int(state.get(roles["write_attempts"], 0)) != 1):
                raise ValueError("unknown current write result retried the bank action")
    run("independent_failed_record", lambda: record_result({"status": "success", "status_code": 200, "data": {"ok": False}}))
    run("independent_unknown_record_no_retry", lambda: record_result({"status": "error", "message": "timeout"}, True, True))
    run("independent_stale_record_status_no_retry", lambda: record_result({"status": "error", "message": "timeout"}, True, True, True))
    run("independent_missing_record_status_no_retry", lambda: record_result({}, True, True, True))
    run("independent_missing_record_body_no_retry", lambda: record_result({"status": "success", "status_code": 200}, True, True, True))

    def retry_limit(recovered=False):
        limit = security.get("write_attempt_limit")
        if type(limit) is not int or limit < 1:
            raise ValueError("security.write_attempt_limit must be a positive integer")
        state, target = confirm(valid_readback())
        approved_request = bound_request(target, state)
        failure = {"status": "success", "status_code": 200, "data": {"ok": False}}
        state, target = complete_record(target, state, failure)
        if limit > 1:
            if target not in record_nodes or state.get(authorization) != authorized or int(state.get(roles["write_attempts"], 0)) != 2:
                raise ValueError("allowed retry did not preserve authorization and count one new attempt")
            if bound_request(target, state) != approved_request:
                raise ValueError("retry changed the immutable approved bank request")
            result = {"status": "success", "status_code": 200, "data": {"ok": True}} if recovered else failure
            state, target = complete_record(target, state, result)
            if recovered and state.get(roles["recorded"]) != "recorded":
                raise ValueError("successful second attempt did not mark the promise recorded")
        assert_denied(state)
        if target in record_nodes:
            raise ValueError("failed record exceeded source write attempt limit")
        if int(state.get(roles["write_attempts"], 0)) > limit:
            raise ValueError("failed record exceeded source write attempt limit")
    run("independent_failed_record_retry_limit", retry_limit)
    if security.get("write_attempt_limit", 1) > 1:
        run("independent_failed_record_then_success", lambda: retry_limit(True))

    def sourced_error_statuses():
        statuses = set()
        for path, item in (openapi or {}).get("paths", {}).items():
            for method, raw_operation in _resolve(item, openapi).items():
                if method.lower() != "post":
                    continue
                operation = _resolve(raw_operation, openapi)
                if operation.get("operationId", path.strip("/").replace("/", "_")) != "create_promise":
                    continue
                for code, response in operation.get("responses", {}).items():
                    description = _resolve(response, openapi).get("description", "").lower()
                    if str(code).isdigit() and 400 <= int(code) < 600 and re.search(r"nothing (?:was|is) recorded", description) and re.search(r"(?:call may be repeated|may be retried|retry is permitted)", description):
                        statuses.add(str(code))
        return statuses

    def error_retry(status_code, allowed, recovered=False):
        limit = security.get("write_attempt_limit")
        state, target = confirm(valid_readback())
        if target not in record_nodes:
            raise ValueError("error replay could not reach the real record action")
        approved_request = bound_request(target, state)
        failure = {"status": "error", "status_code": int(status_code), "message": "API write failed"}
        state, target = complete_record(target, state, failure, skip_post=True)
        if state.get(roles["recorded"]) == "recorded":
            raise ValueError("API error with skipped hook marked the promise recorded")
        if allowed and limit > 1:
            if target not in record_nodes or state.get(authorization) != authorized or int(state.get(roles["write_attempts"], 0)) != 2:
                raise ValueError("sourced no-write API error with skipped hook did not reach the permitted retry")
            if bound_request(target, state) != approved_request:
                raise ValueError("retry changed the immutable approved bank request")
            if recovered:
                state, target = complete_record(target, state, {"status": "success", "status_code": 200, "data": {"ok": True}})
                if state.get(roles["recorded"]) != "recorded":
                    raise ValueError("successful second attempt did not mark the promise recorded")
            else:
                state, target = complete_record(target, state, failure, skip_post=True)
        assert_denied(state)
        if (target in record_nodes or
                nodes[target].get("node_type") == "api_request" and target not in security.get("close_nodes", []) or
                int(state.get(roles["write_attempts"], 0)) > min(limit, 2)):
            raise ValueError("API error exceeded the one permitted retry or retried without a no-write guarantee")
    safe_statuses = sourced_error_statuses()
    for status in sorted(safe_statuses):
        run(f"independent_api_error_{status}_skipped_hook_retry", lambda status=status: error_retry(status, True))
        if security.get("write_attempt_limit", 1) > 1:
            run(f"independent_api_error_{status}_skipped_hook_then_success", lambda status=status: error_retry(status, True, True))
    for status in ("500", "504"):
        if status not in safe_statuses:
            run(f"independent_api_error_{status}_without_no_write_guarantee", lambda status=status: error_retry(status, False))

    def identity_return():
        state = copy.deepcopy(identity)
        bank_var = security.get("bank_verification_variable")
        state[bank_var] = "verified"
        state, target = advance(security.get("decision_node"), state)
        assert_denied(state)
        if target not in security.get("account_nodes", []) and nodes[target].get("node_type") == "conversation" and target not in readbacks:
            if state.get(roles["stage"]) == "identity" or not identity_resume:
                raise ValueError("verified question recovery needs changed stage and fresh identity resume fixture")
            state.update(copy.deepcopy(identity_resume))
            state, target = advance(security.get("decision_node"), state)
        if target not in security.get("account_nodes", []) or state.get(roles["stage"]) == "identity" or state.get(bank_var) != "verified":
            raise ValueError("verified identity plus question did not resume account loading")
        assert_denied(state)
    run("independent_verified_identity_question_return", identity_return)

    def identity_complete():
        state = copy.deepcopy(identity)
        bank_var = security.get("bank_verification_variable")
        state[bank_var] = "verified"
        for node in nodes.values():
            for field in node.get("extraction_schema", []):
                state[field["name"]] = ""
        state, target = advance(security.get("decision_node"), state)
        if target not in security.get("account_nodes", []) or state.get(roles["stage"]) == "identity" or state.get(bank_var) != "verified":
            raise ValueError("completed verified identity must load account without a fresh caller reply")
        assert_denied(state)
    run("independent_verified_identity_completion", identity_complete)

    def missing_speech():
        state = copy.deepcopy(fixture)
        for node in nodes.values():
            for field in node.get("extraction_schema", []):
                state[field["name"]] = ""
        state[authorization] = ""
        state[roles["persuasion_attempts"]] = 0
        state, target = advance(decision, state, (offer, *readbacks, *record_nodes))
        assert_denied(state)
        if nodes[target].get("node_type") != "conversation" or not nodes[target].get("extraction_schema"):
            raise ValueError("missing speech must return to a real listener without a bank action")
        if not _json_equal(state.get(roles["persuasion_attempts"]), 0):
            raise ValueError("missing speech consumed a persuasion attempt")
    run("independent_missing_decision_speech", missing_speech)

    privacy_rules = [rule.get("text", "") for rule in (policy or {}).get("source_rules", [])
                     if rule.get("stage") == "identity" and "before identity" in rule.get("text", "").lower()]
    privacy_rules += [line for lines in (brief_lines or {}).values() for line in lines if "before identity" in line.lower()]
    forbidden_words = [word for text in privacy_rules for word in re.findall(r'["“]([^"”]+)["”]', text.lower().split("before identity")[0].split("do not say")[-1])]

    def identity_close_body(state):
        if not close_tool:
            raise ValueError("pre-identity check needs the actual close action")
        state = dict(state)
        state.setdefault(security["customer_id_variable"], fixture[security["customer_id_variable"]])
        body = bound_request("workflow", state, [close_tool])[0][1]
        hook = next((code for code, operation, kind in snippets.values() if operation == "close_call" and kind == "pre"), "")
        if hook:
            body = _run_check(hook, {"vars": state, "config": {"body": body}, "expected": {}})["config"]["body"]
        return {name: body.get(name) for name in ("outcome", "reason")}

    def pre_identity_exception(event, human=False, relative=False, speech=""):
        state = copy.deepcopy(security.get("validation_pre_identity_human_fixture") if human else third_party_fixture)
        if not isinstance(state, dict) or not state:
            raise ValueError("pre-identity human fixture must contain a current insisting request")
        state[security.get("bank_verification_variable")] = "unverified"
        state[authorization] = ""
        if not human and not relative:
            for field in decision_inputs:
                state[field] = ""
        baseline = copy.deepcopy(state)
        # A relative's speech and offered identity answer belong to both comparison states.
        for field in (roles["decision_event"],) if relative else decision_inputs:
            baseline[field] = ""
        baseline = step(decision, baseline)
        state[roles["decision_event"]] = event
        if not human:
            state[roles["speech_text"]] = (str(state.get(roles["speech_text"], "")) + " " + speech).strip()
        state, target = advance(decision, state, (offer, *readbacks, *record_nodes, *security.get("account_nodes", []), *(identifier for identifier, _ in verification_requests)))
        assert_denied(state)
        node = nodes[target]
        speech = node.get("on_enter", {}).get("text", "")
        if node.get("node_type") == "end_call":
            speech += " " + node.get("terminal", {}).get("function", {}).get("parameters", {}).get("properties", {}).get("spoken_message", {}).get("default", "")
        speech = re.sub(r'\{\{([\w.]+)(?::json)?\}\}', lambda match: str(state.get(match.group(1), "")), speech)
        if any(re.search(r'\b' + re.escape(word) + r'\w*\b', speech, re.I) for word in forbidden_words):
            raise ValueError("pre-identity exception emitted source-forbidden speech")
        if human:
            if node.get("node_type") != "api_request" or not any(name == "transfer_to_agent" for name, _ in bound_request(target, state)):
                raise ValueError("permitted pre-identity human request did not reach a guarded transfer")
        elif node.get("node_type") != "conversation" or not node.get("extraction_schema"):
            raise ValueError("account-specific pre-identity claim must return to an identity listener, without an account closing outcome")
        elif identity_close_body(state) != identity_close_body(baseline):
            raise ValueError("pre-identity claim changed the actual stage-safe close outcome/reason")

    if forbidden_words:
        for name, speech in (("paid", "I already paid."), ("dispute", "This debt is not mine."), ("plan", "I want a new payment plan.")):
            for relative in (False, True):
                suffix = "_relative" if relative else ""
                run(f"independent_pre_identity_{name}{suffix}", lambda name=name, speech=speech, relative=relative: pre_identity_exception(events[name], relative=relative, speech=speech))
        run("independent_pre_identity_human", lambda: pre_identity_exception(events["human"], True))

    def identity_state(input_fixture=identity_answer_fixture):
        state = copy.deepcopy(input_fixture)
        state[security.get("bank_verification_variable")] = "unverified"
        state[roles["party_confirmation"]] = party_confirmed
        state[authorization] = ""
        return state

    def current_identity_state(input_fixture, field, value):
        state = identity_state(input_fixture)
        event = state.get(roles["decision_event"], "")
        for name in decision_inputs:
            state[name] = ""
        state[roles["decision_event"]] = event
        state[field] = value
        return state

    def identity_request_boundary(state, expected_answer, request_context, label):
        state, target = advance(decision, state, (offer, *readbacks, *record_nodes, *security.get("account_nodes", [])))
        assert_denied(state)
        if nodes[target].get("node_type") != "api_request" or target not in {identifier for identifier, _ in verification_requests}:
            raise ValueError(f"complete spoken identity {label} did not reach a verification API action")
        requests = bound_request(target, state)
        canonical_requests = [body for name, body in requests if name in security.get("verification_tools", ["verify_identity"]) and body.get(answer_request_field) == expected_answer]
        if not canonical_requests:
            form = "canonical ISO" if label == "date" else "unchanged canonical code"
            raise ValueError(f"spoken identity {label} was not bound as the {form} verification answer")
        if not any(all(name in body and _json_equal(body[name], value) for name, value in request_context.items()) for body in canonical_requests):
            raise ValueError(f"spoken identity {label} request did not match the declared pending-question context")

    small_words = "zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen seventeen eighteen nineteen".split()
    if "date" in identity_kinds:
        def identity_date_answer(raw_answer, main_date=None):
            field, value = (roles["identity_answer"], raw_answer) if main_date is None else (roles["decision_date"], main_date)
            state = current_identity_state(identity_answer_fixture, field, value)
            identity_request_boundary(state, canonical_identity_answer, identity_request_context, "date")
        day = datetime.date.fromisoformat(canonical_identity_answer)
        month = ("January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December")[day.month - 1]
        suffix = "th" if 11 <= day.day % 100 <= 13 else {1: "st", 2: "nd", 3: "rd"}.get(day.day % 10, "th")
        for label, answer in (
            ("day_first", f"{day.day} {month} {day.year:04d}"),
            ("month_first", f"{month} {day.day} {day.year:04d}"),
            ("ordinal_day", f"{day.day}{suffix} {month} {day.year:04d}"),
            ("ordinal_month_comma", f"{month} {day.day}{suffix}, {day.year:04d}"),
            ("upper_case", f"{day.day} {month.upper()} {day.year:04d}"),
            ("lower_case_comma", f"{month.lower()} {day.day}, {day.year:04d}"),
        ):
            run(f"independent_identity_date_words_{label}", lambda answer=answer: identity_date_answer(answer))
        run("independent_identity_date_in_main_date", lambda: identity_date_answer("", f"{day.day} {month} {day.year:04d}"))
        for label, speech in (
            ("period", f"{day.day} {month} {day.year:04d}."),
            ("period_underscore", f"{day.day} {month} {day.year:04d}._"),
            ("prefix", f"My date of birth is {day.day} {month} {day.year:04d}."),
        ):
            run(f"independent_identity_date_in_speech_text_{label}", lambda speech=speech: identity_request_boundary(current_identity_state(identity_answer_fixture, roles["speech_text"], speech), canonical_identity_answer, identity_request_context, "date"))

        tens_words = "zero ten twenty thirty forty fifty sixty seventy eighty ninety".split()
        ordinal_words = "zero first second third fourth fifth sixth seventh eighth ninth tenth eleventh twelfth thirteenth fourteenth fifteenth sixteenth seventeenth eighteenth nineteenth".split()

        def small_number_words(number):
            return small_words[number] if number < 20 else tens_words[number // 10] + (" " + small_words[number % 10] if number % 10 else "")

        def cardinal_year_words(year):
            parts = []
            if year // 1000:
                parts.append(small_words[year // 1000] + " thousand")
            if year % 1000 // 100:
                parts.append(small_words[year % 1000 // 100] + " hundred")
            if year % 100:
                parts.append(("and " if parts else "") + small_number_words(year % 100))
            return " ".join(parts)

        def ordinal_day_words(number):
            if number < 20:
                return ordinal_words[number]
            if number in (20, 30):
                return "twentieth" if number == 20 else "thirtieth"
            return tens_words[number // 10] + "-" + ordinal_words[number % 10]

        grouped_year = cardinal_year_words(day.year)
        if day.year >= 1000:
            remainder = day.year % 100
            grouped_year = small_number_words(day.year // 100) + (" hundred" if not remainder else " oh " + small_words[remainder] if remainder < 10 else " " + small_number_words(remainder))
        ordinal_day = ordinal_day_words(day.day)
        hyphen_day = day if day.day > 20 and day.day != 30 else day.replace(day=21 + (day.day - 1) % 8)
        for label, raw, expected in (
            ("ordinal", f"{ordinal_day} {month} {grouped_year}", day.isoformat()),
            ("optional_words", f"the {ordinal_day} of {month} {grouped_year}", day.isoformat()),
            ("hyphenated", f"the {ordinal_day_words(hyphen_day.day)} of {month} {grouped_year.replace(' ', '-')}", hyphen_day.isoformat()),
            ("cardinal_year", f"My date of birth is the {ordinal_day} of {month} {cardinal_year_words(day.year)}.", day.isoformat()),
        ):
            for role, input_label in (("identity_answer", "answer"), ("speech_text", "speech_text")):
                run(f"independent_identity_word_date_{input_label}_{label}", lambda raw=raw, expected=expected, role=role: identity_request_boundary(current_identity_state(identity_answer_fixture, roles[role], raw), expected, identity_request_context, "date"))
        cardinal_day = f"{small_number_words(day.day)} {month} {grouped_year}"
        for role, label in (("identity_answer", "answer"), ("speech_text", "speech_text")):
            run(f"independent_identity_cardinal_day_{label}", lambda role=role: identity_request_boundary(current_identity_state(identity_answer_fixture, roles[role], cardinal_day), day.isoformat(), identity_request_context, "date"))

        def missing_identity_year(role, raw=None):
            state = current_identity_state(identity_answer_fixture, roles[role], raw if raw is not None else f"the {ordinal_day} of {month}.")
            for _, tool in verification_requests:
                field = tool.get("function", {}).get("parameters", {}).get("properties", {}).get("body", {}).get("properties", {}).get(answer_request_field, {})
                value = field.get("default")
                placeholder = PLACEHOLDER.fullmatch(value) if isinstance(value, str) else None
                if placeholder and placeholder.group(1) not in decision_inputs:
                    state[placeholder.group(1)] = canonical_identity_answer
            forbidden = (offer, *readbacks, *record_nodes, *security.get("account_nodes", []), *(identifier for identifier, _ in verification_requests))
            state, target = advance(decision, state, forbidden)
            assert_denied(state)
            if nodes[target].get("node_type") != "conversation" or not nodes[target].get("extraction_schema"):
                raise ValueError("identity date without a year must return to a real listener")
        for role, label in (("identity_answer", "answer"), ("speech_text", "speech_text")):
            run(f"independent_missing_identity_year_{label}", lambda role=role: missing_identity_year(role))
            for form, year in (("grouped", "nineteen and"), ("thousand", "two thousand and")):
                raw = f"the {ordinal_day_words(min(day.day, 28))} of {month} {year}."
                run(f"independent_dangling_identity_year_{label}_{form}", lambda role=role, raw=raw: missing_identity_year(role, raw))

    if "numeric_code" in identity_kinds:
        code_prefix = "My last four digits are" if len(canonical_identity_code) == 4 else "My verification code is"
        for label, speech in (("period", canonical_identity_code + "."), ("prefix", code_prefix + " " + canonical_identity_code + ".")):
            run(f"independent_identity_code_in_speech_text_{label}", lambda speech=speech: identity_request_boundary(current_identity_state(identity_code_fixture, roles["speech_text"], speech), canonical_identity_code, identity_code_context, "code"))
        code_words = [small_words[int(digit)] for digit in canonical_identity_code]
        for label, separator in (("space", " "), ("comma", ", "), ("hyphen", "-")):
            speech = separator.join(code_words)
            for role, input_label in (("identity_answer", "answer"), ("speech_text", "speech_text")):
                run(f"independent_identity_code_words_{input_label}_{label}", lambda speech=speech, role=role: identity_request_boundary(current_identity_state(identity_code_fixture, roles[role], speech), canonical_identity_code, identity_code_context, "code"))

    def missing_identity_speech(input_fixture=identity_answer_fixture, cached_answer=canonical_identity_answer, partial_code_field=None):
        state = identity_state(input_fixture)
        event = state.get(roles["decision_event"], "")
        for _, tool in verification_requests:
            field = tool.get("function", {}).get("parameters", {}).get("properties", {}).get("body", {}).get("properties", {}).get(answer_request_field, {})
            value = field.get("default")
            placeholder = PLACEHOLDER.fullmatch(value) if isinstance(value, str) else None
            if placeholder:
                state[placeholder.group(1)] = cached_answer
        for field in decision_inputs:
            state[field] = ""
        if partial_code_field:
            state[roles["decision_event"]] = event
            state[partial_code_field] = " ".join(code_words[:-1])
        state[security.get("bank_verification_variable")] = "unverified"
        state[roles["party_confirmation"]] = party_confirmed
        state[authorization] = ""
        forbidden = (offer, *readbacks, *record_nodes, *security.get("account_nodes", []), *(identifier for identifier, _ in verification_requests))
        state, target = advance(decision, state, forbidden)
        assert_denied(state)
        if nodes[target].get("node_type") != "conversation" or not nodes[target].get("extraction_schema"):
            raise ValueError("missing identity speech must return to a real listener without a bank action")
    if "date" in identity_kinds:
        run("independent_missing_identity_speech", missing_identity_speech)
    if "numeric_code" in identity_kinds:
        run("independent_missing_identity_code_speech", lambda: missing_identity_speech(identity_code_fixture, canonical_identity_code))
        for role, label in (("identity_answer", "answer"), ("speech_text", "speech_text")):
            run(f"independent_partial_identity_code_words_{label}", lambda role=role: missing_identity_speech(identity_code_fixture, canonical_identity_code, roles[role]))

    def inactive_identity_event(input_fixture, speech, event):
        state = current_identity_state(input_fixture, roles["speech_text"], speech)
        state[roles["decision_event"]] = event
        forbidden = (offer, *readbacks, *record_nodes, *security.get("account_nodes", []), *(identifier for identifier, _ in verification_requests))
        state, target = advance(decision, state, forbidden)
        assert_denied(state)
        if nodes[target].get("node_type") != "conversation" or not nodes[target].get("extraction_schema"):
            raise ValueError("inactive identity answer event must return to a real listener")
    for index, question in enumerate(questions):
        kind = question["kind"]
        input_fixture = identity_answer_fixture if kind == "date" else identity_code_fixture if kind == "numeric_code" else question["fixture"]
        field = roles["speech_text"] if kind == "numeric_code" else roles["identity_answer"]
        expected_answer = input_fixture[field]
        run(f"independent_required_identity_question_{index}", lambda input_fixture=input_fixture, field=field, expected_answer=expected_answer, question=question: identity_request_boundary(current_identity_state(input_fixture, field, expected_answer), expected_answer, question["request_context"], question["kind"]))
        if kind == "text":
            run(f"independent_missing_identity_text_speech_{index}", lambda input_fixture=input_fixture, expected_answer=expected_answer: missing_identity_speech(input_fixture, expected_answer))
            for label, event in (("empty", ""), ("unknown", "__unrecognized_event__"), ("question", events["question"])):
                run(f"independent_identity_text_{index}_{label}_event_blocks_verification", lambda input_fixture=input_fixture, expected_answer=expected_answer, event=event: inactive_identity_event(input_fixture, expected_answer, event))
    event_probes = []
    if "date" in identity_kinds:
        event_probes.append(("date", identity_answer_fixture, f"{day.day} {month} {day.year:04d}."))
    if "numeric_code" in identity_kinds:
        event_probes.append(("code", identity_code_fixture, canonical_identity_code + "."))
    for kind, input_fixture, speech in event_probes:
        for label, event in (("empty", ""), ("unknown", "__unrecognized_event__"), ("question", events["question"])):
            run(f"independent_identity_{kind}_{label}_event_blocks_verification", lambda input_fixture=input_fixture, speech=speech, event=event: inactive_identity_event(input_fixture, speech, event))

    def latest_third_party(input_fixture=third_party_fixture):
        state = copy.deepcopy(input_fixture)
        bank_var = security.get("bank_verification_variable")
        state[bank_var] = "unverified"
        state[authorization] = ""
        state[roles["decision_event"]] = events["third_party"]
        state[roles["party_confirmation"]] = party_confirmed
        verification_nodes = [identifier for identifier, _ in verification_requests]
        forbidden = (offer, *readbacks, *record_nodes, *security.get("account_nodes", []), *verification_nodes)
        state, target = advance(decision, state, forbidden)
        assert_denied(state)
        if state.get(roles["party_confirmation"]) == party_confirmed or state.get(bank_var) == "verified":
            raise ValueError("latest third-party speech did not clear prior first-party confirmation")
        if nodes[target].get("node_type") == "api_request":
            bound_request(target, state)
    run("independent_latest_third_party_blocks_identity", latest_third_party)
    if "numeric_code" in identity_kinds:
        run("independent_latest_third_party_blocks_identity_code", lambda: latest_third_party(identity_code_fixture))
    for operation, action_gate in security.get("action_guards", {}).items():
        def empty_action(action_gate=action_gate):
            state = step(action_gate["node"], {})
            if state.get(action_gate["variable"]) == action_gate["operand"]:
                raise ValueError("action guard authorized without caller intent or validated inputs")
        run(f"independent_{operation}_missing_inputs", empty_action)

    def spoken(target, state):
        node = nodes[target]
        text = node.get("on_enter", {}).get("text", "")
        if node.get("node_type") == "end_call":
            text = node.get("terminal", {}).get("function", {}).get("parameters", {}).get("properties", {}).get("spoken_message", {}).get("default", "")
        def replace(match):
            value = state.get(match.group(1))
            if value in (None, ""):
                raise ValueError("spoken placeholder is empty or unset: " + match.group(1))
            return str(value)
        return re.sub(r'\{\{([\w.]+)(?::json)?\}\}', replace, text)

    # These fixtures are required only by sources with the observed negotiation rules.
    conversation_required = all(any(word in text.lower() for text in source_texts)
                                for word in ("minimum_payment", "restructuring", "support"))
    conversation = security.get("validation_conversation")
    if conversation_required or conversation is not None:
        fields = conversation.get("state", {}) if isinstance(conversation, dict) else {}
        if (not isinstance(fields, dict) or set(fields) != {"floor_offered", "support_offered", "minimum_amount"}
                or any(not isinstance(value, str) or value not in trusted for value in fields.values())
                or not all(isinstance(conversation.get(name), dict) and conversation[name]
                           for name in ("minimum_fixture", "support_fixture"))):
            reports.append({"name": "independent_conversation_contract", "ok": False,
                            "error": "source-required conversation checks need trusted state roles and minimum/support input fixtures"})
            return reports

        def current(base, event, text="", raw_date="", amount=""):
            state = copy.deepcopy(base)
            for field in decision_inputs:
                state[field] = ""
            state[roles["decision_event"]] = event
            state[roles["speech_text"]] = text
            state[roles["decision_date"]] = raw_date
            state[roles["decision_amount"]] = amount
            state[authorization] = ""
            return state

        def question(event, missing=False):
            base = conversation["minimum_fixture"]
            state, target = advance(decision, current(base, event, "" if missing else "What is the minimum payment?"),
                                    (offer, *readbacks, *record_nodes, *security["account_nodes"]))
            assert_denied(state)
            text = spoken(target, state)
            value = float(base[fields["minimum_amount"]])
            numbers = [float(number.replace(",", "")) for number in re.findall(r'\b[0-9]+(?:,[0-9]{3})*(?:\.[0-9]+)?\b', text)]
            if not missing and (value not in numbers or "?" in text):
                raise ValueError("minimum question must answer the bank amount without another offer")
            if missing and (numbers or re.search(r'\b(minimum|digital assistant|scam|asgari|dijital asistan|dolandırıcılık)\b', text, re.I)):
                raise ValueError("missing question text invented or reused question content")
            for field in (*fields.values(), roles["persuasion_attempts"]):
                if state.get(field) != base.get(field):
                    raise ValueError("question changed bank/once-only/persuasion state")
            # The same state with no current question cannot replay the consumed text.
            later, later_target = advance(decision, current(state, events["question"]),
                                           (offer, *readbacks, *record_nodes, *security["account_nodes"]))
            if re.search(r'\b(?:minimum|asgari)\b', spoken(later_target, later), re.I):
                raise ValueError("consumed minimum question was reused")

        for label, event in (("question", events["question"]), ("empty", ""), ("wrong", events["no"])):
            run("independent_minimum_answer_" + label, lambda event=event: question(event))
        run("independent_missing_question_text", lambda: question(events["question"], True))

        if security.get("confirmation_return_routes"):
            def missing_non_answer(text):
                base = conversation["minimum_fixture"]
                state, target = advance(decision, current(base, events.get("non_answer", "non_answer"), text),
                                        (offer, *readbacks, *record_nodes, *security["account_nodes"]))
                assert_denied(state)
                reply = spoken(target, state)
                if nodes[target].get("node_type") != "conversation" or not reply.strip() or re.search(r'\b[0-9]+\b', reply):
                    raise ValueError("missing non-answer text must ask for clarification without another payment offer")
                for field in (*fields.values(), *(roles[name] for name in ("proposed_amount", "proposed_date", "persuasion_attempts", "stage"))):
                    if state.get(field) != base.get(field):
                        raise ValueError("missing non-answer text changed proposal/once-only/persuasion state")
            for label, text in (("empty", ""), ("whitespace", " \t ")):
                run("independent_missing_non_answer_" + label, lambda text=text: missing_non_answer(text))

        def support_decline(event, text="I do not want a transfer. Can you reduce the amount?"):
            base = conversation["support_fixture"]
            state, target = advance(decision, current(base, event, text),
                (offer, *readbacks, *record_nodes, *security["account_nodes"]))
            assert_denied(state)
            text = spoken(target, state)
            if nodes[target].get("node_type") != "end_call" or identity_close_body(state) != {"outcome": "no_promise", "reason": "hardship"}:
                raise ValueError("current support decline was shadowed by a question/event")
            if "?" in text or state.get(fields["support_offered"]) != base.get(fields["support_offered"]):
                raise ValueError("declined support was offered again")
        for label, event in (("question", events["question"]), ("empty", ""), ("wrong", events["yes"])):
            run("independent_support_decline_" + label, lambda event=event: support_decline(event))
        run("independent_support_decline_polite_question", lambda: support_decline(events["question"], "No, thanks. Is there a discount?"))
        # Real PUB-05 passive wording; the event label must not shadow it.
        for label, event in (("question", events["question"]), ("empty", ""), ("wrong", events["yes"])):
            run("independent_support_decline_passive_" + label, lambda event=event: support_decline(event, "No, I do not want to be transferred. Can you just give me a discount?"))

        def plan(event, text, wanted, pre_identity=False):
            base = third_party_fixture if pre_identity else fixture
            state = current(base, event, text)
            if pre_identity:
                state[security["bank_verification_variable"]] = "unverified"
            state, target = advance(decision, state, (offer, *readbacks, *record_nodes, *security["account_nodes"]) if pre_identity else (*record_nodes,))
            assert_denied(state)
            requests = bound_request(target, state) if nodes[target].get("node_type") == "api_request" else []
            restructuring = any(name == "transfer_to_agent" and body.get("queue") == "restructuring" for name, body in requests)
            if restructuring != wanted or pre_identity and requests:
                raise ValueError("current plan intent violated the stage/transfer priority")
            if not wanted and nodes[target].get("node_type") == "conversation":
                spoken(target, state)
        for label, event in (("question", events["question"]), ("empty", ""), ("wrong", events["no"])):
            text = "I cannot pay that amount. I need lower instalments and a new payment plan."
            run("independent_mixed_plan_" + label, lambda event=event, text=text: plan(event, text, True))
            run("independent_pre_identity_mixed_plan_" + label, lambda event=event, text=text: plan(event, text, False, True))
        for label, text in (("negated", "I do not want a new payment plan."),
                            ("contraction", "I don't want a plan."), ("paying", "I plan to pay on Friday.")):
            run("independent_plan_" + label, lambda text=text: plan(events["plan"], text, False))
        # A declined instalment object is not a restructuring request under any label.
        for label, event in (("plan", events["plan"]), ("question", events["question"]), ("empty", ""), ("no", events["no"])):
            run("independent_plan_lower_instalments_declined_" + label, lambda event=event: plan(event, "I do not want lower instalments.", False))

        def mixed_ai(event):
            raw = f"the {payment_ordinal_day} of {payment_month}"
            state = current(fixture, event, f"I can pay {full_amount} dollars on {raw}. Are you a robot?", raw, str(full_amount))
            state, target = advance(decision, state)
            assert_denied(state)
            if target not in readbacks or not state.get(roles["offer_fingerprint"]) or state.get(roles["readback_fingerprint"]) != state[roles["offer_fingerprint"]]:
                raise ValueError("mixed AI offer did not reach a current matching readback")
            if not has_ai_answer(spoken(target, state)):
                raise ValueError("AI answer disappeared while keeping the current offer")
            record_amount(state, full_amount, proposal_day.isoformat())
        for label, event in (("offer", events["yes"]), ("question", events["question"]), ("empty", "")):
            run("independent_ai_with_current_offer_" + label, lambda event=event: mixed_ai(event))

        if security.get("confirmation_return_routes"):
            # Source-compiled drafts must also pass raw replies beyond model event labels.
            def raw_approval(state, event, text):
                state = copy.deepcopy(state)
                for field in approval_inputs:
                    state[field] = ""
                state[roles["approval_event"]] = event
                state[roles["approval_text"]] = text
                return state

            def raw_confirmation_denied(text, event=events["yes"], no_transfer=False):
                state, target = advance(approval, raw_approval(valid_readback(), event, text), (*record_nodes,))
                assert_denied(state)
                if no_transfer and nodes[target].get("node_type") == "api_request":
                    if any(name == "transfer_to_agent" for name, _ in bound_request(target, state)):
                        raise ValueError("current plan rejection authorized a transfer")
                spoken(target, state)

            for label, text in (("empty", ""), ("negative", "No, I do not confirm."),
                                ("question", "Could you tell me the minimum?"),
                                ("unable", "Yes, but I cannot pay."), ("past", "I said yes earlier."),
                                ("not_confirmed", "I have not confirmed."), ("uncertain", "Yes, maybe."),
                                ("unrelated_agreement", "I agree that this is your job.")):
                run("independent_raw_confirmation_" + label, lambda text=text: raw_confirmation_denied(text))
            for label, event in (("question", events["question"]), ("plan", events["plan"])):
                run("independent_raw_confirmation_plan_declined_" + label,
                    lambda event=event: raw_confirmation_denied("I do not want lower instalments.", event, True))

            def interrupted_confirmation(change=None):
                state, target = advance(approval, raw_approval(valid_readback(), events["question"], "Am I talking to a robot?"), (*record_nodes,))
                assert_denied(state)
                if not has_ai_answer(spoken(target, state)):
                    raise ValueError("confirmation question lost the sourced AI answer")
                amount = str(conversation["minimum_fixture"][fields["minimum_amount"]]) if change == "amount" else ""
                day = (proposal_day + datetime.timedelta(days=1)).isoformat() if change == "date" else ""
                text = f"Yes, change it to {amount or full_amount} on {day or proposal_day.isoformat()}." if change else "Yes, I confirm."
                state, target = advance(decision, current(state, events["yes"], text, day, amount), (*record_nodes,))
                assert_denied(state)
                if target not in readbacks or not state.get(roles["offer_fingerprint"]) or state.get(roles["readback_fingerprint"]) != state[roles["offer_fingerprint"]]:
                    raise ValueError("reply after a confirmation question did not reach a fresh matching readback")
                spoken(target, state)
                if change == "amount" and float(state.get(roles["proposed_amount"], 0)) != float(amount):
                    raise ValueError("corrected amount was lost before the fresh readback")
                expected_amount, expected_date = state[roles["proposed_amount"]], state[roles["proposed_date"]]
                state, target = confirm(state)
                if target not in record_nodes or state.get(authorization) != authorized:
                    raise ValueError("second explicit confirmation did not authorize the reread offer")
                if not any(name == "create_promise" and _json_equal(body.get(promise_fields["amount"]), expected_amount)
                           and body.get(promise_fields["date"]) == expected_date for name, body in bound_request(target, state)):
                    raise ValueError("second confirmation did not bind the current reread amount and date")

            for label in (None, "amount", "date"):
                run("independent_confirmation_question_return_" + (label or "yes"),
                    lambda label=label: interrupted_confirmation(label))

            def raw_ai_offer(kind):
                raw = f"the {payment_ordinal_day} of {payment_month}"
                day = "the week after next" if kind == "vague" else raw
                amount = str(float(conversation["minimum_fixture"][fields["minimum_amount"]]) / 2) if kind == "invalid" else ""
                text = f"I can pay {amount + ' dollars ' if amount else ''}on {day}. Am I talking to a robot?"
                state, target = advance(decision, current(fixture, "offer", text, day, amount), (*record_nodes,))
                assert_denied(state)
                if not has_ai_answer(spoken(target, state)):
                    raise ValueError("current AI answer disappeared on the final offer or clarification path")

            for kind in ("current", "vague", "invalid"):
                run("independent_raw_ai_offer_" + kind, lambda kind=kind: raw_ai_offer(kind))

            def longer_current_confirmation():
                state = valid_readback()
                amount, day = state[roles["proposed_amount"]], state[roles["proposed_date"]]
                state, target = advance(approval, raw_approval(state, events["yes"], "Yes, please record that payment promise. Thank you."))
                if target not in record_nodes or state.get(authorization) != authorized:
                    raise ValueError("clear current consent did not authorize the readback promise")
                if not any(name == "create_promise" and _json_equal(body.get(promise_fields["amount"]), amount)
                           and body.get(promise_fields["date"]) == day for name, body in bound_request(target, state)):
                    raise ValueError("clear current consent changed the readback promise")
            run("independent_raw_confirmation_longer_current_yes", longer_current_confirmation)

            def turkish_confirmation(text, accepted):
                state = valid_readback()
                amount, day = state[roles["proposed_amount"]], state[roles["proposed_date"]]
                state, target = advance(approval, raw_approval(state, events["yes"], text), () if accepted else (*record_nodes,))
                if not accepted:
                    assert_denied(state)
                    return
                if target not in record_nodes or state.get(authorization) != authorized:
                    raise ValueError("clear current Turkish consent did not authorize the readback promise")
                if not any(name == "create_promise" and _json_equal(body.get(promise_fields["amount"]), amount)
                           and body.get(promise_fields["date"]) == day for name, body in bound_request(target, state)):
                    raise ValueError("Turkish consent changed the current readback promise")
            for label, text, accepted in (("yes", "Evet, onaylıyorum. Teşekkürler.", True),
                                          ("no", "Hayır, onaylamıyorum.", False),
                                          ("conditional", "Evet, maaşım yatarsa.", False),
                                          ("past", "Daha önce evet dedim.", False),
                                          ("question", "Evet, ama tarihi değiştirebilir miyiz?", False)):
                run("independent_raw_turkish_confirmation_" + label,
                    lambda text=text, accepted=accepted: turkish_confirmation(text, accepted))

            def turkish_payment_date(current_input):
                month = ("Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran", "Temmuz", "Ağustos", "Eylül", "Ekim", "Kasım", "Aralık")[proposal_day.month - 1]
                raw = f"{proposal_day.day} {month} {proposal_day.year}"
                state = full_amount_state(events["yes"], str(full_amount)) if current_input else copy.deepcopy(fixture)
                state[roles["decision_date"] if current_input else roles["proposed_date"]] = raw
                expected = full_amount if current_input else float(fixture[roles["proposed_amount"]])
                record_amount(valid_readback(state, decision if current_input else offer), expected, proposal_day.isoformat())
            for label, current_input in (("current", True), ("shared", False)):
                run("independent_turkish_payment_date_" + label,
                    lambda current_input=current_input: turkish_payment_date(current_input))

            def non_agent_robot_question():
                base = conversation["minimum_fixture"]
                state, target = advance(decision, current(base, events["question"], "What is the minimum payment for my robot vacuum purchase?"),
                                        (offer, *readbacks, *record_nodes, *security["account_nodes"]))
                assert_denied(state)
                text = spoken(target, state)
                numbers = [float(number.replace(",", "")) for number in re.findall(r'\b[0-9]+(?:,[0-9]{3})*(?:\.[0-9]+)?\b', text)]
                if float(base[fields["minimum_amount"]]) not in numbers or has_ai_answer(text):
                    raise ValueError("non-agent robot question replaced the sourced minimum answer with an AI disclosure")
            run("independent_raw_non_agent_robot_minimum", non_agent_robot_question)

        def skipped_code():
            fallback = security.get("code_failure_node")
            if fallback not in nodes:
                raise ValueError("code_failure_node must name a literal retry listener")
            listener = nodes[fallback]
            transitions = listener.get("transitions", [])
            if (listener.get("node_type") != "conversation" or not listener.get("extraction_schema")
                    or listener.get("tools") or "{{" in spoken(fallback, {}) or not spoken(fallback, {}).strip()
                    or len(transitions) != 1 or transitions[0].get("target_node") != decision
                    or transitions[0].get("condition") != {"operator": "always"}):
                raise ValueError("code timeout fallback must collect fresh speech without variables/tools")
            for name, node in nodes.items():
                if node.get("node_type") != "code":
                    continue
                transitions = node.get("transitions", [])
                if (node.get("passthrough_default_transition") != fallback or not transitions
                        or transitions[-1].get("target_node") != fallback
                        or transitions[-1].get("condition") != {"operator": "always"}):
                    raise ValueError("skipped code must reach the literal retry listener: " + name)
                if node.get("max_turn_transition", fallback) != fallback:
                    raise ValueError("code max-turn path bypassed safe retry")
            # No snippet is run: the first decision has neither route nor question state.
            target = next_node(decision, {})
            if target != fallback:
                raise ValueError("first code timeout reached an action or uninitialized listener")
        run("independent_first_code_timeout", skipped_code)

        def normal_close():
            state, target = confirm(valid_readback())
            state, target = complete_record(target, state, {"status": "success", "status_code": 200, "data": {"ok": True}})
            text = spoken(target, state)
            if nodes[target].get("node_type") == "conversation":
                state, target = advance(decision, current(state, events["no"], "No, thank you. Goodbye."), (*record_nodes,))
                text += " " + spoken(target, state)
            if nodes[target].get("node_type") != "end_call":
                raise ValueError("normal post-record refusal did not reach a resolved farewell")
            sms = "You will receive a text message confirming this promise."
            if any(sms in line for line in source_texts) and sms not in text:
                raise ValueError("successful bank record lost the source-required SMS sentence")
        run("independent_success_close_resolves", normal_close)
    return reports


def _service_types(schema, document):
    schema = _resolve(schema, document)
    types = {schema['type']} if isinstance(schema.get('type'), str) else set()
    for key in ('anyOf', 'oneOf'):
        for choice in schema.get(key, []):
            types.update(_service_types(choice, document))
    for choice in schema.get('allOf', []):
        choice_types = _service_types(choice, document)
        if choice_types:
            intersection = types & choice_types
            if not intersection and ('number' in types and 'integer' in choice_types or 'integer' in types and 'number' in choice_types):
                intersection = {'integer'}
            types = intersection if types else choice_types
    return types


def _service_properties(schema, document):
    """Keep the intersection of allOf constraints when traversing body fields."""
    schema = _resolve(schema, document)
    properties = dict(schema.get('properties', {}))
    required = set(schema.get('required', []))
    for choice in schema.get('allOf', []):
        fields, demanded = _service_properties(choice, document)
        required.update(demanded)
        for name, child in fields.items():
            properties[name] = {'allOf': [properties[name], child]} if name in properties else child
    return properties, required


def _service_body(properties, state):
    import json
    def value(spec):
        if 'default' in spec:
            raw = spec['default']
            match = PLACEHOLDER.fullmatch(raw) if isinstance(raw, str) else None
            if match:
                if match.group(1) not in state:
                    raise ValueError('unresolved API variable ' + match.group(1))
                raw = state[match.group(1)]
                if spec.get('type') in ('object', 'array') and isinstance(raw, str):
                    raw = json.loads(raw)
            return copy.deepcopy(raw)
        if spec.get('type') == 'object' and isinstance(spec.get('properties'), dict):
            return {name: value(child) for name, child in spec['properties'].items()}
        raise ValueError('API request field has no baked value')
    return {name: value(spec) for name, spec in properties.items()}


def _service_path(value, path):
    for part in path.split('.'):
        if not isinstance(value, dict) or part not in value:
            return None
        value = value[part]
    return value


def _validate_service(workflow, policy, openapi, checks, brief_lines):
    """Validate input-derived service actions without inventing collections roles."""
    errors, reports, snippets, incoming, api_nodes = [], [], {}, {}, {}
    def fail(message):
        errors.append(message)
    security = policy.get('security', {})
    nodes = workflow.get('nodes', {})
    if not isinstance(security, dict) or not isinstance(nodes, dict) or not nodes:
        raise ValueError('Service needs security metadata and a nonempty nodes object')
    if workflow.get('global_nodes') or workflow.get('tools') or workflow.get('test_variables'):
        fail('Service globals, lifecycle tools and test_variables must be empty; use fresh guarded engine actions')
    errors.extend('null value: ' + path for path in _null_paths(workflow))
    context, trusted = security.get('context_variables', []), security.get('trusted_variables', [])
    if (not isinstance(context, list) or not context or not isinstance(trusted, list) or not trusted
            or any(not isinstance(field, str) or not field for field in [*context, *trusted])):
        raise ValueError('Service context_variables and trusted_variables need literal nonempty names')
    context, trusted = set(context), set(trusted)
    customer_field, customer_variable = security.get('customer_id_field'), security.get('customer_id_variable')
    if not isinstance(customer_field, str) or not customer_field or customer_variable not in context:
        fail('Service customer identifier must bind a supplied trusted call input')
    effects = policy.get('service_operations', {})
    gates, results = security.get('action_guards', {}), security.get('api_results', {})
    context_bindings = security.get('context_bindings', {customer_field: customer_variable})
    if not isinstance(context_bindings, dict) or any(not isinstance(path, str) or not path or variable not in context for path, variable in context_bindings.items()):
        fail('Service context_bindings must map sourced request paths to trusted call input variables')
    rules = {rule.get('id') for rule in policy.get('source_rules', []) if isinstance(rule, dict)}
    if not rules or policy.get('unsupported') != []:
        fail('Service needs source rule evidence and no unsupported requirements')
    if not all(isinstance(value, dict) for value in (effects, gates, results)):
        raise ValueError('Service operations, action guards and API results must be objects')
    base = openapi['servers'][0]['url'].rstrip('/')
    operations = {}
    for path, item in openapi['paths'].items():
        for method, raw in _resolve(item, openapi).items():
            if method.lower() not in ('get', 'post', 'put', 'patch', 'delete'):
                continue
            operation = _resolve(raw, openapi)
            name = operation.get('operationId', path.strip('/').replace('/', '_'))
            request = _resolve(operation.get('requestBody', {}), openapi)
            schema = _resolve(request.get('content', {}).get('application/json', {}).get('schema', {'type': 'object', 'properties': {}}), openapi)
            operations[name] = (base + path, method.upper(), schema, operation)
    if not operations:
        fail('Service OpenAPI contains no supported operations')
    for name, effect in effects.items():
        if name not in operations or not isinstance(effect, dict) or effect.get('effect') not in ('read', 'write', 'transfer') or effect.get('source_rule') not in rules:
            fail('Service operation needs a sourced effect: ' + name)
    extracted = set()
    for name, node in nodes.items():
        incoming[name] = []
        if not isinstance(node, dict) or node.get('name') != name or node.get('node_type') not in ('conversation', 'code', 'api_request', 'end_call'):
            fail(name + ': invalid service node')
            continue
        kind = node['node_type']
        transitions = node.get('transitions', [])
        if not isinstance(transitions, list):
            raise ValueError(name + ': transitions must be a list')
        if kind in ('code', 'api_request') and (not node.get('passthrough') or not transitions or transitions[-1].get('condition') != {'operator': 'always'}):
            fail(name + ': engine node needs passthrough and final always fallback')
        if kind == 'conversation':
            if node.get('pre_actions') or node.get('tools') or node.get('passthrough') or len(transitions) != 1 or transitions[0].get('condition') != {'operator': 'always'} or nodes.get(transitions[0].get('target_node'), {}).get('node_type') != 'code':
                fail(name + ': listener must have one always transition to code and no tools')
            if node.get('on_enter', {}).get('type') != 'tts' or not node.get('on_enter', {}).get('text'):
                fail(name + ': listener needs fixed TTS')
        for field in node.get('extraction_schema', []):
            variable = field.get('name')
            extracted.add(variable)
            if (not isinstance(variable, str) or not variable or variable in context | trusted
                    or field.get('type') != 'string' or field.get('min_confidence') != 0 or field.get('max_retries') != 1
                    or field.get('validation_pattern') or field.get('format') or 'enum' in field and '' not in field['enum']):
                fail(name + ': extraction must be untrusted, blankable and optional')
        if node.get('tools'):
            fail(name + ': model-visible tools are unavailable')
        actions = node.get('pre_actions', [])
        if kind in ('code', 'api_request') and len(actions) != 1:
            fail(name + ': engine node needs exactly one action')
        for tool in actions:
            function = tool.get('function', {})
            handler, operation = function.get('handler'), function.get('name')
            properties = function.get('parameters', {}).get('properties', {})
            if not isinstance(function.get('description'), str) or not function['description'].strip():
                fail(name + ': action needs description')
            if handler == '__function__:code_exec' and kind == 'code':
                snippets[name] = (properties.get('code', {}).get('default'), None, None)
            elif handler == '__function__:api_call' and kind == 'api_request':
                if operation not in operations or operation not in effects:
                    fail(name + ': API action needs a real OpenAPI operation and sourced effect')
                    continue
                url, method, schema, _ = operations[operation]
                if properties.get('url', {}).get('default') != url or properties.get('method', {}).get('default') != method:
                    fail(name + ': wrong API URL or method')
                if tool.get('pre_process_code'):
                    fail(name + ': API request must already be validated before entry')
                if tool.get('config', {}).get('maxRetries') != 0 or properties.get('connect_retries', {}).get('default') != 0:
                    fail(name + ': service actions need zero automatic retries')
                body = properties.get('body', {})
                fields = body.get('properties', {})
                def request_fields(schema, provided, required, prefix=''):
                    schema = _resolve(schema, openapi)
                    for field in schema.get('required', []):
                        if field not in provided or field not in required:
                            fail(name + ': missing required request field ' + prefix + field)
                    for field, spec in provided.items():
                        expected = _resolve(schema.get('properties', {}).get(field, {}), openapi)
                        value = spec.get('default')
                        match = PLACEHOLDER.fullmatch(value) if isinstance(value, str) else None
                        if not expected or spec.get('type') not in _service_types(expected, openapi) or 'const' in spec:
                            fail(name + ': unsupported request field ' + prefix + field)
                        if spec.get('type') == 'object' and 'default' not in spec and isinstance(spec.get('properties'), dict):
                            request_fields(expected, spec['properties'], spec.get('required', []), prefix + field + '.')
                        elif 'default' not in spec:
                            fail(name + ': unbound request field ' + prefix + field)
                        if 'enum' in expected and (set(spec.get('enum', [])) != set(expected['enum']) or not match and value not in expected['enum']):
                            fail(name + ': invalid request enum ' + prefix + field)
                        if match and match.group(1) not in context | trusted:
                            fail(name + ': API body may not bind raw speech or unknown variables')
                        path = prefix + field
                        if path in context_bindings and value != '{{' + str(context_bindings[path]) + '}}':
                            fail(name + ': call context must be bound unchanged at ' + path)
                        if expected.get('format') and spec.get('format') != expected['format']:
                            fail(name + ': wrong request format ' + path)
                request_fields(schema, fields, body.get('required', []))
                api_nodes[name] = operation
                if tool.get('post_process_code'):
                    snippets[name + ':' + operation + ':post'] = (tool['post_process_code'], operation, 'post')
                for mapping in tool.get('response_mapping', []) + node.get('response_mapping', []):
                    if (not mapping.get('path', '').startswith('data.') or mapping.get('variable') not in trusted or mapping.get('variable') in context
                            or mapping.get('variable') in {gate.get('variable') for gate in gates.values() if isinstance(gate, dict)}
                            or mapping.get('variable') in {result.get('success_variable') for result in results.values() if isinstance(result, dict)}):
                        fail(name + ': response mappings may write sourced bank state only')
            else:
                fail(name + ': unsupported engine action')
        if kind == 'end_call':
            function = node.get('terminal', {}).get('function', {})
            parameters = function.get('parameters', {}).get('properties', {})
            if transitions or actions or function.get('handler') != '__function__:end_call' or parameters.get('message_mode', {}).get('default') != 'custom' or not parameters.get('spoken_message', {}).get('default'):
                fail(name + ': terminal needs a fixed end_call farewell')
    for source, node in nodes.items():
        targets = [(item.get('target_node'), item.get('condition')) for item in node.get('transitions', [])]
        targets += [(node[key], {'operator': 'always'}) for key in ('passthrough_default_transition', 'max_turn_transition') if node.get(key)]
        for target, condition in targets:
            if target not in nodes:
                fail(source + ': unknown route ' + str(target))
            else:
                incoming[target].append((source, condition))
    initial = workflow.get('initial_node')
    if nodes.get(initial, {}).get('node_type') != 'conversation' or '{{' in nodes.get(initial, {}).get('on_enter', {}).get('text', ''):
        fail('Service must start with a literal conversation opening')
    edges = {name: {target for target, _ in [(item.get('target_node'), item.get('condition')) for item in node.get('transitions', [])]} for name, node in nodes.items()}
    unreachable = set(nodes) - _reachable(edges, [initial])
    if unreachable:
        fail('Service nodes unreachable from opening: ' + ', '.join(sorted(unreachable)))
    authorizations = {gate.get('variable'): gate for gate in gates.values() if isinstance(gate, dict)}
    response_prefixes = {name + '_response': result for name, result in results.items() if isinstance(result, dict)}
    if any(field == prefix or field.startswith(prefix + '.') for field in context | trusted | extracted for prefix in response_prefixes):
        fail('Service engine response namespaces may not be model, bank-mapping or call-context variables')
    for identifier, (code, operation, hook) in snippets.items():
        try:
            tree = _parse(code)
            writes = _writes(tree)
            if writes & context:
                fail(identifier + ': code may not overwrite trusted call context')
            lines = code.splitlines()
            owned_lines = set()
            owned_sections = set()
            for name, gate in gates.items():
                if gate.get('node') == identifier:
                    owned_sections.update({'SERVICE INPUT ' + name, 'SERVICE OUTPUT ' + name})
            for name, result in results.items():
                if result.get('entry_node') == identifier:
                    owned_sections.add('SERVICE RESET ' + name)
                if result.get('result_node') == identifier:
                    owned_sections.update({'SERVICE RESULT INPUT ' + name, 'SERVICE RESULT OUTPUT ' + name})
            language_fields = security.get('language_input', {})
            if isinstance(language_fields, dict) and any(identifier in language_fields.get(key, {}) for key in ('date_fields', 'amount_fields')):
                owned_sections.add('SERVICE LANGUAGE INPUT')
            inside = None
            for number, line in enumerate(lines, 1):
                if line.startswith('# BEGIN KAAN '):
                    section = line[len('# BEGIN KAAN '):]
                    if section not in owned_sections or inside:
                        fail(identifier + ': unexpected compiler-owned code section')
                    inside = section if section in owned_sections else None
                if inside:
                    owned_lines.add(number)
                if line.startswith('# END KAAN '):
                    if line[len('# END KAAN '):] != inside:
                        fail(identifier + ': invalid compiler-owned code section')
                    inside = None
            if inside:
                fail(identifier + ': unclosed compiler-owned code section')
            for assignment in ast.walk(tree):
                reserved = (assignment.id if isinstance(assignment, ast.Name) else assignment.name if isinstance(assignment, (ast.FunctionDef, ast.AsyncFunctionDef))
                            else assignment.arg if isinstance(assignment, ast.arg) else assignment.asname if isinstance(assignment, ast.alias) else None)
                if isinstance(reserved, str) and reserved.startswith('_service_') and assignment.lineno not in owned_lines:
                    fail(identifier + ': generated code may not access compiler-owned result snapshots or reserved helper names')
            for variable in writes:
                for prefix, result in response_prefixes.items():
                    if variable == prefix or variable.startswith(prefix + '.'):
                        for value in _authorization_values(tree, variable):
                            if (identifier != result.get('entry_node') or not isinstance(value, ast.Constant)
                                    or value.value != '' or value.lineno not in owned_lines):
                                fail(identifier + ': engine response evidence is read-only outside its source-owned reset')
            for variable, gate in authorizations.items():
                if identifier != gate.get('node'):
                    for value in _authorization_values(tree, variable):
                        if not isinstance(value, ast.Constant) or value.value == gate.get('operand'):
                            fail(identifier + ': only its source guard may authorize an action')
            for result in results.values():
                if identifier != result.get('result_node'):
                    for value in _authorization_values(tree, result.get('success_variable')):
                        if not isinstance(value, ast.Constant) or value.value == result.get('success_operand'):
                            fail(identifier + ': only current result classifier may mark success')
        except (ValueError, SyntaxError, TypeError) as exc:
            fail(identifier + ': invalid Python: ' + str(exc))
    for name, node in nodes.items():
        if node.get('node_type') == 'code':
            fallback = node.get('passthrough_default_transition')
            target = nodes.get(fallback, {})
            if (target.get('node_type') != 'conversation' or '{{' in target.get('on_enter', {}).get('text', '')
                    or not target.get('on_enter', {}).get('text') or target.get('tools')):
                fail(name + ': code timeout must reach a literal retry listener')
    language = security.get('language_input', {})
    if not isinstance(language, dict):
        fail('Service language_input must be an object')
    else:
        date_fields, amount_fields = language.get('date_fields', {}), language.get('amount_fields', {})
        if not isinstance(date_fields, dict) or not isinstance(amount_fields, dict):
            fail('Service language fields must map real code nodes to raw speech fields')
        else:
            if date_fields and language.get('now_variable') not in context:
                fail('Service date anchor must be an immutable supplied call-context variable')
            for node, fields in [*date_fields.items(), *amount_fields.items()]:
                if nodes.get(node, {}).get('node_type') != 'code' or not isinstance(fields, list) or any(field not in extracted for field in fields):
                    fail('Service language normalization must bind real code nodes and actual raw speech fields')
    for name, gate in gates.items():
        if not isinstance(gate, dict) or effects.get(name, {}).get('effect') not in ('write', 'transfer'):
            fail('Service action guard names a non-mutating operation: ' + name)
            continue
        node, target, variable, operand = (gate.get(key) for key in ('node', 'target', 'variable', 'operand'))
        if node not in snippets or nodes.get(node, {}).get('node_type') != 'code' or api_nodes.get(target) != name or variable not in trusted or not isinstance(operand, str) or not operand or gate.get('source_rule') not in rules:
            fail(name + ': action guard needs real code, action, trusted authorization and source evidence')
        if effects[name]['effect'] == 'write' and gate.get('consent_required', True) is not True:
            fail(name + ': a mutating service action requires current customer consent')
        if gate.get('consent_required', True):
            if any(gate.get(key) not in extracted for key in ('text_field', 'event_field')) or not isinstance(gate.get('fixture'), dict) or not isinstance(gate.get('valid_text'), str) or not gate['valid_text'].strip():
                fail(name + ': current consent needs actual speech fields and a synthetic valid fixture')
        entries = incoming.get(target, [])
        if len(entries) != 1 or entries[0][0] != node or not _exact_guard(entries[0][1], variable, operand):
            fail(name + ': action must have one exact authorization edge from its guard')
        if gate.get('confirmation_required'):
            readbacks = gate.get('confirmation_nodes', [])
            if not readbacks or any(nodes.get(item, {}).get('node_type') != 'conversation' for item in readbacks) or node in _reachable(edges, [initial], readbacks):
                fail(name + ': confirmation guard is reachable before a fresh readback')
            if any(gate.get(key) not in trusted for key in ('fingerprint_variable', 'readback_fingerprint_variable')):
                fail(name + ': confirmed request needs matching trusted payload and readback fingerprints')
            if not isinstance(gate.get('consent_phrases', []), list) or any(not isinstance(phrase, str) or not phrase.strip() for phrase in gate.get('consent_phrases', [])):
                fail(name + ': additional confirmation phrases must come from the sourced action vocabulary')
        if not isinstance(gate.get('value_fields', []), list) or any(field not in extracted for field in gate.get('value_fields', [])):
            fail(name + ': changed value fields must be actual fresh speech fields')
    result_nodes = [result.get('result_node') for result in results.values() if isinstance(result, dict)]
    if len(result_nodes) != len(set(result_nodes)):
        fail('Service API actions need separate current-result code nodes; one classifier may not process multiple API responses')
    for node, operation in api_nodes.items():
        if effects[operation]['effect'] != 'read' and gates.get(operation, {}).get('target') != node:
            fail(node + ': mutating action has no declared guard')
        result = results.get(node, {})
        if (not isinstance(result, dict) or result.get('entry_node') not in snippets or result.get('result_node') not in snippets
                or nodes.get(result.get('entry_node'), {}).get('node_type') != 'code' or nodes.get(result.get('result_node'), {}).get('node_type') != 'code'
                or result.get('entry_node') == result.get('result_node') or result.get('success_variable') not in trusted
                or not isinstance(result.get('success_operand'), str) or not result.get('success_operand')
                or result.get('route_variable') not in trusted or result.get('speech_variable') not in trusted
                or not isinstance(result.get('failure_route'), str) or not isinstance(result.get('failure_text'), str) or not result['failure_text'].strip()
                or not isinstance(result.get('fixture'), dict) or not isinstance(result.get('success_result'), dict)
                or not isinstance(result.get('required_response_fields'), list) or not isinstance(result.get('success_statuses'), list) or not result['success_statuses']):
            fail(node + ': API needs a failure-safe current-result classifier, source-shaped fixture and honest fallback')
            continue
        response_codes = operations[operation][3].get('responses', {})
        if any(str(status) not in response_codes or not str(status).startswith('2') for status in result['success_statuses']):
            fail(node + ': success HTTP status is absent from the supplied API')
        if not incoming.get(node) or any(source != result['entry_node'] for source, _ in incoming[node]):
            fail(node + ': API must enter through its response-reset code')
        transitions = nodes[node].get('transitions', [])
        if len(transitions) != 1 or transitions[0].get('target_node') != result['result_node'] or transitions[0].get('condition') != {'operator': 'always'}:
            fail(node + ': every API success/error must reach its own result code')
        business = result.get('business_success')
        if business is not None and (not isinstance(business, dict) or not isinstance(business.get('path'), str) or not business['path'].startswith('data.') or 'operand' not in business):
            fail(node + ': business success must use a sourced body property')
        source_business = operations[operation][3].get('x-business-success')
        if source_business:
            expected_business = {'path': 'data.' + source_business['path'], 'operand': source_business['operand']}
            if not _json_equal(business, expected_business):
                fail(node + ': business success must preserve the supplied source-contract success condition')
        def source_response_path(path, statuses):
            if not isinstance(path, str) or not path.startswith('data.'):
                return False
            for status in statuses:
                response = _resolve(response_codes.get(str(status), {}), openapi)
                schema = response.get('content', {}).get('application/json', {}).get('schema', {})
                for part in path[5:].split('.'):
                    fields, _ = _service_properties(schema, openapi)
                    schema = fields.get(part, {})
                if not schema:
                    return False
            return True
        if not result['required_response_fields'] and not business:
            fail(node + ': success requires a sourced body flag or required response fields')
        for path in result['required_response_fields']:
            if not source_response_path(path, result['success_statuses']):
                fail(node + ': required response field is absent from the successful API schema: ' + str(path))
        if isinstance(business, dict) and not source_response_path(business.get('path'), result['success_statuses']):
            fail(node + ': business success field is absent from the successful API schema')
        if result.get('response_prefix', node + '_response') != node + '_response':
            fail(node + ': API response prefix must use the real engine node identifier')
        if result.get('entry_node') != gates.get(operation, {}).get('node') and effects[operation]['effect'] != 'read':
            fail(node + ': mutating action response reset must be in its consent guard')
        if not isinstance(result.get('error_outcomes', []), list):
            fail(node + ': sourced error outcomes must be an array')
        for error in result.get('error_outcomes', []):
            if (not isinstance(error, dict) or str(error.get('status')) not in response_codes
                    or not isinstance(error.get('path'), str) or not error['path'].startswith('data.')
                    or 'operand' not in error or not isinstance(error.get('route'), str)
                    or not isinstance(error.get('speech'), str) or not error['speech'].strip() or error.get('source_rule') not in rules):
                fail(node + ': known error outcome needs source status, body code and honest sourced route/speech')
            elif not source_response_path(error['path'], [error['status']]) or str(error['status']).startswith('2'):
                fail(node + ': known error code is absent from the supplied error response schema')
    if set(results) != set(api_nodes):
        fail('Service api_results must cover exactly the actual API nodes')
    if not isinstance(checks, list) or not checks:
        fail('Service needs generated runnable control checks')
        checks = []
    for check in checks:
        identifier = check.get('node_id') if isinstance(check, dict) else None
        report = {'name': check.get('name', '') if isinstance(check, dict) else '', 'node_id': identifier, 'ok': False}
        try:
            if identifier not in snippets or not isinstance(check.get('vars'), dict) or not isinstance(check.get('expected'), dict) or not check['expected'] or not any(key in trusted for key in check['expected']):
                raise ValueError('Service check must execute real code and assert a trusted control')
            _run_check(snippets[identifier][0], check)
            report['ok'] = True
        except (ValueError, TypeError, KeyError, EOFError) as exc:
            report['error'] = str(exc)
            fail('check ' + report['name'] + ': ' + str(exc))
        reports.append(report)
    def probe(name, node, state, expected):
        report = {'name': name, 'node_id': node, 'ok': False}
        try:
            output = _run_check(snippets[node][0], {'vars': state, 'expected': {}})['vars']
            expected(output)
            report['ok'] = True
        except (ValueError, TypeError, KeyError, EOFError) as exc:
            report['error'] = str(exc)
            fail('check ' + name + ': ' + str(exc))
        reports.append(report)
    def require(condition, message):
        if not condition:
            raise ValueError(message)
    def audible_result(identifier, state, expected):
        current = identifier
        for _ in range(len(nodes) + 1):
            node = nodes[current]
            if node.get('node_type') in ('conversation', 'end_call'):
                speech = (node.get('on_enter', {}).get('text', '') if node['node_type'] == 'conversation' else
                          node.get('terminal', {}).get('function', {}).get('parameters', {}).get('properties', {}).get('spoken_message', {}).get('default', ''))
                speech = re.sub(r'\{\{([\w.]+)\}\}', lambda match: str(state.get(match.group(1), '')), speech)
                require(expected in speech, 'failure graph did not speak the declared honest current-result outcome')
                return
            require(node.get('node_type') == 'code', 'failure graph reached another HTTP action before an honest outcome')
            if current != identifier:
                state = _run_check(snippets[current][0], {'vars': state, 'expected': {}})['vars']
            targets = [item['target_node'] for item in node.get('transitions', []) if _condition(item.get('condition', {}), state)]
            require(bool(targets), 'result graph has no matching route')
            current = targets[0]
        raise ValueError('failure graph loops before speaking its current outcome')
    if not errors:
        def check_request(node, state):
            tool = nodes[node]['pre_actions'][0]
            properties = tool['function']['parameters']['properties']['body']['properties']
            body = _service_body(properties, state)
            schema = operations[api_nodes[node]][2]
            def shape(value, schema):
                schema = _resolve(schema, openapi)
                allowed = _service_types(schema, openapi)
                actual = ('boolean' if isinstance(value, bool) else 'object' if isinstance(value, dict) else 'array' if isinstance(value, list)
                          else 'string' if isinstance(value, str) else 'integer' if isinstance(value, int) else 'number' if isinstance(value, float) else 'null')
                require(actual in allowed or actual == 'integer' and 'number' in allowed, 'resolved request value has wrong JSON type')
                if isinstance(value, dict):
                    require(all(field in value for field in schema.get('required', [])), 'resolved request omitted required fields')
                    for key, item in value.items():
                        require(key in schema.get('properties', {}), 'resolved request introduced unknown fields')
                        shape(item, schema['properties'][key])
                if isinstance(value, list):
                    for item in value:
                        shape(item, schema['items'])
                if 'enum' in schema:
                    require(any(_json_equal(value, expected) for expected in schema['enum']), 'resolved request value is outside the source enum')
                if actual in ('integer', 'number'):
                    require(-float('inf') < value < float('inf'), 'non-finite request number')
                    require('minimum' not in schema or value >= schema['minimum'], 'request number below source bound')
                    require('maximum' not in schema or value <= schema['maximum'], 'request number above source bound')
            shape(body, schema)
            for path, variable in context_bindings.items():
                declared = schema
                for part in path.split('.'):
                    declared = _resolve(declared, openapi).get('properties', {}).get(part, {})
                if declared:
                    require(_json_equal(_service_path(body, path), state.get(variable)), 'request changed or omitted trusted call context at ' + path)

        for name, gate in gates.items():
            if not gate.get('consent_required', True):
                continue
            text, event, authorization = gate['text_field'], gate['event_field'], gate['variable']
            valid = copy.deepcopy(gate['fixture'])
            valid[text] = gate['valid_text']
            probe('independent_service_' + name + '_current_consent', gate['node'], valid,
                  lambda output, gate=gate: require(output.get(gate['variable']) == gate['operand'], 'current valid consent did not authorize'))
            for label, raw in (('empty', ''), ('negative', 'Hayır, onaylamıyorum.'), ('question', 'Bu işlem ne yapar?'), ('uncertain', 'Belki, emin değilim.')):
                state = copy.deepcopy(valid)
                state[text] = raw
                probe('independent_service_' + name + '_' + label, gate['node'], state,
                      lambda output, gate=gate: require(output.get(gate['variable']) != gate['operand'], 'untrusted current reply authorized an action'))
            state = _run_check(snippets[gate['node']][0], {'vars': valid, 'expected': {}})['vars']
            probe('independent_service_' + name + '_consumed_reply', gate['node'], state,
                  lambda output, gate=gate: require(output.get(gate['variable']) != gate['operand'], 'consumed consent was reused'))
            if gate.get('confirmation_required'):
                changed = copy.deepcopy(valid)
                changed[gate['readback_fingerprint_variable']] = '__different_readback__'
                probe('independent_service_' + name + '_different_readback', gate['node'], changed,
                      lambda output, gate=gate: require(output.get(gate['variable']) != gate['operand'], 'changed readback authorized an action'))
                for field in gate.get('value_fields', []):
                    changed = copy.deepcopy(valid)
                    changed[field] = '__new_current_value__'
                    probe('independent_service_' + name + '_current_correction_' + field, gate['node'], changed,
                          lambda output, gate=gate: require(output.get(gate['variable']) != gate['operand'], 'current correction authorized an old action'))
        for node, result in results.items():
            prefix = result.get('response_prefix', node + '_response')
            def state_for(envelope, result=result, prefix=prefix):
                state = copy.deepcopy(result['fixture'])
                for field in list(state):
                    if field == prefix or field.startswith(prefix + '.'):
                        del state[field]
                state[result['success_variable']] = result['success_operand']
                def flatten(value, path):
                    state[path] = value
                    if isinstance(value, dict):
                        for key, item in value.items():
                            flatten(item, path + '.' + key)
                flatten(envelope, prefix)
                return state
            success = result['success_result']
            probe('independent_service_' + node + '_current_success', result['result_node'], state_for(success),
                  lambda output, result=result: require(output.get(result['success_variable']) == result['success_operand'], 'valid current API result did not succeed'))
            failures = {'missing': {}, 'transport_failure': {**success, 'status': 'error', 'status_code': 503, 'data': {}}}
            from builder.compiler import _service_schema_definition
            operation = operations[api_nodes[node]][3]
            def response_fields(schema, path=()):
                schema = _resolve(schema, openapi)
                fields, required = _service_properties(schema, openapi)
                for field, child in fields.items():
                    child = _resolve(child, openapi)
                    child_path = (*path, field)
                    yield child_path, child, field in required
                    yield from response_fields(child, child_path)
            response = _resolve(operation.get('responses', {}).get(str(success.get('status_code')), {}), openapi)
            source_schema = _service_schema_definition(response.get('content', {}).get('application/json', {}).get('schema', {}), openapi)
            for index, (path, spec, required) in enumerate(response_fields(source_schema)):
                target = success.get('data', {})
                for part in path[:-1]:
                    target = target.get(part, {}) if isinstance(target, dict) else {}
                if not isinstance(target, dict) or path[-1] not in target:
                    continue
                if required:
                    failed = copy.deepcopy(success)
                    parent = failed['data']
                    for part in path[:-1]:
                        parent = parent[part]
                    del parent[path[-1]]
                    failures['missing_required_' + str(index)] = failed
                types = _service_types(spec, openapi)
                if not types:
                    continue
                wrong = None if 'null' not in types and not spec.get('nullable') else {} if 'object' not in types else [] if 'array' not in types else '__wrong_type__'
                failed = copy.deepcopy(success)
                parent = failed['data']
                for part in path[:-1]:
                    parent = parent[part]
                parent[path[-1]] = wrong
                failures['malformed_field_' + str(index)] = failed
            business = result.get('business_success')
            if business:
                failed = copy.deepcopy(success)
                target = failed
                parts = business['path'].split('.')
                for part in parts[:-1]:
                    target = target.setdefault(part, {})
                target[parts[-1]] = False if business['operand'] is True else '__not_business_success__'
                failures['business_failure'] = failed
            for label, envelope in failures.items():
                def failed_outcome(output, result=result):
                    require(output.get(result['success_variable']) != result['success_operand'] and output.get(result['speech_variable']) == result['failure_text'], 'failure reused success or claimed a successful action')
                    audible_result(result['result_node'], output, result['failure_text'])
                probe('independent_service_' + node + '_' + label, result['result_node'], state_for(envelope),
                      failed_outcome)
            for index, error in enumerate(result.get('error_outcomes', [])):
                envelope = {'status': 'error', 'status_code': error['status']}
                target = envelope
                parts = error['path'].split('.')
                for part in parts[:-1]:
                    target = target.setdefault(part, {})
                target[parts[-1]] = error['operand']
                def error_outcome(output, result=result, error=error):
                    require(output.get(result['success_variable']) != result['success_operand']
                            and output.get(result['route_variable']) == error['route'] and output.get(result['speech_variable']) == error['speech'],
                            'known warning lost its sourced outcome or was claimed as success')
                    audible_result(result['result_node'], output, error['speech'])
                probe('independent_service_' + node + '_sourced_error_' + str(index), result['result_node'], state_for(envelope), error_outcome)
            entry = result['entry_node']
            operation = api_nodes[node]
            gate = gates.get(operation)
            state = copy.deepcopy(gate['fixture'] if gate and gate.get('consent_required', True) else result['fixture'])
            if gate and gate.get('consent_required', True):
                state[gate['text_field']] = gate['valid_text']
            for label, value in (('original_context', state.get(customer_variable)), ('changed_context', '88112233')):
                current = copy.deepcopy(state)
                current[customer_variable] = value
                probe('independent_service_' + node + '_' + label + '_request', entry, current,
                      lambda output, node=node: check_request(node, output))
    return {'ok': not errors, 'valid': not errors, 'errors': errors, 'checks': reports}


def validate(workflow, policy, openapi, checks, brief_lines=None):
    try:
        if isinstance(policy, dict) and policy.get('workflow_kind') == 'service':
            return _validate_service(workflow, policy, openapi, checks, brief_lines)
        return _validate(workflow, policy, openapi, checks, brief_lines)
    except (AttributeError, KeyError, TypeError, ValueError) as exc:
        return {"ok": False, "valid": False, "errors": [f"malformed generated data: {exc}"], "checks": []}


def _validate(workflow, policy, openapi, checks, brief_lines=None):
    """Return a JSON report; never execute a workflow API call."""
    errors, reports, snippets, api_entries = [], [], {}, []
    def fail(message):
        errors.append(message)
    if not all(isinstance(value, dict) for value in (workflow, policy, openapi)):
        return {"ok": False, "valid": False, "errors": ["workflow, policy and openapi must be objects"], "checks": []}
    errors.extend(f"null value: {path}" for path in _null_paths(workflow))
    nodes = workflow.get("nodes", {})
    globals_ = workflow.get("global_nodes", {})
    if not isinstance(nodes, dict) or not nodes or not isinstance(globals_, dict):
        return {"ok": False, "valid": False, "errors": errors + ["nodes must be a nonempty object; global_nodes an object"], "checks": []}
    if set(nodes) & set(globals_):
        fail("regular and global node IDs overlap")
    all_nodes = dict(nodes, **globals_)
    if workflow.get("initial_node") not in nodes:
        fail("initial_node must name a regular node")
    security = policy.get("security", {})
    if not isinstance(security, dict):
        security = {}
    required_lists = ("identity_nodes", "trusted_variables", "account_nodes", "record_nodes", "confirmation_nodes", "close_nodes")
    for key in required_lists:
        if not isinstance(security.get(key), list) or not security[key] or any(not isinstance(item, str) for item in security[key]):
            fail(f"security.{key} must be a nonempty string list")
    trusted = set(security.get("trusted_variables", []))
    bank_var = security.get("bank_verification_variable", "")
    customer_field = security.get("customer_id_field", "")
    customer_variable = security.get("customer_id_variable", "")
    if not isinstance(customer_field, str) or not customer_field or not isinstance(customer_variable, str) or not customer_variable:
        fail("security.customer_id_field and customer_id_variable must be strings")
    authorization = security.get("record_authorization_variable", "record_authorization")
    authorized = security.get("record_authorization_operand", "authorized")
    action_guards = security.get("action_guards", {})
    if not isinstance(action_guards, dict):
        fail("security.action_guards must be an object")
        action_guards = {}
    for name, action_gate in action_guards.items():
        if not isinstance(action_gate, dict) or all_nodes.get(action_gate.get("node"), {}).get("node_type") != "code" or action_gate.get("variable") not in trusted or not isinstance(action_gate.get("operand"), str) or not action_gate["operand"]:
            fail(f"security.action_guards.{name} needs a code node, trusted variable and operand")
    for variable in (bank_var, authorization):
        if not isinstance(variable, str) or not variable or variable not in trusted:
            fail(f"trusted_variables must include security control {variable!r}")
    for key in ("offer_guard_node", "approval_guard_node"):
        if all_nodes.get(security.get(key), {}).get("node_type") != "code":
            fail(f"security.{key} must name a code node")
    for key in required_lists:
        if key != "trusted_variables":
            for node_id in security.get(key, []):
                if node_id not in all_nodes:
                    fail(f"security.{key}: unknown node {node_id}")
                elif key == "confirmation_nodes" and all_nodes[node_id].get("node_type") != "conversation":
                    fail(f"security.{key}: {node_id} must be a conversation")
    if set(workflow.get("test_variables", {})) & trusted:
        fail("test_variables may not initialize trusted state")
    source_rules = policy.get("source_rules", [])
    if not isinstance(source_rules, list) or not source_rules:
        fail("policy needs source_rules evidence")
    else:
        for rule in source_rules:
            if not isinstance(rule, dict) or any(not isinstance(rule.get(key), str) or not rule[key] for key in ("id", "source", "text", "stage")) or type(rule.get("line")) is not int or rule["line"] < 1:
                fail("source_rules entries need id/source/line/text/stage evidence")
    if policy.get("unsupported") != []:
        fail("policy.unsupported must be an empty list before publishing")
    operations = {}
    try:
        base = openapi["servers"][0]["url"].rstrip("/")
        for path, path_item in openapi["paths"].items():
            for method, raw in _resolve(path_item, openapi).items():
                if method.lower() not in ("get", "post", "put", "patch", "delete"):
                    continue
                operation = _resolve(raw, openapi)
                name = operation.get("operationId", path.strip("/").replace("/", "_"))
                request = _resolve(operation.get("requestBody", {}), openapi)
                schema = request.get("content", {}).get("application/json", {}).get("schema", {"type": "object", "properties": {}})
                operations[name] = (base + path, method.upper(), _resolve(schema, openapi))
    except (KeyError, TypeError, ValueError, AttributeError) as exc:
        fail(f"invalid OpenAPI: {exc}")
    verification_tools = security.get("verification_tools", ["verify_identity"])
    incoming = {node_id: [] for node_id in all_nodes}
    lifecycle = workflow.get("tools", [])
    if lifecycle and (len(lifecycle) != 1 or lifecycle[0].get("function", {}).get("name") != "close_call" or lifecycle[0].get("config", {}).get("alwaysRunsAt") != ["end_of_call"] or not lifecycle[0].get("pre_process_code", "").strip()):
        fail("lifecycle must be one end_of_call close_call with a trusted-state pre-hook")
    node_entries = list(all_nodes.items())
    if lifecycle:
        node_entries.append(("workflow", {"name": "workflow", "node_type": "api_request", "pre_actions": lifecycle}))
    for node_id, node in node_entries:
        if not isinstance(node, dict):
            fail(f"{node_id}: node must be an object")
            continue
        kind = node.get("node_type")
        if kind not in ("conversation", "api_request", "code", "end_call") or node.get("name") != node_id:
            fail(f"{node_id}: invalid node_type or name")
        if node.get("pre_actions") and kind == "conversation":
            fail(f"{node_id}: conversation pre_actions would be stripped")
        if node.get("tools") and kind != "conversation":
            fail(f"{node_id}: action-node tools would be stripped")
        if node.get("tools"):
            fail(f"{node_id}: model-visible tools are unsupported; use engine actions")
        transitions = node.get("transitions", [])
        if not isinstance(transitions, list):
            fail(f"{node_id}: transitions must be a list")
            transitions = []
        if kind == "conversation":
            if node.get("passthrough") or node.get("loop_condition") or len(transitions) != 1 or transitions[0].get("condition") != {"operator": "always"} or all_nodes.get(transitions[0].get("target_node"), {}).get("node_type") != "code":
                fail(f"{node_id}: listening conversation needs one always route to decision code")
            if node.get("on_enter", {}).get("type") != "tts" or not node.get("on_enter", {}).get("text"):
                fail(f"{node_id}: listening conversation needs a fixed TTS question")
        if node.get("passthrough") and (not transitions or transitions[-1].get("condition") != {"operator": "always"}):
            fail(f"{node_id}: passthrough needs final always transition")
        for transition in transitions:
            target = transition.get("target_node")
            target_actions = all_nodes.get(target, {}).get("pre_actions", [])
            if transition.get("is_tool_call") and any(action.get("function", {}).get("handler") == "__function__:api_call" for action in target_actions):
                fail(f"{node_id} -> {target}: model tool transition cannot enter a bank action")
            if target not in all_nodes and not (target == "__previous__" and node_id in globals_):
                fail(f"{node_id}: unknown transition target {target}")
            elif target in incoming:
                incoming[target].append((node_id, transition.get("condition", {})))
        for key in ("passthrough_default_transition", "max_turn_transition"):
            if node.get(key):
                target = node[key]
                if target not in all_nodes:
                    fail(f"{node_id}: unknown {key} target {target}")
                else:
                    incoming[target].append((node_id, {"operator": "always"}))
        for extraction in node.get("extraction_schema", []):
            if extraction.get("type") != "string" or extraction.get("validation_pattern") or extraction.get("format") or extraction.get("min_confidence") != 0 or extraction.get("max_retries") != 1 or "enum" in extraction and "" not in extraction["enum"]:
                fail(f"{node_id}: extraction must be a blankable string with min_confidence=0 and max_retries=1")
            if extraction.get("name") in trusted or extraction.get("name") == customer_variable:
                fail(f"{node_id}: extraction overwrites trusted variable {extraction['name']}")
        entries = [("tools", tool) for tool in node.get("tools", [])] + [("pre_actions", tool) for tool in node.get("pre_actions", [])]
        for placement, tool in entries:
            function = tool.get("function", {})
            name, handler = function.get("name"), function.get("handler")
            if not isinstance(function.get("description"), str) or not function["description"].strip():
                fail(f"{node_id}/{name}: function.description must be a nonempty string")
            properties = function.get("parameters", {}).get("properties", {})
            if handler == "__function__:code_exec":
                if kind != "code" or placement != "pre_actions":
                    fail(f"{node_id}: model code tools are unavailable")
                if node_id in snippets:
                    fail(f"{node_id}: use one code snippet per code node")
                snippets[node_id] = (properties.get("code", {}).get("default"), None, None)
            elif handler == "__function__:api_call":
                api_entries.append((node_id, placement, tool))
                if placement == "pre_actions" and kind != "api_request":
                    fail(f"{node_id}/{name}: bank actions must use api_request nodes")
                if name not in operations:
                    fail(f"{node_id}: API tool {name} is absent from OpenAPI")
                    continue
                url, method, schema = operations[name]
                if properties.get("url", {}).get("default") != url or properties.get("method", {}).get("default") != method:
                    fail(f"{node_id}/{name}: wrong API URL or method")
                body = properties.get("body", {})
                fields = body.get("properties", {})
                if name == "create_promise":
                    bindings = security.get("promise_request_fields", {})
                    for role, expected_type in (("amount", "number"), ("date", "string")):
                        field = bindings.get(role) if isinstance(bindings, dict) else None
                        expected = _resolve(schema.get("properties", {}).get(field, {}), openapi)
                        if field not in fields or field not in schema.get("required", []) or expected.get("type") != expected_type or role == "date" and expected.get("format") != "date":
                            fail(f"{node_id}/{name}: promise_request_fields.{role} must match a required semantic OpenAPI/request property")
                guarded_write = node_id in security.get("record_nodes", []) or name in action_guards or name in ("schedule_callback", "transfer_to_agent", "add_note")
                for field in schema.get("required", []):
                    if field not in fields:
                        fail(f"{node_id}/{name}: missing required body field {field}")
                    if field not in body.get("required", []):
                        fail(f"{node_id}/{name}: body.required must include {field}")
                for field, field_schema in fields.items():
                    expected = _resolve(schema.get("properties", {}).get(field, {}), openapi)
                    if not expected:
                        fail(f"{node_id}/{name}: unknown body field {field}")
                        continue
                    if field_schema.get("type") != expected.get("type"):
                        fail(f"{node_id}/{name}: wrong type for {field}")
                    if "enum" in expected and (not field_schema.get("enum") or set(field_schema["enum"]) != set(expected["enum"])):
                        fail(f"{node_id}/{name}: invalid or missing enum for {field}")
                    value = field_schema.get("default")
                    dynamic = isinstance(value, str) and PLACEHOLDER.fullmatch(value)
                    if "const" in field_schema:
                        fail(f"{node_id}/{name}: body values must use default, never const")
                    if "default" in field_schema and not dynamic:
                        types_ = {"string": str, "number": (int, float), "integer": int, "boolean": bool, "object": dict, "array": list}
                        expected_type = types_.get(expected.get("type"))
                        if expected_type and (not isinstance(value, expected_type) or expected.get("type") in ("number", "integer") and isinstance(value, bool)):
                            fail(f"{node_id}/{name}: wrong default type for {field}")
                        if "enum" in expected and value not in expected["enum"]:
                            fail(f"{node_id}/{name}: default outside enum for {field}")
                    if placement == "pre_actions" and "default" not in field_schema:
                        fail(f"{node_id}/{name}: action body {field} must be baked from state")
                    if guarded_write and field != customer_field and (not dynamic or dynamic.group(1) not in trusted):
                        fail(f"{node_id}/{name}: record field {field} must bind trusted validated state")
                if customer_field not in schema.get("required", []) or fields.get(customer_field, {}).get("default") != "{{" + customer_variable + "}}":
                    fail(f"{node_id}/{name}: customer_id binding must match the required API field and fixed call variable")
                if node_id == "workflow":
                    for field, field_schema in fields.items():
                        if field != customer_field and ("default" not in field_schema or isinstance(field_schema.get("default"), str) and PLACEHOLDER.fullmatch(field_schema["default"])):
                            fail(f"workflow/{name}: closing defaults must resolve before setup")
                if placement == "tools" and (name not in verification_tools or node_id not in security.get("identity_nodes", [])):
                    fail(f"{node_id}/{name}: bank read/write must run in an engine action")
                if name not in verification_tools and name != "get_account" and tool.get("config", {}).get("maxRetries") != 0:
                    fail(f"{node_id}/{name}: writes need maxRetries=0")
                if guarded_write and tool.get("pre_process_code", "").strip():
                    fail(f"{node_id}/{name}: record arguments must be validated before entry, not in a pre-hook")
                for suffix, field in (("pre", "pre_process_code"), ("post", "post_process_code")):
                    if tool.get(field, "").strip():
                        snippets[f"{node_id}:{name}:{suffix}"] = (tool[field], name, suffix)
                for mapping in tool.get("response_mapping", []) + node.get("response_mapping", []):
                    if not mapping.get("path", "").startswith("data."):
                        fail(f"{node_id}/{name}: response mappings must start data.")
                    if mapping.get("variable") == bank_var:
                        fail(f"{node_id}/{name}: bank gate must be set by the verification post-hook")
                    if mapping.get("variable") == authorization:
                        fail(f"{node_id}/{name}: response_mapping may not write record authorization")
                    if mapping.get("variable") in {item.get("variable") for item in action_guards.values() if isinstance(item, dict)}:
                        fail(f"{node_id}/{name}: response_mapping may not write action authorization")
            elif handler != "__function__:end_call" or kind != "end_call":
                fail(f"{node_id}: unsupported or early lifecycle handler {handler}")
        if kind == "code" and node_id not in snippets:
            fail(f"{node_id}: code node has no code_exec snippet")
    bank_writers = []
    for identifier, (code, operation, hook) in snippets.items():
        try:
            tree = _parse(code)
            writes = _writes(tree)
            if customer_variable in writes:
                fail(f"{identifier}: code may not overwrite the call customer identifier")
            if hook == "pre":
                _pre_hook_request(tree, identifier.startswith("workflow:"))
            if identifier != security.get("approval_guard_node"):
                for value in _authorization_values(tree, authorization):
                    if not isinstance(value, ast.Constant) or value.value == authorized:
                        fail(f"{identifier}: only the approval guard may activate record authorization")
            for name, action_gate in action_guards.items():
                if not isinstance(action_gate, dict) or identifier == action_gate.get("node"):
                    continue
                for value in _authorization_values(tree, action_gate.get("variable")):
                    if not isinstance(value, ast.Constant) or value.value == action_gate.get("operand"):
                        fail(f"{identifier}: only {name} guard may activate action authorization")
            if bank_var in writes:
                if operation in verification_tools and hook == "post":
                    bank_writers.append(identifier)
                elif any(not isinstance(value, ast.Constant) or value.value == "verified" for value in _authorization_values(tree, bank_var)):
                    fail(f"{identifier}: bank verification can only be activated in a verification post-hook")
        except (ValueError, SyntaxError, TypeError) as exc:
            fail(f"{identifier}: invalid Python: {exc}")
    if not bank_writers:
        fail("bank verification has no trusted verification post-hook writer")
    gate = security.get("bank_gate", {})
    if not isinstance(gate, dict) or gate.get("variable") != bank_var or gate.get("operand") != "verified" or gate.get("node") not in all_nodes or gate.get("target") not in security.get("account_nodes", []):
        fail("security.bank_gate must identify the trusted verified route into account")
        gate = {}
    for node_id in security.get("account_nodes", []):
        if [tool.get("function", {}).get("name") for tool in all_nodes.get(node_id, {}).get("pre_actions", [])] != ["get_account"]:
            fail(f"{node_id}: account node must contain exactly one get_account action")
        if node_id in globals_ or node_id == workflow.get("initial_node") or not incoming.get(node_id):
            fail(f"{node_id}: account action must be reached through bank gate")
        if len(incoming.get(node_id, [])) != 1:
            fail(f"{node_id}: account action needs exactly one bank-gated incoming edge")
        for source, condition in incoming.get(node_id, []):
            if source != gate.get("node") or not _exact_guard(condition, bank_var, "verified"):
                fail(f"{node_id}: account route bypasses trusted bank verification")
    for node_id in security.get("record_nodes", []):
        if [tool.get("function", {}).get("name") for tool in all_nodes.get(node_id, {}).get("pre_actions", [])] != ["create_promise"]:
            fail(f"{node_id}: record node must contain exactly one create_promise action")
        if node_id in globals_ or node_id == workflow.get("initial_node") or not incoming.get(node_id):
            fail(f"{node_id}: record action must be reached through approval guard")
        for source, condition in incoming.get(node_id, []):
            if source != security.get("approval_guard_node") or not _exact_guard(condition, authorization, authorized):
                fail(f"{node_id}: record route bypasses immutable authorization")
    for node_id, placement, tool in api_entries:
        name = tool.get("function", {}).get("name")
        if name not in (*verification_tools, "get_account", "create_promise", "close_call"):
            action_gate = action_guards.get(name, {})
            if not action_gate:
                fail(f"{node_id}/{name}: missing security.action_guards entry")
            if node_id in globals_ or node_id == workflow.get("initial_node") or not incoming.get(node_id):
                fail(f"{node_id}/{name}: action must be reachable through its guard")
            if len(incoming.get(node_id, [])) != 1:
                fail(f"{node_id}/{name}: action needs exactly one guard incoming edge")
            for source, condition in incoming.get(node_id, []):
                if source != action_gate.get("node") or not _exact_guard(condition, action_gate.get("variable"), action_gate.get("operand")):
                    fail(f"{node_id}/{name}: action route bypasses its trusted guard")
        required_nodes = "account_nodes" if name == "get_account" else "record_nodes" if name == "create_promise" else "close_nodes" if name == "close_call" else ""
        if required_nodes and node_id != "workflow" and node_id not in security.get(required_nodes, []):
            fail(f"{node_id}/{name}: API action omitted from security.{required_nodes}")
    for node_id in security.get("close_nodes", []):
        node = all_nodes.get(node_id, {})
        if node.get("node_type") == "end_call":
            if node_id not in security.get("close_nodes", []):
                fail(f"{node_id}: terminal omitted from security.close_nodes")
            if node.get("transitions"):
                fail(f"{node_id}: terminal close node has outgoing routes")
            continue
        names = [tool.get("function", {}).get("name") for tool in node.get("pre_actions", [])]
        if names != ["close_call"] or node.get("node_type") != "api_request":
            fail(f"{node_id}: close node must contain exactly one close_call action")
        if any(all_nodes.get(t.get("target_node"), {}).get("node_type") != "end_call" for t in node.get("transitions", [])):
            fail(f"{node_id}: no bank action may follow close_call")
    for node_id, node in all_nodes.items():
        if node.get("node_type") == "end_call":
            terminal = node.get("terminal", {})
            function = terminal.get("function", {})
            properties = function.get("parameters", {}).get("properties", {})
            if terminal.get("type") != "function" or function.get("handler") != "__function__:end_call" or properties.get("message_mode", {}).get("default") != "custom" or not isinstance(properties.get("spoken_message", {}).get("default"), str) or not properties["spoken_message"]["default"]:
                fail(f"{node_id}: terminal needs end_call with a fixed spoken farewell")
            if node_id == workflow.get("initial_node") or node_id in globals_ or not incoming[node_id] or not lifecycle and any(source not in security.get("close_nodes", []) for source, _ in incoming[node_id]):
                fail(f"{node_id}: ending must follow bank close_call")
    closing_entries = [entry for entry in api_entries if entry[2].get("function", {}).get("name") == "close_call"]
    if len(closing_entries) != 1:
        fail("workflow must declare close_call exactly once")
    if globals_:
        fail("global_nodes must be empty; fresh exceptions belong in decision code")
    errors.extend(_graph_checks(workflow, all_nodes, security))
    if not isinstance(checks, list):
        checks = []
        fail("checks must be an array")
    names = [check.get("name", "") for check in checks if isinstance(check, dict)]
    for required in REQUIRED_CHECKS:
        if not any(name == required or name.startswith(required + "_") for name in names):
            fail(f"missing generated check: {required}")
    canonical_offers = {category for category in ("invalid_amount", "invalid_date") if any(
        isinstance(check, dict) and check.get("node_id") == security.get("offer_guard_node") and
        (check.get("name") == category or check.get("name", "").startswith(category + "_"))
        for check in checks
    )}
    for check in checks:
        identifier = check.get("node_id") if isinstance(check, dict) else ""
        report = {"name": check.get("name", "") if isinstance(check, dict) else "", "node_id": identifier, "ok": False}
        try:
            if not isinstance(check, dict) or not isinstance(check.get("vars"), dict) or not isinstance(check.get("expected"), dict) or not check["expected"]:
                raise ValueError("check needs vars and nonempty expected objects")
            if any(_null_paths(check["expected"], "expected")):
                raise ValueError("check expected values may not contain null")
            if identifier not in snippets:
                raise ValueError("check must target an actual code node or API hook")
            category = next((name for name in REQUIRED_CHECKS if check.get("name") == name or check.get("name", "").startswith(name + "_")), "")
            _, operation, hook = snippets[identifier]
            if category == "identity_unverified":
                if operation not in verification_tools or hook != "post":
                    raise ValueError("identity_unverified must target a verification post-hook")
                if bank_var not in check["expected"] or check["expected"][bank_var] == "verified":
                    raise ValueError(f"identity_unverified must assert {bank_var} != 'verified'")
            if category in ("invalid_amount", "invalid_date") and identifier != security.get("offer_guard_node") and (category not in canonical_offers or identifier != security.get("decision_node")):
                raise ValueError(f"{category} must target the offer guard")
            if category in ("correction_clears_confirmation", "negative_confirmation", "duplicate_promise_blocked"):
                if identifier != security.get("approval_guard_node"):
                    raise ValueError(f"{category} must target the approval guard")
                if authorization not in check["expected"] or check["expected"][authorization] == authorized:
                    raise ValueError(f"{category} must assert cleared record authorization")
            if category == "business_failure_not_success" and (operation != "create_promise" or hook != "post"):
                raise ValueError("business_failure_not_success must target a create_promise post-hook")
            if not any(key in trusted or key.startswith(("result.", "config.")) for key in check["expected"]):
                raise ValueError("check must assert a trusted control or actual hook output")
            _parse(snippets[identifier][0])
            _run_check(snippets[identifier][0], check)
            report["ok"] = True
        except (ValueError, SyntaxError, TypeError, KeyError, EOFError) as exc:
            report["error"] = str(exc)
            fail(f"check {report['name']}: {exc}")
        reports.append(report)
    independent = _independent_checks(all_nodes, snippets, security, checks, policy=policy, openapi=openapi, brief_lines=brief_lines, close_tool=closing_entries[0][2] if closing_entries else None)
    reports.extend(independent)
    for report in independent:
        if not report["ok"]:
            fail(f"check {report['name']}: {report['error']}")
    return {"ok": not errors, "valid": not errors, "errors": errors, "checks": reports}
