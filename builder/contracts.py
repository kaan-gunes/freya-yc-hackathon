"""Check a model-extracted HTTP contract against the original document text."""
import re
import json
from urllib.parse import urlsplit


def _business_conditions(lines):
    # shortcut: parse an explicit single-line equality; review other source wording separately.
    pattern = r'Success\s*=\s*HTTP\s+\d+\s+and\s+`([\w.]+)`\s+(?:is|==|=)\s+`([^`]+)`'
    found = []
    for number, line in enumerate(lines, 1):
        match = re.search(pattern, line, re.I)
        if match:
            try:
                found.append(({"path": match[1], "operand": json.loads(match[2])}, number))
            except ValueError:
                raise ValueError("Explicit business-success equality has an invalid JSON value.")
    return found


def validate_extracted_contract(contract, evidence, sources, server):
    if not isinstance(contract, dict) or not str(contract.get("openapi", "")).startswith("3."):
        raise ValueError("Extracted contract must be OpenAPI 3.x.")
    if contract.get("servers") != [{"url": server}]:
        raise ValueError("Extracted contract must use the supplied mock service base.")
    paths = contract.get("paths")
    if not isinstance(paths, dict) or not paths:
        raise ValueError("No explicit HTTP integration contract was extracted.")
    text = "\n".join(line for lines in sources.values() for line in lines)
    operations = {}
    prefixes = {urlsplit(url.rstrip('.,;`')).path.rstrip('/') for url in re.findall(r'https?://[^\s<>"\x27]+', text)}
    for path, methods in paths.items():
        if not isinstance(path, str) or not path.startswith("/"):
            raise ValueError("Extracted API path is absent from sources: " + str(path))
        literal = bool(re.search(r"(?<![\w/])" + re.escape(path) + r"(?![\w/.-])", text))
        if path not in prefixes and not literal and not any(prefix and path.startswith(prefix + "/")
                and "/" not in path[len(prefix) + 1:] and path[len(prefix) + 1:] in text for prefix in prefixes):
            raise ValueError("Extracted API path or base/endpoint composition is absent from sources: " + path)
        if not isinstance(methods, dict):
            raise ValueError("Extracted API methods must be an object.")
        for method, operation in methods.items():
            if method not in {"get", "post", "put", "patch", "delete", "head", "options"}:
                continue
            name = operation.get("operationId") if isinstance(operation, dict) else None
            if not isinstance(name, str) or not name or name in operations:
                raise ValueError("Extracted operations need unique operationId names.")
            if not isinstance(operation.get("responses"), dict) or not operation["responses"]:
                raise ValueError("Extracted operation has no sourced responses: " + name)
            operations[name] = (method, path, operation)
    if not operations:
        raise ValueError("Extracted contract contains no HTTP operations.")
    if not isinstance(evidence, list):
        raise ValueError("Extracted contract evidence must be a list.")
    covered = set()
    for item in evidence:
        if not isinstance(item, dict) or item.get("operationId") not in operations:
            raise ValueError("Extracted contract evidence names an unknown operation.")
        lines = sources.get(item.get("source"))
        number, quote = item.get("line"), item.get("text")
        if (not lines or type(number) is not int or not 1 <= number <= len(lines)
                or not isinstance(quote, str) or not quote.strip() or quote.strip() not in lines[number - 1]):
            raise ValueError("Extracted contract evidence does not match the original source line.")
        method, path, operation = operations[item["operationId"]]
        endpoint = path.rsplit("/", 1)[-1]
        if path not in quote and not re.search(r"(?<![\w.])" + re.escape(endpoint) + r"(?![\w.])", quote):
            raise ValueError("Extracted evidence does not identify its HTTP endpoint.")
        direct_methods = re.findall(r'\b(GET|POST|PUT|PATCH|DELETE|HEAD|OPTIONS)\b', quote)
        shared = [line for line in lines if re.search(r'\b(?:every|all|each)\s+(?:HTTP\s+)?(?:service|services|endpoint|endpoints|operation|operations)\b|\b(?:t[uü]m|b[uü]t[uü]n) (?:servis|hizmet)', line, re.I)]
        declared_methods = direct_methods or [verb for line in shared for verb in re.findall(r'\b(GET|POST|PUT|PATCH|DELETE|HEAD|OPTIONS)\b', line)]
        if not declared_methods or set(declared_methods) != {method.upper()}:
            raise ValueError("Extracted HTTP method does not match its source evidence.")
        marker = operation.get("x-business-success")
        conditions = _business_conditions(lines)
        if conditions and marker not in [condition for condition, _ in conditions]:
            raise ValueError("Extracted operation omits or changes its explicit business-success equality.")
        if marker is not None:
            if not isinstance(marker, dict) or set(marker) != {"path", "operand"} or not isinstance(marker["path"], str):
                raise ValueError("Extracted business-success binding must contain path and operand.")
            proof = item.get("business_success")
            proof_lines = sources.get(proof.get("source")) if isinstance(proof, dict) else None
            proof_number = proof.get("line") if isinstance(proof, dict) else None
            proof_quote = proof.get("text") if isinstance(proof, dict) else None
            if (not proof_lines or type(proof_number) is not int or not 1 <= proof_number <= len(proof_lines)
                    or not isinstance(proof_quote, str) or not proof_quote.strip()
                    or proof_quote.strip() not in proof_lines[proof_number - 1]
                    or marker["path"] not in proof_quote or json.dumps(marker["operand"], ensure_ascii=False) not in proof_quote):
                raise ValueError("Extracted business-success equality needs exact source evidence.")
        covered.add(item["operationId"])
    if covered != set(operations):
        raise ValueError("Extracted contract has operations without source evidence.")

    def fields(value):
        if isinstance(value, dict):
            properties = value.get("properties", {})
            if not isinstance(properties, dict):
                raise ValueError("Extracted schema properties must be an object.")
            for field in properties:
                if not re.search(r"(?<!\w)" + re.escape(field) + r"(?!\w)", text):
                    raise ValueError("Extracted API property is absent from sources: " + field)
            for child in value.values():
                fields(child)
        elif isinstance(value, list):
            for child in value:
                fields(child)
    fields(contract)
