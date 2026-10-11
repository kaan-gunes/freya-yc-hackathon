import inspect
import unittest

from builder.compiler import _kaan_clear_confirmation, _kaan_question_kind
from builder.validation import _parse


class CompilerIntentChecks(unittest.TestCase):
    def test_embedded_helpers_pass_the_portable_python_boundary(self):
        for helper in (_kaan_clear_confirmation, _kaan_question_kind):
            with self.subTest(helper=helper.__name__):
                _parse(inspect.getsource(helper))

    def test_clear_current_consent_includes_polite_long_replies(self):
        for text in (
            "Yes.",
            "Yes, I confirm. Thank you.",
            "Yes, I confirm. Thank you very much!",
            "Yes, 600 on October 16th.",
            "No problem, yes, I confirm.",
            "Yes, please record the promise for that amount and date.",
            "I confirm the payment amount and the date. Thank you.",
            "Yes, that sounds right. Please go ahead and register the promise.",
        ):
            with self.subTest(text=text):
                self.assertTrue(_kaan_clear_confirmation(text))

    def test_refusal_history_uncertainty_and_partial_consent_are_denied(self):
        for text in (
            "", "No, I do not confirm.", "Yes, but I cannot pay.",
            "I said yes earlier.", "I have not confirmed.", "Yes, maybe.",
            "I agree that this is your job.",
            "Yes, please record it only if I approve later.",
            "Yes, I confirm the amount, the date is wrong.",
            "I agree with the amount only.",
            "Yes, I can pay that amount if I get paid.",
            "Yes, 600 on October 16th I cannot afford it.",
            "Yes, 600 on October 16th I have not agreed.",
            "Yes, I confirm the amount.", "Yes, I confirm the date.",
        ):
            with self.subTest(text=text):
                self.assertFalse(_kaan_clear_confirmation(text))

    def test_turkish_consent_keeps_the_same_strict_current_reply_boundary(self):
        for text in (
            'Evet.', 'Tamam.', 'Onaylıyorum.', 'EVET, TUTARI VE TARİHİ ONAYLIYORUM.',
            'Evet, bu ödeme sözünü kabul ediyorum. Teşekkür ederim.',
            "Evet, 637,50 TL'yi 16 Ekim 2026 tarihinde ödeyeceğim.",
            "Evet, 1.250,50 TL'yi on altı Ekim'de ödeyeceğim.",
            'Evet, 600 TL, 16 Ekim. Lütfen kaydedin.',
        ):
            with self.subTest(text=text):
                self.assertTrue(_kaan_clear_confirmation(text))
        for text in (
            'Hayır.', 'Evet ama ödeyemem.', 'Evet, belki.',
            'Eğer para gelirse onaylıyorum.', 'Önceden onayladım.',
            'Evet, sadece tutarı onaylıyorum.', 'Evet, tarih yanlış.',
            'Tutar doğru mu?', 'Evet, tarihi değiştirin.',
            "Evet, 637,50 TL'yi 16 Ekim'de ödeyemem.",
            'Evet, bir miktarını ödeyebilirim.',
            'Evet, tutarı onaylıyorum.', 'Evet, tarihi onaylıyorum.',
        ):
            with self.subTest(text=text):
                self.assertFalse(_kaan_clear_confirmation(text))

    def test_ai_question_refers_to_the_current_assistant(self):
        for text in (
            "Are you an AI?", "Am I talking to an AI here?",
            "Is it really AI speaking?", "Is this a digital assistant?",
        ):
            with self.subTest(text=text):
                self.assertEqual(_kaan_question_kind(text), "ai")

    def test_unrelated_ai_or_robot_words_do_not_trigger_assistant_answer(self):
        for text in (
            "What is the minimum payment for my robot vacuum purchase?",
            "Is the AI investment fund responsible for this charge?",
            "Could I pay next Friday? My robot vacuum broke.",
            "My robot vacuum broke.",
        ):
            with self.subTest(text=text):
                self.assertEqual(_kaan_question_kind(text), "")
        self.assertEqual(_kaan_question_kind("Is this a scam?"), "scam")
        self.assertEqual(_kaan_question_kind('Siz bir yapay zekâ mısınız?'), 'ai')
        self.assertEqual(_kaan_question_kind('Bu bir dolandırıcılık mı?'), 'scam')
        self.assertEqual(_kaan_question_kind('Robot süpürgem için ne kadar ödemeliyim?'), '')


if __name__ == "__main__":
    unittest.main()
