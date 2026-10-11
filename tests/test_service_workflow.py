"""Offline synthetic service checks; no final-case values or network calls."""
import copy
import inspect
import unittest

from builder.compiler import _service_clear_confirmation, _service_matches_schema, compile_candidate
from builder.validation import _parse, _run_check, validate


def route(target, variable=None, operand=None):
    condition = {'operator': 'always'} if variable is None else {
        'logic': 'or', 'conditions': [{'variable': variable, 'operator': 'equals', 'operand': operand}]}
    return {'target_node': target, 'condition': condition, 'description': target}


def code_node(name, code, transitions):
    return {'name': name, 'node_type': 'code', 'passthrough': True,
            'passthrough_default_transition': 'retry', 'transitions': transitions,
            'pre_actions': [{'type': 'function', 'function': {
                'name': 'code_exec', 'handler': '__function__:code_exec', 'description': 'Check current source-derived state.',
                'parameters': {'type': 'object', 'properties': {'code': {'type': 'string', 'default': code}}}}}]}


def listener(name, text, target, extract=False):
    fields = [{'name': key, 'type': 'string', 'min_confidence': 0, 'max_retries': 1}
              for key in ('raw_text', 'raw_event', 'raw_choice', 'raw_day')] if extract else []
    return {'name': name, 'node_type': 'conversation', 'on_enter': {'type': 'tts', 'text': text},
            'extraction_schema': fields, 'transitions': [route(target)]}


