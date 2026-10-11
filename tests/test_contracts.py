import copy
import unittest

from builder.contracts import validate_extracted_contract
from tests.test_final_runner import runner


class ContractEvidenceChecks(unittest.TestCase):
    def setUp(self):
        self.sources = {"contract.md": ["POST /lookup accepts clientCode and returns balance", "Deployment: 1. run locally"]}
        self.contract = {"openapi": "3.0.3", "servers": [{"url": "https://synthetic.workers.dev"}], "paths": {
            "/lookup": {"post": {"operationId": "lookup", "requestBody": {"content": {"application/json": {
                "schema": {"type": "object", "properties": {"clientCode": {"type": "string"}}}}}},
                "responses": {"200": {"description": "Response", "content": {"application/json": {
                    "schema": {"type": "object", "properties": {"balance": {"type": "number"}}}}}}}}}}}
        self.evidence = [{"operationId": "lookup", "source": "contract.md", "line": 1, "text": self.sources["contract.md"][0]}]

    def test_exact_source_contract_accepts_only_sourced_fields_paths_and_evidence(self):
        validate_extracted_contract(self.contract, self.evidence, self.sources, "https://synthetic.workers.dev")
        for failure in ("path", "property", "quote", "unrelated", "method", "missing", "server"):
            contract, evidence = copy.deepcopy(self.contract), copy.deepcopy(self.evidence)
            if failure == "path":
                contract["paths"]["/invented"] = contract["paths"].pop("/lookup")
            elif failure == "property":
                contract["paths"]["/lookup"]["post"]["requestBody"]["content"]["application/json"]["schema"]["properties"]["invented"] = {"type": "string"}
            elif failure == "quote":
                evidence[0]["text"] = "invented quote"
            elif failure == "unrelated":
                evidence[0].update(line=2, text=self.sources["contract.md"][1])
            elif failure == "method":
                contract["paths"]["/lookup"]["put"] = contract["paths"]["/lookup"].pop("post")
            elif failure == "missing":
                evidence = []
            else:
                contract["servers"][0]["url"] = "https://other.workers.dev"
            with self.subTest(failure=failure), self.assertRaises(ValueError):
                validate_extracted_contract(contract, evidence, self.sources, "https://synthetic.workers.dev")

    def test_explicit_shared_base_and_method_compose_the_named_endpoint(self):
        sources = {"contract.md": ["Every service is POST.", "https://bank.example/api/v2/", "### `lookup`"]}
        contract = copy.deepcopy(self.contract)
        contract["paths"]["/api/v2/lookup"] = contract["paths"].pop("/lookup")
        sources["contract.md"].append("clientCode balance")
        evidence = [{"operationId": "lookup", "source": "contract.md", "line": 3, "text": "### `lookup`"}]
        validate_extracted_contract(contract, evidence, sources, "https://synthetic.workers.dev")
        sources["contract.md"].append("POST https://bank.example/api/v2/lookup")
        with self.assertRaises(ValueError):
            validate_extracted_contract(self.contract, evidence, sources, "https://synthetic.workers.dev")

    def test_service_provenance_requires_exact_quote_without_turning_deployment_lists_into_bank_rules(self):
        policy = {"workflow_kind": "service", "source_rules": self.evidence}
        self.assertTrue(runner.provenance_report(policy, self.sources)["ok"])
        policy["source_rules"][0]["text"] = "invented"
        self.assertFalse(runner.provenance_report(policy, self.sources)["ok"])
        self.assertFalse(runner.provenance_report({"workflow_kind": "service", "source_rules": []}, self.sources)["ok"])

    def test_explicit_body_success_equality_cannot_be_omitted_or_changed(self):
        self.sources["contract.md"].append('Success = HTTP 200 and `outcome.flag` is `"accepted"`.')
        operation = self.contract["paths"]["/lookup"]["post"]
        with self.assertRaises(ValueError):
            validate_extracted_contract(self.contract, self.evidence, self.sources, "https://synthetic.workers.dev")
        operation["x-business-success"] = {"path": "outcome.flag", "operand": "accepted"}
        self.evidence[0]["business_success"] = {"source": "contract.md", "line": 3, "text": self.sources["contract.md"][2]}
        validate_extracted_contract(self.contract, self.evidence, self.sources, "https://synthetic.workers.dev")
        for failure in ("value", "proof"):
            contract, evidence = copy.deepcopy(self.contract), copy.deepcopy(self.evidence)
            if failure == "value":
                contract["paths"]["/lookup"]["post"]["x-business-success"]["operand"] = "rejected"
            else:
                evidence[0]["business_success"]["text"] = "invented"
            with self.subTest(failure=failure), self.assertRaises(ValueError):
                validate_extracted_contract(contract, evidence, self.sources, "https://synthetic.workers.dev")


if __name__ == "__main__":
    unittest.main()
