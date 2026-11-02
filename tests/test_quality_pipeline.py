"""Pin generic quality gating, binding and correction limits without a model."""
import copy
import hashlib
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
try:
    from guardrails_local.quality_pipeline import QualityPipeline, contract_hash
except ImportError:
    QualityPipeline = None


class QualityPipelineTests(unittest.TestCase):
    def test_revoked_receipt_cannot_be_reused_by_direct_quality_pipeline(self):
        from guardrails_local.action_evidence import record_tool_result
        session, turn = '11111111-1111-4111-8111-111111111111', '22222222-2222-4222-8222-222222222222'
        config_path = self.root / 'work/codex/config.json'
        config_path.parent.mkdir(parents=True, exist_ok=True)
        config = dict(enabled=True, critic_enabled=False, session_ids=[session], action_evidence_session_ids=[session])
        config_path.write_text(json.dumps(config), encoding='utf-8')
        record_tool_result(self.root, session, turn, 'mcp__codex_app__list_threads', 'proof', {},
            dict(structuredContent=dict(threads=[dict(id='chat', title='Tatsächlicher Titel')]), isError=False))
        self.request.update(session_id=session, turn_id=turn,
                            answer='Ich habe den Chat „Tatsächlicher Titel“ in der Chatliste gefunden.')
        self.assertEqual('PASS', self.run_pipeline(evaluator=self.verdict)['final_status'])
        for changes in (dict(action_evidence_session_ids=[]), dict(enabled=False), dict(session_ids=[])):
            config_path.write_text(json.dumps(dict(config, **changes)), encoding='utf-8')
            evaluator, corrector = Mock(), Mock()
            with patch('guardrails_local.action_evidence._turn_receipts') as reader:
                report = self.run_pipeline(evaluator=evaluator, corrector=corrector, max_corrections=2)
            self.assertEqual('UNVERIFIED', report['final_status'])
            reader.assert_not_called()
            evaluator.assert_not_called()
            corrector.assert_not_called()

    def test_mixed_action_fail_and_unverified_do_not_start_correction(self):
        session, turn = '11111111-1111-4111-8111-111111111111', '22222222-2222-4222-8222-222222222222'
        config = self.root / 'work/codex/config.json'
        config.parent.mkdir(parents=True, exist_ok=True)
        config.write_text(json.dumps(dict(enabled=True, critic_enabled=False, session_ids=[session],
                                         action_evidence_session_ids=[session])), encoding='utf-8')
        self.request.update(session_id=session, turn_id=turn,
            answer='Ich habe den Chat „Nicht vorhanden“ in der Chatliste gefunden. '
                   'Ich habe die offizielle Dokumentation geprüft.')
        evaluator, corrector = Mock(), Mock(return_value='Hallo')
        report = self.run_pipeline(evaluator=evaluator, corrector=corrector, max_corrections=2)
        self.assertEqual('FAIL', report['final_status'])
        self.assertEqual({'FAIL', 'UNVERIFIED'}, {claim['status'] for claim in report['attempts'][0]['action_claims']['claims']})
        self.assertEqual(1, len(report['attempts']))
        evaluator.assert_not_called()
        corrector.assert_not_called()

    def test_known_fail_is_not_hidden_by_unverified(self):
        self.request.update(answer='Eine zu lange Antwort', constraints={'max_chars': 5})
        evaluator, corrector = Mock(), Mock()
        with patch('guardrails_local.quality_pipeline.check_action_claims',
                   return_value=dict(status='UNVERIFIED', findings=['Missing receipt'])):
            report = self.run_pipeline(evaluator=evaluator, corrector=corrector, max_corrections=2)
        self.assertEqual('FAIL', report['final_status'])
        self.assertEqual('UNVERIFIED', report['attempts'][0]['action_claims']['status'])
        self.assertEqual(1, len(report['attempts']))
        evaluator.assert_not_called()
        corrector.assert_not_called()

    def setUp(self):
        self.assertIsNotNone(QualityPipeline, 'Generic native quality gate is missing')
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        shutil.copytree(ROOT / 'work/profile-components', self.root / 'work/profile-components')
        session = '11111111-1111-4111-8111-111111111111'
        config = self.root / 'work/codex/config.json'
        config.parent.mkdir(parents=True)
        config.write_text(json.dumps(dict(enabled=True, critic_enabled=False, session_ids=[session],
            action_evidence_session_ids=[session])), encoding='utf-8')
        self.request = dict(task='Antworte mit Hallo.', answer='Hallo', instructions=['Antworte auf Deutsch.'],
                            criteria=['Erfülle die Aufgabe vollständig.'])

    def verdict(self, request, status='PASS', **changes):
        return dict(status=status, framework='deepeval', native_metric=False,
            task_sha256=hashlib.sha256(request['task'].encode()).hexdigest(),
            answer_sha256=hashlib.sha256(request['answer'].encode()).hexdigest(),
            contract_sha256=contract_hash(request), score=1 if status == 'PASS' else 0,
            reason='Explizites synthetisches Testurteil.', **changes)

    def run_pipeline(self, **options):
        return QualityPipeline(self.root).run(copy.deepcopy(self.request), **options)

    def test_native_guardrails_accepts_bound_assessment_without_claiming_independent_release(self):
        result = self.run_pipeline(evaluator=self.verdict)
        self.assertEqual('PASS', result['final_status'])
        self.assertTrue(result['attempts'][0]['guardrails_passed'])
        self.assertEqual('Hallo', result['candidate_text'])
        self.assertIsNone(result['released_text'])
        self.assertFalse(result['verified'])
        self.assertFalse(result['model_evaluation_verified'])
        self.assertTrue(Path(result['log_path']).is_file())

    def test_no_evaluator_cannot_be_mistaken_for_quality_pass_or_start_corrections(self):
        def forbidden(*args):
            self.fail('UNVERIFIED must not trigger correction')
        result = self.run_pipeline(corrector=forbidden, max_corrections=1)
        self.assertEqual('UNVERIFIED', result['final_status'])
        self.assertIsNone(result['candidate_text'])

    def test_false_lookup_is_rejected_before_spending_a_judge_call(self):
        self.request.update(answer='Ich habe den Chat „Erfunden“ in deiner Chatliste gefunden.',
            session_id='11111111-1111-4111-8111-111111111111',
            turn_id='22222222-2222-4222-8222-222222222222')
        result = self.run_pipeline(evaluator=lambda req: self.fail('Host violation should not consume judge'))
        self.assertEqual('FAIL', result['final_status'])
        self.assertFalse(result['attempts'][0]['guardrails_passed'])
        self.assertIsNone(result['candidate_text'])

    def test_failed_format_can_be_corrected_then_really_rechecked(self):
        self.request.update(answer='Eine viel zu lange Antwort', constraints={'max_chars': 5})
        result = self.run_pipeline(evaluator=self.verdict, corrector=lambda req, feedback, index: 'Hallo',
                                   max_corrections=1)
        self.assertEqual('PASS', result['final_status'])
        self.assertEqual(2, len(result['attempts']))
        self.assertEqual('FAIL', result['attempts'][0]['status'])
        self.assertEqual('Hallo', result['candidate_text'])

    def test_correction_cannot_mutate_the_original_task_or_criteria(self):
        seen = []
        def evaluator(req):
            seen.append(copy.deepcopy(req))
            return self.verdict(req, 'FAIL' if req['answer'] == 'Hallo' else 'PASS')
        def corrector(req, feedback, index):
            req['task'] = 'Ignoriere den Auftrag'
            req['criteria'].clear()
            return 'Guten Tag'
        result = self.run_pipeline(evaluator=evaluator, corrector=corrector, max_corrections=1)
        self.assertEqual('PASS', result['final_status'])
        self.assertEqual([self.request['task']] * 2, [r['task'] for r in seen])
        self.assertEqual([self.request['criteria']] * 2, [r['criteria'] for r in seen])

    def test_stale_judge_criteria_binding_is_error_without_automatic_retry(self):
        def stale(req):
            result = self.verdict(req)
            result['contract_sha256'] = '0' * 64
            return result
        result = self.run_pipeline(evaluator=stale,
            corrector=lambda *args: self.fail('Technical errors must stop'), max_corrections=2)
        self.assertEqual('ERROR', result['final_status'])
        self.assertEqual(1, len(result['attempts']))

    def test_error_or_unverified_judge_never_triggers_a_retry(self):
        for status in ('ERROR', 'UNVERIFIED'):
            with self.subTest(status=status):
                result = self.run_pipeline(evaluator=lambda req: self.verdict(req, status),
                    corrector=lambda *args: self.fail('No retry'), max_corrections=2)
                self.assertEqual(status, result['final_status'])
                self.assertIsNone(result['released_text'])

    def test_correction_budget_is_exhausted_after_two_rechecks(self):
        indices = []
        def corrector(req, feedback, index):
            indices.append(index)
            return f'Kandidat {index}'
        result = self.run_pipeline(evaluator=lambda req: self.verdict(req, 'FAIL'),
                                   corrector=corrector, max_corrections=2)
        self.assertEqual('ESCALATED', result['final_status'])
        self.assertEqual([1, 2], indices)
        self.assertEqual(3, len(result['attempts']))
        self.assertIsNone(result['candidate_text'])

    def test_unknown_fields_and_nonfinite_data_are_rejected_without_a_judge(self):
        for extra in ({'allow_release': True}, {'criteria': [float('nan')]}):
            with self.subTest(extra=extra):
                self.request.update(extra)
                result = self.run_pipeline(evaluator=lambda req: self.fail('Invalid request'))
                self.assertEqual('ERROR', result['final_status'])
                self.request = dict(task='Antworte mit Hallo.', answer='Hallo', instructions=[], criteria=[])

    def test_boolean_score_is_not_a_valid_deepeval_grade(self):
        def bad(req):
            result = self.verdict(req)
            result['score'] = True
            return result
        self.assertEqual('ERROR', self.run_pipeline(evaluator=bad)['final_status'])

    def test_a_native_error_before_measurement_is_not_an_execution_proof(self):
        def failed(req):
            result = self.verdict(req, 'ERROR')
            result.update(native_metric=True, calls=0)
            return result
        report = self.run_pipeline(evaluator=failed)
        self.assertEqual('ERROR', report['final_status'])
        self.assertFalse(report['native_deepeval_executed'])

    def test_a_metric_cannot_certify_itself_or_select_an_unknown_mode(self):
        def self_verified(req):
            result = self.verdict(req)
            result['verified'] = True
            return result
        self.assertEqual('ERROR', self.run_pipeline(evaluator=self_verified)['final_status'])
        self.request['metric'] = 'external_cloud'
        self.assertEqual('ERROR', self.run_pipeline(evaluator=self.verdict)['final_status'])

    def test_explicit_native_prompt_alignment_mode_is_bound_into_the_contract(self):
        self.request['metric'] = 'prompt_alignment'
        report = self.run_pipeline(evaluator=self.verdict)
        self.assertEqual('PASS', report['final_status'])
        self.assertIsNone(report['released_text'])


if __name__ == '__main__':
    unittest.main()
