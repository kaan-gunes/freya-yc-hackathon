import unittest

from builder.validation import _identity_requirements


class FinalIdentitySourceTests(unittest.TestCase):
    def requirements(self, text):
        rule = {"id": "identity-rule", "text": text, "stage": "identity", "source": "brief.md", "line": 1}
        return _identity_requirements({"source_rules": [rule]}, {"brief.md": [text]})

    def test_turkish_date_numeric_question_and_explicit_count(self):
        _, kinds, counts, _ = self.requirements("1. İki güvenlik sorusu sor: doğum tarihi ve telefonun son dört hanesi.")
        self.assertEqual(kinds, {"date", "numeric_code"})
        self.assertEqual(counts, {"identity-rule": 2})

    def test_turkish_prohibited_question_is_not_required(self):
        _, kinds, _, _ = self.requirements("1. Doğum tarihi sormayın. Sayısal kod sor.")
        self.assertEqual(kinds, {"numeric_code"})

    def test_english_source_behavior_is_preserved(self):
        _, kinds, counts, _ = self.requirements("1. Ask two security questions: date of birth and last four digits.")
        self.assertEqual(kinds, {"date", "numeric_code"})
        self.assertEqual(counts, {"identity-rule": 2})


if __name__ == "__main__":
    unittest.main()
