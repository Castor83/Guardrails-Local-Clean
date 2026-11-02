"""Real QualityPipeline provider with explicitly synthetic, offline evaluator fixtures."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import shutil
import sys
import tempfile
import weakref

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT / 'src'))
_OWNED_LOOPBACK_LISTENERS = weakref.WeakSet()


def _deny_remote_or_model_process(event, args):
    # Windows asyncio creates an internal loopback socketpair. Permit only a
    # connection to this process's own ephemeral listener, never Ollama/HTTP.
    if event == 'socket.bind' and isinstance(args[1], tuple) and args[1] == ('127.0.0.1', 0):
        _OWNED_LOOPBACK_LISTENERS.add(args[0])
    if event in {'socket.connect', 'socket.connect_ex'} and isinstance(args[1], tuple):
        import socket
        for listener in list(_OWNED_LOOPBACK_LISTENERS):
            try:
                if listener.getsockname() == args[1] and listener.getsockopt(socket.SOL_SOCKET, socket.SO_ACCEPTCONN):
                    return
            except OSError:
                continue
    if event in {'socket.connect', 'socket.connect_ex', 'socket.sendto', 'socket.getaddrinfo',
                 'socket.gethostbyname', 'subprocess.Popen', 'os.system'}:
        raise PermissionError('Promptfoo fixture worker forbids network and model subprocesses: ' + event)


sys.addaudithook(_deny_remote_or_model_process)


def call_api(prompt, options, context):
    """Evaluate the actual product pipeline, never substitute a pipeline double."""
    from guardrails_local.promptfoo_runner import _fixed_cases, _canonical_hash
    from guardrails_local.quality_pipeline import QualityPipeline, contract_hash
    from guardrails_local.action_evidence import record_tool_result

    cases = _fixed_cases(PROJECT_ROOT)
    case_id = context.get('vars', {}).get('case_id')
    case = next((item for item in cases if item['id'] == case_id), None)
    if case is None or prompt.strip() != case_id:
        return {'error': 'Unknown fixed regression case.'}
    request = deepcopy(case['request'])
    original = deepcopy(request)
    evaluator_calls, corrector_calls, observed_contracts = [], [], []
    run_area = PROJECT_ROOT / 'work/promptfoo-runtime/cases'
    run_area.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=case_id + '-', dir=run_area) as temporary:
        root = Path(temporary)
        if 'session_id' in request:
            configuration = root / 'work/codex/config.json'
            configuration.parent.mkdir(parents=True)
            configuration.write_text(json.dumps(dict(enabled=True, critic_enabled=False,
                session_ids=[request['session_id']], action_evidence_session_ids=[request['session_id']])),
                encoding='utf-8')
        # Real profile modules read only fixed hash-pinned components in this
        # isolated fixture root. Fake receipts are never written to the project.
        source = PROJECT_ROOT / 'work/profile-components'
        target = root / 'work/profile-components'
        target.mkdir(parents=True)
        shutil.copyfile(source / 'manifest.json', target / 'manifest.json')
        for key in ('valid_length', 'valid_url'):
            (target / key).mkdir()
            shutil.copyfile(source / key / 'main.py', target / key / 'main.py')
        if case.get('receipt_title'):
            record_tool_result(root, request['session_id'], request['turn_id'],
                'mcp__codex_app__list_threads', 'call_fixture_title', {},
                {'structuredContent': {'threads': [{'id': 'fixture-thread', 'title': case['receipt_title']}]},
                 'isError': False})

        def evaluator(current):
            evaluator_calls.append(deepcopy(current))
            observed_contracts.append(contract_hash(current))
            statuses = case.get('evaluator_statuses', ['PASS'])
            status = statuses[min(len(evaluator_calls) - 1, len(statuses) - 1)]
            result = dict(status=status, framework='deepeval', native_metric=False, fixture=True,
                task_sha256=hashlib.sha256(current['task'].encode('utf-8')).hexdigest(),
                answer_sha256=hashlib.sha256(current['answer'].encode('utf-8')).hexdigest(),
                contract_sha256=contract_hash(current),
                reason='Explizites synthetisches Regressionsurteil; kein DeepEval-Modell ausgeführt.')
            if status in {'PASS', 'FAIL'}:
                result['score'] = 1 if status == 'PASS' else 0
            return result

        def corrector(current, feedback, index):
            corrector_calls.append(deepcopy(current))
            observed_contracts.append(contract_hash(current))
            corrections = case.get('corrections', [])
            return corrections[min(index - 1, len(corrections) - 1)] if corrections else current['answer']

        report = QualityPipeline(root).run(request, evaluator=evaluator,
            corrector=corrector if case.get('max_corrections', 0) else None,
            max_corrections=case.get('max_corrections', 0))
        output = dict(case_id=case_id, case_sha256=_canonical_hash(case),
            final_status=report['final_status'], assessment_status=report.get('assessment_status'),
            released_text=report.get('released_text'), verified=report.get('verified'),
            fixture=True, native_metric=False, model_called=False,
            evaluator_calls=len(evaluator_calls), corrector_calls=len(corrector_calls),
            attempt_count=len(report.get('attempts', [])),
            pipeline_error=report.get('error'),
            original_contract_preserved=(request == original and all(
                value == contract_hash(original) for value in observed_contracts)),
            pipeline_framework=type(QualityPipeline(root)).__module__)
        return {'output': json.dumps(output, ensure_ascii=False), 'cached': False,
                'tokenUsage': {'total': 0, 'prompt': 0, 'completion': 0, 'numRequests': 0}, 'cost': 0}