def candidate(read_only=False):
    operation = 'inspectItem' if read_only else 'adjustItem'
    request_schema = {'type': 'object', 'required': ['data'], 'properties': {
        'data': {'type': 'object', 'required': ['actorRef', 'slot'], 'properties': {
            'actorRef': {'type': 'string'}, 'slot': {'type': 'integer', 'minimum': 1, 'maximum': 9}}}}}
    success_schema = {'type': 'object', 'required': ['receipt', 'state'], 'properties': {
        'receipt': {'type': 'string'}, 'state': {'type': 'string'}}}
    openapi = {'openapi': '3.0.3', 'servers': [{'url': 'https://service.invalid'}], 'paths': {
        '/items': {'post': {'operationId': operation,
                           'requestBody': {'content': {'application/json': {'schema': request_schema}}},
                           'responses': {'200': {'content': {'application/json': {'schema': success_schema}}},
                                         '404': {'content': {'application/json': {'schema': {
                                             'type': 'object', 'properties': {'warning': {'type': 'string'}}}}}},
                                         '503': {'description': 'Unavailable'}}}}}}
    if not read_only:
        openapi['paths']['/items']['post']['x-business-success'] = {'path': 'state', 'operand': 'committed'}
    fixture = {'actor': 'SYNTHETIC-CALLER', 'anchor': '2040-03-04', 'slot': 2,
               'fingerprint': 'item:synthetic|slot:2', 'readback': 'item:synthetic|slot:2',
               'raw_text': 'Evet, lütfen.', 'raw_event': 'yes', 'raw_choice': '', 'raw_day': ''}
    guard_code = "vars['route'] = 'retry'\nvars['speech'] = 'İşlem tamamlanmadı.'\n"
    if not read_only:
        guard_code += ("if vars.get('raw_event') == 'yes' and vars.get('raw_text'):\n"
                       "    vars['authorization'] = 'allow'\n")
    result_code = ("vars['route'] = 'retry'\nvars['speech'] = 'İşlem tamamlanmadı.'\n"
                   "if str(vars.get('action_response.status_code')) == '200':\n"
                   "    vars['current_success'] = 'done'\n"
                   "    vars['route'] = 'done'\n"
                   "    vars['speech'] = 'İşlem tamamlandı.'\n")
    action = {'name': 'action', 'node_type': 'api_request', 'passthrough': True,
              'transitions': [route('result')], 'pre_actions': [{'type': 'function', 'config': {'maxRetries': 0},
                  'function': {'name': operation, 'handler': '__function__:api_call', 'description': 'Run the sourced item operation.',
                      'parameters': {'type': 'object', 'properties': {
                          'url': {'type': 'string', 'default': 'https://service.invalid/items'},
                          'method': {'type': 'string', 'default': 'POST'},
                          'connect_retries': {'type': 'integer', 'default': 0},
                          'body': {'type': 'object', 'required': ['data'], 'properties': {
                              'data': {'type': 'object', 'required': ['actorRef', 'slot'], 'properties': {
                                  'actorRef': {'type': 'string', 'default': '{{actor}}'},
                                  'slot': {'type': 'integer', 'default': '{{slot}}'}}}}}}}}}]}
    nodes = {
        'opening': listener('opening', 'Seçilen işlem için onay verir misiniz?', 'entry', True),
        'entry': code_node('entry', guard_code, [route('action')] if read_only else [route('action', 'authorization', 'allow'), route('retry')]),
        'action': action,
        'result': code_node('result', result_code, [route('done', 'current_success', 'done'), route('retry')]),
        'retry': listener('retry', 'İşlem tamamlanmadı. Tekrar söyler misiniz?', 'reset', True),
        'reset': code_node('reset', "vars['route'] = 'opening'", [route('opening')]),
        'done': {'name': 'done', 'node_type': 'end_call', 'transitions': [], 'terminal': {'function': {
            'name': 'finish', 'handler': '__function__:end_call', 'parameters': {'type': 'object', 'properties': {
                'message_mode': {'type': 'string', 'default': 'custom'},
                'spoken_message': {'type': 'string', 'default': 'İşlem tamamlandı. İyi günler.'}}}}}}
    }
    result = {'entry_node': 'entry', 'result_node': 'result', 'success_variable': 'current_success',
              'success_operand': 'done', 'success_statuses': [200], 'required_response_fields': ['data.receipt'],
              'route_variable': 'route', 'failure_route': 'retry', 'speech_variable': 'speech',
              'failure_text': 'İşlem tamamlanmadı.', 'fixture': copy.deepcopy(fixture),
              'success_result': {'status': 'success', 'status_code': 200, 'data': {'receipt': 'synthetic', 'state': 'committed'}}}
    if not read_only:
        result['business_success'] = {'path': 'data.state', 'operand': 'committed'}
    security = {'context_variables': ['actor', 'anchor'], 'trusted_variables': ['slot', 'fingerprint', 'readback', 'authorization', 'current_success', 'route', 'speech'],
                'customer_id_field': 'data.actorRef', 'customer_id_variable': 'actor',
                'context_bindings': {'data.actorRef': 'actor'}, 'api_results': {'action': result}, 'action_guards': {}}
    if not read_only:
        security['action_guards'][operation] = {'node': 'entry', 'target': 'action', 'variable': 'authorization', 'operand': 'allow',
            'source_rule': 'R1', 'consent_required': True, 'confirmation_required': True,
            'text_field': 'raw_text', 'event_field': 'raw_event', 'value_fields': ['raw_choice', 'raw_day'],
            'confirmation_nodes': ['opening'], 'fingerprint_variable': 'fingerprint', 'readback_fingerprint_variable': 'readback',
            'consent_phrases': ['gönderin', 'tarihi onaylıyorum'], 'fixture': copy.deepcopy(fixture), 'valid_text': 'Evet, lütfen.'}
    return {'workflow': {'initial_node': 'opening', 'nodes': nodes},
            'policy': {'workflow_kind': 'service', 'source_rules': [{'id': 'R1', 'source': 'synthetic.md', 'line': 1, 'text': 'Use the identified caller for the item operation.'}],
                       'unsupported': [], 'security': security,
                       'service_operations': {operation: {'effect': 'read' if read_only else 'write', 'source_rule': 'R1'}}},
            'openapi': openapi, 'checks': [{'name': 'current-result', 'node_id': 'result',
                'vars': {'action_response.status_code': 200, 'action_response.data': {'receipt': 'synthetic', 'state': 'committed'}, 'action_response.data.receipt': 'synthetic', 'action_response.data.state': 'committed'},
                'expected': {'current_success': 'done'}}]}


def compiled_report(value):
    compiled, changes = compile_candidate(value, value['openapi'])
    return compiled, changes, validate(compiled['workflow'], compiled['policy'], compiled['openapi'], compiled['checks'])


