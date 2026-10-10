"""Local checks for generated Freya workflows, before any bank call is allowed."""

import ast
import builtins
import copy
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
        if isinstance(node, (ast.ClassDef, ast.Global, ast.Nonlocal)):
            raise ValueError(f"unsupported Python statement {type(node).__name__}")
        if isinstance(node, ast.Name) and node.id.startswith("__"):
            raise ValueError("private names are unavailable")
        if isinstance(node, ast.Attribute) and (node.attr.startswith("_") or node.attr in UNSAFE_ATTRIBUTES):
            raise ValueError("private/runtime attributes are unavailable")
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
    for node in ast.walk(tree):
        if isinstance(node, (ast.Assign, ast.AnnAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            if any(isinstance(target, ast.Name) and target.id == "vars" for target in targets) or isinstance(node.value, ast.Name) and node.value.id == "vars":
                raise ValueError("do not replace or alias the workflow variable table")
        if isinstance(node, ast.Return) and isinstance(node.value, ast.Name) and node.value.id == "vars":
            raise ValueError("do not return the workflow variable table")
        if isinstance(node, ast.Call) and any(isinstance(argument, ast.Name) and argument.id == "vars" for argument in node.args):
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
                elif key in ("identity_nodes", "confirmation_nodes") and all_nodes[node_id].get("node_type") != "conversation":
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
        transitions = node.get("transitions", [])
        if not isinstance(transitions, list):
            fail(f"{node_id}: transitions must be a list")
            transitions = []
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
            if extraction.get("name") in trusted or extraction.get("name") == customer_variable:
                fail(f"{node_id}: extraction overwrites trusted variable {extraction['name']}")
        entries = [("tools", tool) for tool in node.get("tools", [])] + [("pre_actions", tool) for tool in node.get("pre_actions", [])]
        for placement, tool in entries:
            function = tool.get("function", {})
            name, handler = function.get("name"), function.get("handler")
            if (node_id == "workflow" or placement == "tools") and (not isinstance(function.get("description"), str) or not function["description"].strip()):
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
                    if node_id in security.get("record_nodes", []) and field != customer_field and (not dynamic or dynamic.group(1) not in trusted):
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
                if node_id in security.get("record_nodes", []) and tool.get("pre_process_code", "").strip():
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
            elif handler != "__function__:end_call" or kind != "end_call":
                fail(f"{node_id}: unsupported or early lifecycle handler {handler}")
        if kind == "code" and node_id not in snippets:
            fail(f"{node_id}: code node has no code_exec snippet")
    bank_writers = []
    for identifier, (code, operation, hook) in snippets.items():
        try:
            tree = _parse(code)
            writes = _writes(tree)
            if identifier != security.get("approval_guard_node"):
                for value in _authorization_values(tree, authorization):
                    if not isinstance(value, ast.Constant) or value.value == authorized:
                        fail(f"{identifier}: only the approval guard may activate record authorization")
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
    if not isinstance(gate, dict) or gate.get("variable") != bank_var or gate.get("operand") != "verified" or gate.get("node") not in security.get("identity_nodes", []) or gate.get("target") not in security.get("account_nodes", []):
        fail("security.bank_gate must identify the trusted verified route into account")
        gate = {}
    for node_id in security.get("account_nodes", []):
        if [tool.get("function", {}).get("name") for tool in all_nodes.get(node_id, {}).get("pre_actions", [])] != ["get_account"]:
            fail(f"{node_id}: account node must contain exactly one get_account action")
        if node_id in globals_ or node_id == workflow.get("initial_node") or not incoming.get(node_id):
            fail(f"{node_id}: account action must be reached through bank gate")
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
    if not isinstance(checks, list):
        checks = []
        fail("checks must be an array")
    names = [check.get("name", "") for check in checks if isinstance(check, dict)]
    for required in REQUIRED_CHECKS:
        if not any(name == required or name.startswith(required + "_") for name in names):
            fail(f"missing generated check: {required}")
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
            if category in ("invalid_amount", "invalid_date") and identifier != security.get("offer_guard_node"):
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
    return {"ok": not errors, "valid": not errors, "errors": errors, "checks": reports}
