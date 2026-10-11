import inspect
import unittest

from builder.compiler import compile_candidate
from builder.language import normalize_amount_input, normalize_date_input
from builder.validation import _parse, _run_check, _writes
from tests.test_confirmation_return import advance, interrupted_candidate
from tests.test_focused_conversation import snippet


class LanguageTests(unittest.TestCase):
    def test_portable_input_helpers_have_no_runtime_dependencies(self):
        for helper in (normalize_amount_input, normalize_date_input):
            _writes(_parse(inspect.getsource(helper)))

    def test_exact_and_relative_dates_use_only_the_supplied_call_anchor(self):
        cases = {
            'bugün': '2026-10-14', 'yarın': '2026-10-15',
            '16 EKİM 2026': '2026-10-16', 'on altı Ekim 2026': '2026-10-16',
            '16.10.2026': '2026-10-16', 'October sixteenth, 2026': '2026-10-16',
            'bu cuma': '2026-10-16', 'gelecek pazartesi': '2026-10-19',
            'Cuma on altı': '2026-10-16',
            '16 Ekim': '2026-10-16', 'on altı Ekim': '2026-10-16',
            "16 Ekim'de": '2026-10-16',
        }
        for raw, expected in cases.items():
            with self.subTest(raw=raw):
                self.assertEqual(normalize_date_input(raw, '2026-10-14T11:00', '2026-10-23'), expected)
        self.assertEqual(normalize_date_input('2 Ocak', '2026-12-30', '2027-01-05'), '2027-01-02')
        self.assertEqual(normalize_date_input('on altı Ekim', '2026-10-14'), '16 october')

    def test_vague_ambiguous_impossible_and_corrected_dates_stay_unaccepted(self):
        for raw in ('gelecek hafta', 'belki 16 Ekim', '16 Ekim veya 17 Ekim',
                    '31 Şubat 2026', '15 Ekim, ama değiştirin', 'Cuma on yedi'):
            with self.subTest(raw=raw):
                self.assertEqual(normalize_date_input(raw, '2026-10-14', '2026-10-23'), '')
        self.assertEqual(normalize_date_input('16 Ekim', '2026-10-14', '2027-10-23'), '')
        self.assertEqual(normalize_date_input('cuma', '2026-10-14', '2026-10-23'), '')

    def test_birth_dates_need_a_complete_year(self):
        for raw in ('14 Mart 1988', 'on dört Mart 1988', '14.03.1988', 'Doğum tarihim 14 Mart 1988'):
            self.assertEqual(normalize_date_input(raw, identity=True), '1988-03-14')
        for raw in ('14 Mart', 'yarın', 'bu cuma', '1988', '31 Şubat 1988'):
            self.assertEqual(normalize_date_input(raw, '2026-10-14', '2026-10-23', identity=True), '')

    def test_decimal_comma_amounts_keep_whole_value_and_ambiguity(self):
        for raw, expected in (('637,50 TL', '637.50'), ('1.250,50 TL', '1250.50'),
                              ('1.250 TL', '1250'), ('1.250', '1.250'),
                              ("600 TL'yi", '600'), ('-5,00', '-5.00'),
                              ('1,250', '1,250'), ('600 dollars', '600 dollars'),
                              ('600 ama 16 Ekim', '600 ama 16 Ekim')):
            self.assertEqual(normalize_amount_input(raw), expected)

    def test_current_identity_date_text_is_a_fallback_without_guessing_a_year(self):
        original = interrupted_candidate()
        answer_field = original['policy']['security']['validation_state']['identity_answer']
        original['policy']['security']['language_input'] = {
            'now_variable': 'now', 'identity_date_fields': [answer_field],
        }
        code = original['workflow']['nodes']['decision']['pre_actions'][0]['function']['parameters']['properties']['code']
        code['default'] = "vars['seen_date_answer'] = vars.get(" + repr(answer_field) + ")\n" + code['default']
        compiled, _ = compile_candidate(original)
        for text, expected in (('Doğum tarihim on dört Mart 1988', '1988-03-14'),
                               ('Doğum tarihim 14 Mart', ''), ('Belki 14 Mart 1988', '')):
            state = dict(compiled['policy']['security']['validation_fixture'],
                         stage='identity', identity_answer='', speech_text=text, speech_event='answer')
            state[answer_field] = ''
            output = _run_check(snippet(compiled['workflow'], 'decision'), {'vars': state, 'expected': {}})['vars']
            self.assertEqual(output['seen_date_answer'], expected)

    def test_compiled_guards_actually_use_turkish_dates_amounts_and_consent(self):
        original = interrupted_candidate()
        original['policy']['security']['language_input'] = {
            'now_variable': 'now', 'deadline_variable': 'deadline', 'identity_date_fields': [],
        }
        compiled, _ = compile_candidate(original)
        self.assertEqual(compile_candidate(compiled)[0], compiled)
        for name in ('decision', 'offer', 'approval'):
            _writes(_parse(snippet(compiled['workflow'], name)))
        state = dict(compiled['policy']['security']['validation_fixture'],
                     now='2026-10-14T11:00', deadline='2026-10-23',
                     speech_event='yes', speech_text="Evet, 35,00 TL'yi 16 Ekim'de ödeyeceğim.",
                     speech_amount='35,00 TL', speech_date='on altı Ekim')
        state, target = advance(compiled['workflow'], 'decision', state)
        self.assertEqual(target, 'confirmation')
        self.assertEqual(state['validated_amount'], 35.0)
        self.assertEqual(state['validated_date'], '2026-10-16')
        self.assertEqual(state['record_authorization'], '')
        state.update(approval='yes', approval_text='Evet, tutarı ve tarihi onaylıyorum.',
                     approval_amount='35,00 TL', approval_date='16 Ekim', correction='')
        state, target = advance(compiled['workflow'], 'approval', state)
        self.assertEqual(target, 'record')
        self.assertEqual(state['record_authorization'], 'authorized')
        readback, target = advance(compiled['workflow'], 'offer', dict(
            compiled['policy']['security']['validation_fixture'], write_attempts=0, write_result=''))
        self.assertEqual(target, 'confirmation')
        for text in ('Evet ama ödeyemem.', 'Tutar doğru mu?', 'Evet, sadece tutarı onaylıyorum.',
                     'Evet, tutarı onaylıyorum.', 'Evet, tarihi onaylıyorum.',
                     'Yes, I confirm the amount.', 'Yes, I confirm the date.'):
            denied, target = advance(compiled['workflow'], 'approval', dict(readback,
                approval='yes', approval_text=text, approval_amount='', approval_date='', correction=''))
            self.assertEqual(denied['record_authorization'], '')
            self.assertNotEqual(target, 'record')


if __name__ == '__main__':
    unittest.main()
