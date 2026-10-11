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
    "re": ("compile", "match", "fullmatch", "search", "findall", "sub", "split", "escape", "IGNORECASE"),
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


def _independent_checks(nodes, snippets, security, checks):
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
    required_roles = ("proposed_amount", "proposed_date", "approval_event", "correction", "decision_event", "decision_date", "decision_amount", "full_amount", "identity_answer", "speech_text", "persuasion_attempts", "party_confirmation", "recorded", "offer_fingerprint", "readback_fingerprint", "exception", "route", "stage", "write_attempts", "write_result")
    for label, data, names in (("validation_state", roles, required_roles), ("validation_events", events, ("yes", "no", "question", "human", "plan", "hardship", "dispute", "third_party")), ("validation_routes", routes, ("account", "confirmation", "record", "offer", "transfer", "end"))):
        if not isinstance(data, dict) or any(not isinstance(data.get(name), str) or not data[name] for name in names):
            return [{"name": "independent_contract", "ok": False, "error": f"security.{label} needs every declared string role"}]
    if len(set(roles.values())) != len(roles):
        return [{"name": "independent_contract", "ok": False, "error": "validation_state roles must name different variables"}]
    if not all(isinstance(data, dict) and data for data in (fixture, confirmation, identity)):
        return [{"name": "independent_contract", "ok": False, "error": "independent checks need offer, confirmation and identity input fixtures"}]
    trusted = set(security.get("trusted_variables", []))
    contract_errors = []
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
    try:
        if not isinstance(identity_answer_fixture, dict) or not identity_answer_fixture.get(roles["stage"]):
            raise ValueError("identity answer fixture needs current pre-verification state")
        canonical_identity_answer = identity_answer_fixture.get(roles["identity_answer"])
        if not isinstance(canonical_identity_answer, str) or datetime.date.fromisoformat(canonical_identity_answer).isoformat() != canonical_identity_answer:
            raise ValueError("identity answer fixture needs a valid canonical ISO raw answer")
    except (TypeError, ValueError) as exc:
        contract_errors.append(f"validation_identity_answer_fixture: {exc}")
    canonical_identity_code = None
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
    for label, context in (("validation_identity_request_context", identity_request_context), ("validation_identity_code_request_context", identity_code_context)):
        if not isinstance(context, dict) or not context:
            contract_errors.append(f"{label} must declare the pending question's request properties")
        elif any(not isinstance(name, str) or not name or name in (security.get("customer_id_field"), answer_request_field) or not isinstance(value, (str, int, float, bool)) or isinstance(value, str) and "{{" in value for name, value in context.items()):
            contract_errors.append(f"{label} needs literal values and cannot include customer or answer fields")
        elif not any(context_schema_matches(tool, context) for _, tool in verification_requests):
            contract_errors.append(f"{label} must match real verification request property types and enums")
    offer, approval = security.get("offer_guard_node"), security.get("approval_guard_node")
    record_nodes = security.get("record_nodes", [])
    readbacks = security.get("confirmation_nodes", [])
    for identifier, required_reads, required_writes in (
        (offer, ("proposed_amount", "proposed_date"), ("offer_fingerprint", "readback_fingerprint")),
        (approval, ("approval_event", "correction", "recorded", "offer_fingerprint", "readback_fingerprint", "write_attempts", "write_result"), ("route", "write_attempts")),
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

    def bound_request(target, state):
        bodies = []
        for tool in nodes[target].get("pre_actions", []):
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
        state = step(f"{target}:create_promise:post", state, {"status": "success", "status_code": 200, "data": {"ok": True}})
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
        matching_amounts = [body for name, body in requests if name == "create_promise" and _json_equal(body.get("amount"), expected_amount)]
        if not matching_amounts:
            raise ValueError("amount promise did not bind the original numeric amount")
        if expected_date is not None and not any(body.get("date") == expected_date for body in matching_amounts):
            raise ValueError("promise did not bind the original canonical date")
        state = step(f"{target}:create_promise:post", state, {"status": "success", "status_code": 200, "data": {"ok": True}})
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

    def record_result(result, unknown=False):
        state, target = confirm(valid_readback())
        if target not in record_nodes:
            raise ValueError("failure check could not reach record action")
        state = step(f"{target}:create_promise:post", state, result)
        if state.get(roles["recorded"]) == "recorded":
            raise ValueError("failed/unknown business result marked current product recorded")
        if unknown:
            state = step(approval, state)
            assert_denied(state)
    run("independent_failed_record", lambda: record_result({"status": "success", "status_code": 200, "data": {"ok": False}}))
    run("independent_unknown_record_no_retry", lambda: record_result({"status": "error", "error": "timeout"}, True))

    def retry_limit():
        limit = security.get("write_attempt_limit")
        if type(limit) is not int or limit < 1:
            raise ValueError("security.write_attempt_limit must be a positive integer")
        state, target = confirm(valid_readback())
        failure = {"status": "success", "status_code": 200, "data": {"ok": False}}
        state = step(f"{target}:create_promise:post", state, failure)
        if limit > 1:
            state = step(approval, state)
            if state.get(authorization) != authorized or int(state.get(roles["write_attempts"], 0)) != 2:
                raise ValueError("allowed retry did not preserve authorization and count one new attempt")
            state = step(f"{target}:create_promise:post", state, failure)
        state[roles["write_attempts"]] = limit
        state = step(approval, state)
        assert_denied(state)
        if int(state.get(roles["write_attempts"], 0)) > limit:
            raise ValueError("failed record exceeded source write attempt limit")
    run("independent_failed_record_retry_limit", retry_limit)

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

    small_words = "zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen seventeen eighteen nineteen".split()
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

    def missing_identity_year(role):
        state = current_identity_state(identity_answer_fixture, roles[role], f"the {ordinal_day} of {month}.")
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

    code_prefix = "My last four digits are" if len(canonical_identity_code) == 4 else "My verification code is"
    for label, speech in (("period", canonical_identity_code + "."), ("prefix", code_prefix + " " + canonical_identity_code + ".")):
        run(f"independent_identity_code_in_speech_text_{label}", lambda speech=speech: identity_request_boundary(current_identity_state(identity_code_fixture, roles["speech_text"], speech), canonical_identity_code, identity_code_context, "code"))

    def missing_identity_speech(input_fixture=identity_answer_fixture, cached_answer=canonical_identity_answer):
        state = identity_state(input_fixture)
        for _, tool in verification_requests:
            field = tool.get("function", {}).get("parameters", {}).get("properties", {}).get("body", {}).get("properties", {}).get(answer_request_field, {})
            value = field.get("default")
            placeholder = PLACEHOLDER.fullmatch(value) if isinstance(value, str) else None
            if placeholder:
                state[placeholder.group(1)] = cached_answer
        for field in decision_inputs:
            state[field] = ""
        state[security.get("bank_verification_variable")] = "unverified"
        state[roles["party_confirmation"]] = party_confirmed
        state[authorization] = ""
        forbidden = (offer, *readbacks, *record_nodes, *security.get("account_nodes", []), *(identifier for identifier, _ in verification_requests))
        state, target = advance(decision, state, forbidden)
        assert_denied(state)
        if nodes[target].get("node_type") != "conversation" or not nodes[target].get("extraction_schema"):
            raise ValueError("missing identity speech must return to a real listener without a bank action")
    run("independent_missing_identity_speech", missing_identity_speech)
    run("independent_missing_identity_code_speech", lambda: missing_identity_speech(identity_code_fixture, canonical_identity_code))

    def inactive_identity_event(input_fixture, speech, event):
        state = current_identity_state(input_fixture, roles["speech_text"], speech)
        state[roles["decision_event"]] = event
        forbidden = (offer, *readbacks, *record_nodes, *security.get("account_nodes", []), *(identifier for identifier, _ in verification_requests))
        state, target = advance(decision, state, forbidden)
        assert_denied(state)
        if nodes[target].get("node_type") != "conversation" or not nodes[target].get("extraction_schema"):
            raise ValueError("inactive identity answer event must return to a real listener")
    for kind, input_fixture, speech in (("date", identity_answer_fixture, f"{day.day} {month} {day.year:04d}."), ("code", identity_code_fixture, canonical_identity_code + ".")):
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
    run("independent_latest_third_party_blocks_identity_code", lambda: latest_third_party(identity_code_fixture))
    for operation, action_gate in security.get("action_guards", {}).items():
        def empty_action(action_gate=action_gate):
            state = step(action_gate["node"], {})
            if state.get(action_gate["variable"]) == action_gate["operand"]:
                raise ValueError("action guard authorized without caller intent or validated inputs")
        run(f"independent_{operation}_missing_inputs", empty_action)
    return reports


def validate(workflow, policy, openapi, checks):
    try:
        return _validate(workflow, policy, openapi, checks)
    except (AttributeError, KeyError, TypeError, ValueError) as exc:
        return {"ok": False, "valid": False, "errors": [f"malformed generated data: {exc}"], "checks": []}


def _validate(workflow, policy, openapi, checks):
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
    independent = _independent_checks(all_nodes, snippets, security, checks)
    reports.extend(independent)
    for report in independent:
        if not report["ok"]:
            fail(f"check {report['name']}: {report['error']}")
    return {"ok": not errors, "valid": not errors, "errors": errors, "checks": reports}
