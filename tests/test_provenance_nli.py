"""NLI admission and classification contracts; no ML imports or inference."""

import builtins
import importlib.util
import os
import json
import shutil
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
try:
    from guardrails_local import provenance_nli
except ImportError:
    provenance_nli = None


LABELS = {0: "entailment", 1: "neutral", 2: "contradiction"}


class NliContractTests(unittest.TestCase):
    def test_smoke_case_content_is_pinned_before_any_measurement(self):
        document = dict(schema_version=1, cases=[
            dict(id='source_supported', sources=['Berlin ist die Hauptstadt Deutschlands.'],
                 actual_output='Berlin ist die Hauptstadt Deutschlands.', expected_verdict='PASS'),
            dict(id='source_contradiction', sources=['Berlin ist die Hauptstadt Deutschlands.'],
                 actual_output='Bonn ist die Hauptstadt Deutschlands.', expected_verdict='FAIL')])
        path = self.root / 'changed.json'
        for changes in ({'actual_output': 'An unrelated statement.'}, {'expected_verdict': 'PASS'},
                        {'sources': ['Bonn ist die Hauptstadt Deutschlands.']}):
            changed = json.loads(json.dumps(document))
            changed['cases'][-1].update(changes)
            path.write_text(json.dumps(changed), encoding='utf-8')
            with patch.object(provenance_nli, 'validation_worker', side_effect=[
                    dict(status='PASS', native_validator=True), dict(status='FAIL', native_validator=True)]) as worker:
                report = provenance_nli.smoke_nli(self.root, path)
            self.assertEqual('UNVERIFIED', report['status'])
            worker.assert_not_called()

    def test_fresh_checkout_supplies_two_fixed_nli_cases(self):
        self.assertTrue((ROOT / 'examples/evals/nli-smoke.json').is_file())
        shutil.copytree(ROOT / 'examples/evals', self.root / 'examples/evals')
        seen = []
        def measure(root, request):
            seen.append(request)
            return dict(status='PASS' if request['value'].startswith('Berlin') else 'FAIL', native_validator=True)
        with patch.object(provenance_nli, 'validation_worker', side_effect=measure):
            report = provenance_nli.smoke_nli(self.root)
        self.assertEqual('PASS', report['status'])
        self.assertEqual(['Berlin ist die Hauptstadt Deutschlands.', 'Bonn ist die Hauptstadt Deutschlands.'],
                         [request['value'] for request in seen])

    def setUp(self):
        self.assertIsNotNone(
            provenance_nli, "The local, lazy-import Provenance NLI bridge is missing."
        )
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.model_path = self.root / "models" / "pinned-nli-classifier"
        self.model_path.mkdir(parents=True)
        self.source_file = self.root / "explicit-source.txt"
        self.source = "Berlin ist die Hauptstadt Deutschlands."
        self.value = "Berlin ist die Hauptstadt Deutschlands."
        self.source_file.write_text(self.source, encoding="utf-8")

    def admission(self, **changes):
        arguments = dict(
            value=self.value,
            sources=[self.source],
            model_path=str(self.model_path),
            token_count=20,
            max_tokens=512,
        )
        arguments.update(changes)
        return provenance_nli.admit_request(**arguments)

    def test_controller_module_import_does_not_import_ml_or_native_validators(self):
        forbidden = {
            "torch", "transformers", "guardrails", "guardrails_ai", "nltk",
            "numpy", "sentence_transformers", "deepeval",
        }
        real_import = builtins.__import__

        def stdlib_only(name, *args, **kwargs):
            if name.split(".", 1)[0] in forbidden:
                raise AssertionError("Controller imported optional ML dependency: " + name)
            return real_import(name, *args, **kwargs)

        name = "guardrails_local._provenance_nli_stdlib_import_check"
        spec = importlib.util.spec_from_file_location(name, provenance_nli.__file__)
        module = importlib.util.module_from_spec(spec)
        with patch.dict(sys.modules, {name: module}):
            with patch("builtins.__import__", side_effect=stdlib_only):
                spec.loader.exec_module(module)
        self.assertTrue(callable(module.check_nli))

    def test_worker_socket_guard_denies_network_without_opening_a_socket(self):
        # Exercise the audit callback itself; never install a permanent audit hook
        # in the shared CPU suite or attempt an actual network connection.
        for event in ("socket.connect", "socket.sendto", "socket.getaddrinfo"):
            with self.subTest(event=event):
                with self.assertRaises(PermissionError):
                    provenance_nli._offline_socket_audit(event, ())
        provenance_nli._offline_socket_audit("open", ())

    def test_ipv6_capability_bind_is_only_admitted_inside_synchronous_urllib3_import(self):
        imported = []

        def initialize(name, *args, **kwargs):
            self.assertEqual('urllib3', name)
            imported.append(name)
            provenance_nli._offline_socket_audit('socket.bind', (None, ('::1', 0)))
            with self.assertRaises(PermissionError):
                provenance_nli._offline_socket_audit('socket.connect', (None, ('::1', 0)))
            for address in (('::', 0), ('::1', 8080), ('127.0.0.1', 11434)):
                with self.subTest(address=address), self.assertRaises(PermissionError):
                    provenance_nli._offline_socket_audit('socket.bind', (None, address))

        with patch.object(provenance_nli, '_NETWORK_ATTEMPTS', []):
            with self.assertRaises(PermissionError):
                provenance_nli._offline_socket_audit('socket.bind', (None, ('::1', 0)))
            with patch('builtins.__import__', side_effect=initialize):
                provenance_nli._initialize_http_dependencies()
            self.assertEqual(['urllib3'], imported)
            with self.assertRaises(PermissionError):
                provenance_nli._offline_socket_audit('socket.bind', (None, ('::1', 0)))

    def test_failed_urllib3_import_closes_the_ipv6_probe_window(self):
        with patch('builtins.__import__', side_effect=RuntimeError('fixture import failure')):
            with self.assertRaisesRegex(RuntimeError, 'fixture import failure'):
                provenance_nli._initialize_http_dependencies()
        with patch.object(provenance_nli, '_NETWORK_ATTEMPTS', []):
            with self.assertRaises(PermissionError):
                provenance_nli._offline_socket_audit('socket.bind', (None, ('::1', 0)))

    def test_confident_entailment_is_supported(self):
        result = provenance_nli.evaluate_prediction([8.0, -1.0, -1.0], LABELS)
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(result["label"], "entailment")
        self.assertGreater(result["confidence"], 0.99)

    def test_neutral_is_rejected_even_when_entailment_exceeds_threshold(self):
        # softmax([1, 2, 0]) gives entailment > .2, but neutral wins.
        result = provenance_nli.evaluate_prediction(
            [1.0, 2.0, 0.0], LABELS, min_confidence=0.2
        )
        self.assertEqual(result["status"], "FAIL")
        self.assertEqual(result["label"], "neutral")

    def test_contradiction_is_rejected_even_when_entailment_exceeds_threshold(self):
        result = provenance_nli.evaluate_prediction(
            [1.0, 0.0, 2.0], LABELS, min_confidence=0.2
        )
        self.assertEqual(result["status"], "FAIL")
        self.assertEqual(result["label"], "contradiction")

    def test_configured_label_indices_are_used_instead_of_binary_zip(self):
        permuted = {"0": "contradiction", "1": "entailment", "2": "neutral"}
        result = provenance_nli.evaluate_prediction([-1.0, 8.0, -1.0], permuted)
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(result["label"], "entailment")

    def test_unknown_incomplete_or_duplicate_labels_cannot_be_accepted(self):
        bad_mappings = (
            {0: "LABEL_0", 1: "LABEL_1", 2: "LABEL_2"},
            {0: "entailment", 1: "not_entailment"},
            {0: "entailment", 1: "entailment", 2: "contradiction"},
            {0: "entailment", 1: "neutral", 3: "contradiction"},
        )
        for mapping in bad_mappings:
            with self.subTest(mapping=mapping):
                result = provenance_nli.evaluate_prediction([8.0, -1.0, -1.0], mapping)
                self.assertEqual(result["status"], "UNVERIFIED")

    def test_nonfinite_or_wrong_sized_logits_cannot_pass(self):
        for logits in (
            [float("nan"), 0.0, 0.0],
            [float("inf"), 0.0, 0.0],
            [float("-inf"), 0.0, 0.0],
            [8.0, 0.0],
            [8.0, 0.0, 0.0, 0.0],
        ):
            with self.subTest(logits=logits):
                self.assertEqual(
                    provenance_nli.evaluate_prediction(logits, LABELS)["status"],
                    "UNVERIFIED",
                )

    def test_low_confidence_entailment_does_not_pass(self):
        result = provenance_nli.evaluate_prediction(
            [0.1, 0.0, 0.0], LABELS, min_confidence=0.8
        )
        self.assertNotEqual(result["status"], "PASS")

    def test_complete_pair_at_token_limit_can_be_admitted(self):
        self.assertEqual(self.admission(token_count=512)["status"], "PASS")

    def test_pair_above_limit_is_unverified_instead_of_truncated(self):
        self.assertEqual(self.admission(token_count=513)["status"], "UNVERIFIED")

    def test_no_source_or_empty_source_does_not_become_a_factuality_pass(self):
        for sources in (None, [], [""], ["   "], "not an explicit source list"):
            with self.subTest(sources=sources):
                self.assertEqual(self.admission(sources=sources)["status"], "UNVERIFIED")

    def test_empty_answer_is_not_vacuously_accepted(self):
        for value in ("", " \n\t"):
            with self.subTest(value=value):
                self.assertEqual(self.admission(value=value)["status"], "UNVERIFIED")

    def test_remote_hub_or_network_model_location_is_rejected(self):
        for location in (
            "MoritzLaurer/multilingual-MiniLMv2-L6-mnli-xnli",
            "https://huggingface.co/example/model",
            "http://127.0.0.1:8000/inference",
            "\\\\server\\share\\model",
        ):
            with self.subTest(location=location):
                self.assertEqual(
                    self.admission(model_path=location)["status"], "UNVERIFIED"
                )

    def test_live_bridge_without_explicit_source_file_never_starts_worker(self):
        with patch.object(provenance_nli, "validation_worker") as worker:
            result = provenance_nli.check_nli(
                self.root, self.value, model_path=self.model_path
            )
        self.assertEqual(result["status"], "UNVERIFIED")
        worker.assert_not_called()

    def test_missing_or_empty_source_file_never_starts_worker(self):
        empty = self.root / "empty-source.txt"
        empty.write_text(" \n", encoding="utf-8")
        for source_file in (self.root / "missing-source.txt", empty):
            with self.subTest(source_file=source_file):
                with patch.object(provenance_nli, "validation_worker") as worker:
                    result = provenance_nli.check_nli(
                        self.root, self.value, source_file,
                        model_path=self.model_path,
                    )
                self.assertEqual(result["status"], "UNVERIFIED")
                worker.assert_not_called()

    def test_bridge_forwards_whole_original_source_and_answer_without_retrieval(self):
        source = "Erste Quellenzeile: Berlin.\n\nZweite Quellenzeile: 18 Grad.\nLetzter Beleg: Öäü.\n"
        value = "Die Quelle nennt Berlin.\nDie Messung beträgt 18 Grad."
        self.source_file.write_bytes(source.encode("utf-8"))
        worker_result = {"status": "FAIL", "label": "contradiction", "confidence": 0.92}
        with patch.object(
            provenance_nli, "validation_worker", return_value=worker_result
        ) as worker:
            result = provenance_nli.check_nli(
                self.root, value, self.source_file, model_path=self.model_path
            )
        worker.assert_called_once()
        worker_root, request = worker.call_args.args
        self.assertEqual(Path(worker_root).resolve(), self.root)
        self.assertEqual(request["value"], value)
        self.assertEqual(request["sources"], [source])
        self.assertEqual(Path(request["source_file"]).resolve(), self.source_file)
        self.assertEqual(Path(request["model_path"]).resolve(), self.model_path)
        self.assertEqual(request["max_tokens"], 512)
        self.assertIs(request["truncation"], False)
        self.assertEqual(result["status"], "FAIL")

    def test_worker_failure_is_bounded_and_cannot_release_a_pass(self):
        with patch.object(
            provenance_nli, "validation_worker", side_effect=TimeoutError("worker deadline")
        ) as worker:
            result = provenance_nli.check_nli(
                self.root, self.value, self.source_file, model_path=self.model_path
            )
        worker.assert_called_once()
        self.assertIn(result["status"], ("ERROR", "UNVERIFIED"))

    def test_worker_environment_excludes_all_unreviewed_credentials(self):
        with patch.dict(os.environ, {'SystemRoot': r'C:\Windows', 'PATH': 'system-path',
                'UNREVIEWED_SECRET': 'fixture-only', 'AZURE_OPENAI_API_KEY': 'fixture-only',
                'PYTHONPATH': 'foreign-packages', 'HTTPS_PROXY': 'https://fixture.invalid'}, clear=True):
            environment = provenance_nli._offline_environment()
        self.assertFalse(any(key in environment for key in (
            'UNREVIEWED_SECRET', 'AZURE_OPENAI_API_KEY', 'PYTHONPATH', 'HTTPS_PROXY')),
            'The NLI worker inherited unreviewed environment data.')

    def test_private_worker_keeps_existing_punkt_and_project_torch_cache_after_rescrub(self):
        appdata = self.root / 'existing-appdata'
        nltk_data = appdata / 'nltk_data'
        (nltk_data / 'tokenizers/punkt').mkdir(parents=True)
        with patch.dict(os.environ, {'APPDATA': str(appdata)}, clear=True):
            environment = provenance_nli._offline_environment(self.root)
        self.assertEqual(str(nltk_data.resolve()), environment.get('NLTK_DATA'))
        self.assertEqual('true', environment.get('GUARDRAILS_RUN_SYNC'))
        cache = Path(environment['TORCHINDUCTOR_CACHE_DIR']).resolve()
        self.assertTrue(cache.is_relative_to(self.root / 'work/evals-runtime'))
        with patch.dict(os.environ, environment, clear=True):
            second = provenance_nli._offline_environment(self.root)
        self.assertEqual(environment['NLTK_DATA'], second.get('NLTK_DATA'))
        self.assertEqual(environment['TORCHINDUCTOR_CACHE_DIR'], second.get('TORCHINDUCTOR_CACHE_DIR'))

    def test_missing_local_punkt_never_launches_the_native_worker(self):
        model = self.root / 'work/evals-runtime/model'
        model.mkdir(parents=True)
        runtime = self.root / 'work/evals-runtime/.venv/Scripts/python.exe'
        runtime.parent.mkdir(parents=True)
        runtime.write_bytes(b'fixture-path-only')
        (self.root / 'nli-worker.py').write_bytes(b'fixture-path-only')
        request = dict(value=self.value, sources=[self.source], model_path=str(model), truncation=False)
        with patch.object(provenance_nli, '_offline_environment', return_value={}):
            with patch.object(provenance_nli.subprocess, 'run') as worker:
                result = provenance_nli.validation_worker(self.root, request)
        self.assertEqual('UNVERIFIED', result['status'])
        worker.assert_not_called()

    def test_nli_contradiction_participates_once_in_existing_orchestrator(self):
        from guardrails_local.orchestrator import Orchestrator
        from guardrails_local.domain import import_text
        (self.root / 'config').mkdir()
        for filename in ('requirements.json', 'catalog.json'):
            (self.root / 'config' / filename).write_bytes((ROOT / 'config' / filename).read_bytes())
        draft = import_text(self.value, source='fixture')
        with patch.object(provenance_nli, 'check_nli', return_value={
                'status': 'FAIL', 'label': 'contradiction', 'confidence': .99}) as checker:
            report = Orchestrator(self.root, nli_source_file=self.source_file).run(draft)
        self.assertEqual('FAIL', report['final_status'])
        self.assertEqual('FAIL', report['attempts'][0]['provenance_nli']['status'])
        checker.assert_called_once_with(self.root, self.value, self.source_file)


if __name__ == "__main__":
    unittest.main()