class ServiceWorkflowTests(unittest.TestCase):
    def test_allof_keeps_shared_required_fields_types_and_enum_constraints(self):
        value = candidate()
        operation = value['openapi']['paths']['/items']['post']
        original = operation['responses']['200']['content']['application/json']['schema']
        value['openapi']['components'] = {'schemas': {'SharedResult': original}}
        operation['responses']['200']['content']['application/json']['schema'] = {
            'allOf': [{'$ref': '#/components/schemas/SharedResult'}, {'type': 'object', 'required': ['progress'],
                       'properties': {'progress': {'type': 'string', 'enum': ['READY']}, 'state': {'enum': ['committed']}}}]}
        value['policy']['security']['api_results']['action']['success_result']['data']['progress'] = 'READY'
        value['checks'][0]['vars']['action_response.data']['progress'] = 'READY'
        compiled, _, report = compiled_report(value)
        self.assertTrue(report['ok'], report['errors'])
        code = compiled['workflow']['nodes']['result']['pre_actions'][0]['function']['parameters']['properties']['code']['default']
        for body in ({'receipt': 'synthetic', 'state': 'committed', 'progress': 'WAIT'},
                     {'receipt': 'synthetic', 'state': 'committed'},
                     {'state': 'committed', 'progress': 'READY'},
                     {'receipt': [], 'state': 'committed', 'progress': 'READY'}):
            _run_check(code, {'vars': {'action_response.status_code': 200, 'action_response.data': body},
                              'expected': {'current_success': '', 'speech': 'İşlem tamamlanmadı.'}})
        self.assertFalse(_service_matches_schema({'code': 9}, {'allOf': [
            {'type': 'object', 'required': ['code'], 'properties': {'code': {'type': 'integer'}}},
            {'properties': {'code': {'enum': [0]}}}]}))

    def test_confirmed_service_passes_independent_guards_and_nested_requests(self):
        compiled, changes, report = compiled_report(candidate())
        self.assertTrue(report['ok'], report['errors'])
        self.assertGreaterEqual(len(report['checks']), 15)
        again, _ = compile_candidate(compiled, compiled['openapi'])
        self.assertEqual(again, compiled)
        self.assertTrue(changes)

    def test_read_only_service_needs_no_collections_roles_or_invented_body_flag(self):
        _, _, report = compiled_report(candidate(True))
        self.assertTrue(report['ok'], report['errors'])
        self.assertFalse(any('identity' in error or 'promise' in error for error in report['errors']))

    def test_one_field_turkish_consent_is_bounded_and_portable(self):
        _parse(inspect.getsource(_service_clear_confirmation))
        phrases = ['gönderin', 'tarihi onaylıyorum']
        for raw in ['yes', 'Evet, lütfen.', 'Evet gönderin', 'Tarihi onaylıyorum', 'Evet, gönderin, teşekkürler.']:
            self.assertTrue(_service_clear_confirmation(raw, phrases), raw)
        for raw in ['Hayır', 'Belki evet', 'Eğer uygunsa evet', 'Daha önce evet demiştim', 'Gönderin mi?', 'Evet ama göndermeyin', 'yes if ready', 'evet işlemi değiştirdim']:
            self.assertFalse(_service_clear_confirmation(raw, phrases), raw)
        self.assertFalse(_service_clear_confirmation('tarihi onaylıyorum', []))

    def test_sourced_warning_is_honest_and_old_warning_evidence_is_reset(self):
        value = candidate(True)
        metadata = value['policy']['security']['api_results']['action']
        metadata['error_outcomes'] = [{'status': 404, 'path': 'data.warning', 'operand': 'empty', 'route': 'nothing', 'speech': 'Kayıt bulunamadı.', 'source_rule': 'R1'}]
        nodes = value['workflow']['nodes']
        nodes['result']['transitions'].insert(-1, route('nothing', 'route', 'nothing'))
        nodes['nothing'] = copy.deepcopy(nodes['done'])
        nodes['nothing']['name'] = 'nothing'
        nodes['nothing']['terminal']['function']['parameters']['properties']['spoken_message']['default'] = 'Kayıt bulunamadı.'
        compiled, _, report = compiled_report(value)
        self.assertTrue(report['ok'], report['errors'])
        code = compiled['workflow']['nodes']['entry']['pre_actions'][0]['function']['parameters']['properties']['code']['default']
        state = _run_check(code, {'vars': {'action_response.data.warning': 'empty'}, 'expected': {'action_response.data.warning': ''}})['vars']
        self.assertEqual(state['action_response.data.warning'], '')

    def test_response_evidence_cannot_be_forged_after_reset(self):
        value = candidate()
        code = value['workflow']['nodes']['entry']['pre_actions'][0]['function']['parameters']['properties']['code']
        code['default'] += "vars['action_response.status_code'] = 200\nvars['action_response.data.receipt'] = 'OLD'\n"
        _, _, report = compiled_report(value)
        self.assertFalse(report['ok'])
        self.assertTrue(any('response evidence is read-only' in error for error in report['errors']))

    def test_snapshot_mutation_and_forged_compiler_markers_are_rejected(self):
        mutation = ("if isinstance(_service_current_body, dict) and _service_current_body.get('state') == 'rejected':\n"
                    "    _service_current_body['state'] = 'committed'\n")
        for prefix, suffix in [('', ''), ('# BEGIN KAAN SERVICE FAKE\n', '# END KAAN SERVICE FAKE\n')]:
            value = candidate()
            code = value['workflow']['nodes']['result']['pre_actions'][0]['function']['parameters']['properties']['code']
            code['default'] = prefix + mutation + suffix + code['default']
            _, _, report = compiled_report(value)
            self.assertFalse(report['ok'])
            self.assertTrue(any('compiler-owned' in error for error in report['errors']))

    def test_source_flag_cannot_be_omitted_and_required_response_types_are_enforced(self):
        value = candidate()
        del value['policy']['security']['api_results']['action']['business_success']
        _, _, report = compiled_report(value)
        self.assertFalse(report['ok'])
        self.assertTrue(any('source-contract success' in error for error in report['errors']))
        compiled, _, report = compiled_report(candidate())
        self.assertTrue(report['ok'], report['errors'])
        code = compiled['workflow']['nodes']['result']['pre_actions'][0]['function']['parameters']['properties']['code']['default']
        for body in ({'receipt': [], 'state': 'committed'}, {'receipt': 'synthetic'}, {'receipt': 'synthetic', 'state': 'rejected'}):
            _run_check(code, {'vars': {'action_response.status_code': 200, 'action_response.data': body}, 'expected': {'current_success': '', 'speech': 'İşlem tamamlanmadı.'}})

    def test_failure_graph_cannot_speak_a_successful_terminal(self):
        value = candidate()
        value['workflow']['nodes']['result']['transitions'] = [route('done')]
        _, _, report = compiled_report(value)
        self.assertFalse(report['ok'])
        self.assertTrue(any('failure graph' in error for error in report['errors']))

    def test_date_anchor_and_raw_input_bindings_are_source_guarded(self):
        for language in [{'now_variable': 'raw_text', 'date_fields': {'entry': ['raw_day']}},
                         {'now_variable': 'anchor', 'date_fields': {'entry': ['slot']}}]:
            value = candidate(True)
            value['policy']['security']['language_input'] = language
            _, _, report = compiled_report(value)
            self.assertFalse(report['ok'])

    def test_invalid_url_raw_binding_context_mutation_and_guard_bypass_are_rejected(self):
        changes = [
            ('url', lambda v: v['workflow']['nodes']['action']['pre_actions'][0]['function']['parameters']['properties']['url'].update(default='https://wrong.invalid/items')),
            ('raw speech', lambda v: v['workflow']['nodes']['action']['pre_actions'][0]['function']['parameters']['properties']['body']['properties']['data']['properties']['slot'].update(default='{{raw_choice}}')),
            ('context', lambda v: v['workflow']['nodes']['reset']['pre_actions'][0]['function']['parameters']['properties']['code'].update(default="vars['actor'] = 'OTHER'")),
            ('bypass', lambda v: v['workflow']['nodes']['reset']['transitions'].append(route('action'))),
        ]
        for name, change in changes:
            with self.subTest(name=name):
                value = candidate()
                change(value)
                _, _, report = compiled_report(value)
                self.assertFalse(report['ok'])

    def test_missing_real_response_field_and_shared_result_nodes_are_rejected(self):
        value = candidate(True)
        value['policy']['security']['api_results']['action']['required_response_fields'] = ['data.invented']
        _, _, report = compiled_report(value)
        self.assertFalse(report['ok'])
        self.assertTrue(any('absent from' in error for error in report['errors']))
        value = candidate(True)
        value['policy']['security']['api_results']['another'] = copy.deepcopy(value['policy']['security']['api_results']['action'])
        report = validate(value['workflow'], value['policy'], value['openapi'], value['checks'])
        self.assertFalse(report['ok'])
        self.assertTrue(any('separate current-result' in error for error in report['errors']))

    def test_declared_raw_date_normalizes_with_supplied_anchor(self):
        value = candidate(True)
        value['policy']['security']['language_input'] = {'now_variable': 'anchor', 'date_fields': {'entry': ['raw_day']}}
        compiled, _, report = compiled_report(value)
        self.assertTrue(report['ok'], report['errors'])
        code = compiled['workflow']['nodes']['entry']['pre_actions'][0]['function']['parameters']['properties']['code']['default']
        _run_check(code, {'vars': {'raw_day': 'yarın', 'anchor': '2040-03-04'}, 'expected': {'raw_day': '2040-03-05'}})


if __name__ == '__main__':
    unittest.main()
