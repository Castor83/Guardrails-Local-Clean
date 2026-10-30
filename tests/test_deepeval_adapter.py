"""Offline contracts for the bounded DeepEval bridge; never load a model."""

import asyncio
import json
import os
import shutil
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import types
import unittest
from unittest.mock import patch

from pydantic import BaseModel

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))
from test_critic import DIGEST, MODEL, envelope, fake_ollama, settings

try:
    from guardrails_local import deepeval_adapter as adapter
except ImportError:
    adapter = None


SCHEMA = {
    "type": "object", "additionalProperties": False,
    "properties": {"score": {"type": "number"}, "reason": {"type": "string"}},
    "required": ["score", "reason"],
}
ANSWER = {"score": 1, "reason": "Die Antwort folgt der Anweisung."}


class _ReasonScore(BaseModel):
    score: float
    reason: str


class _BaseLLMWithDeepEval431Fallback:
    """Only the upstream schema fallback that the adapter must override."""

    def __init__(self, model=None):
        self.name = model
        self.model = self.load_model()

    def generate_with_schema(self, prompt, schema=None, **kwargs):
        if schema is not None:
            try:
                return self.generate(prompt, schema=schema, **kwargs)
            except TypeError:
                pass
        return self.generate(prompt, **kwargs)

    async def a_generate_with_schema(self, prompt, schema=None, **kwargs):
        if schema is not None:
            try:
                return await self.a_generate(prompt, schema=schema, **kwargs)
            except TypeError:
                pass
        return await self.a_generate(prompt, **kwargs)


def fake_deepeval_modules():
    package = types.ModuleType("deepeval")
    package.__path__ = []
    models = types.ModuleType("deepeval.models")
    models.DeepEvalBaseLLM = _BaseLLMWithDeepEval431Fallback
    package.models = models
    return {"deepeval": package, "deepeval.models": models}


class DeepEvalBridgeTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(adapter, "The bounded DeepEval adapter is not implemented.")

    def bridge(self, url, **kwargs):
        return adapter.BoundedOllamaBridge(settings(url), **kwargs)

    def test_complete_prompt_and_schema_cross_the_fixed_native_boundary(self):
        prompt = "Auftrag: ausschließlich Deutsch.\n" + "x" * 7000 + "\nENDE DES ENTWURFS"
        with fake_ollama({"/api/chat": envelope(ANSWER)}) as (url, calls):
            bridge = self.bridge(url)
            output = bridge.generate(prompt, schema=SCHEMA)
        self.assertEqual(ANSWER, json.loads(output))
        self.assertEqual(["/api/tags", "/api/ps", "/api/chat"], [c["path"] for c in calls])
        request = calls[-1]["body"]
        self.assertEqual(MODEL, request["model"])
        self.assertIs(False, request["stream"])
        self.assertEqual("low", request["think"])
        self.assertEqual(0, request["keep_alive"])
        self.assertEqual({"num_ctx": 4096, "num_predict": 1200, "temperature": 0}, request["options"])
        self.assertEqual(SCHEMA, request["format"])
        self.assertEqual(prompt, request["messages"][-1]["content"])
        self.assertLessEqual(sum(len(m["content"].encode("utf-8")) for m in request["messages"]), 8500)
        self.assertNotIn("PRIVATE_REASONING", output)
        self.assertEqual(1, bridge.calls_attempted)

    def test_oversize_utf8_is_rejected_before_preflight_and_never_shortened(self):
        with fake_ollama() as (url, calls):
            bridge = self.bridge(url)
            with self.assertRaises(adapter.DeepEvalError):
                bridge.generate("ä" * 4251, schema=SCHEMA)
            self.assertEqual([], calls)
            self.assertEqual(0, bridge.calls_attempted)

    def test_one_bridge_enforces_one_global_four_call_budget(self):
        with fake_ollama({"/api/chat": envelope(ANSWER)}) as (url, calls):
            bridge = self.bridge(url)
            for index in range(4):
                self.assertEqual(ANSWER, json.loads(bridge.generate(f"Fall {index}", schema=SCHEMA)))
            with self.assertRaises(adapter.DeepEvalError):
                bridge.generate("Kein fünfter Aufruf", schema=SCHEMA)
        self.assertEqual(4, bridge.calls_attempted)
        self.assertEqual(4, sum(c["path"] == "/api/chat" for c in calls))

    def test_budget_cannot_be_widened_above_four(self):
        for value in (0, -1, 5, True, 4.0):
            with self.subTest(value=value), self.assertRaises(adapter.DeepEvalError):
                self.bridge("http://127.0.0.1:11434", max_calls=value)

    def test_http_failure_consumes_budget_and_is_not_retried(self):
        with fake_ollama({"/api/chat": (503, {}, {"error": "unavailable"}, 0)}) as (url, calls):
            bridge = self.bridge(url, max_calls=1)
            with self.assertRaises(adapter.DeepEvalError):
                bridge.generate("Prüfen", schema=SCHEMA)
            with self.assertRaises(adapter.DeepEvalError):
                bridge.generate("Nach Fehler nicht erneut senden", schema=SCHEMA)
        self.assertEqual(1, sum(c["path"] == "/api/chat" for c in calls))
        self.assertEqual(1, bridge.calls_attempted)

    def test_digest_mismatch_blocks_before_generation(self):
        routes = {"/api/tags": {"models": [{"name": MODEL, "model": MODEL, "digest": "changed"}]}}
        with fake_ollama(routes) as (url, calls):
            with self.assertRaises(adapter.DeepEvalError):
                self.bridge(url).generate("Prüfen", schema=SCHEMA)
        self.assertEqual(["/api/tags"], [c["path"] for c in calls])

    def test_foreign_loaded_model_blocks_without_unloading(self):
        routes = {"/api/ps": {"models": [{"name": "foreign:model", "digest": "foreign"}]}}
        with fake_ollama(routes) as (url, calls):
            with self.assertRaises(adapter.DeepEvalError):
                self.bridge(url).generate("Prüfen", schema=SCHEMA)
        self.assertEqual(["/api/tags", "/api/ps"], [c["path"] for c in calls])

    def test_changed_runtime_state_is_checked_before_each_generation(self):
        reads = [0]

        def running():
            reads[0] += 1
            return {"models": [] if reads[0] == 1 else [{"name": "foreign:model", "digest": "foreign"}]}

        with fake_ollama({"/api/ps": running, "/api/chat": envelope(ANSWER)}) as (url, calls):
            bridge = self.bridge(url)
            bridge.generate("Erster Fall", schema=SCHEMA)
            with self.assertRaises(adapter.DeepEvalError):
                bridge.generate("Zweiter Fall", schema=SCHEMA)
        self.assertEqual(1, sum(c["path"] == "/api/chat" for c in calls))
        self.assertEqual(2, sum(c["path"] == "/api/ps" for c in calls))

    def test_truncation_wrong_model_and_incomplete_protocol_never_become_scores(self):
        for changes in ({"done_reason": "length"}, {"done": False}, {"model": "foreign:model"},
                        {"message": {"role": "user", "content": json.dumps(ANSWER)}}):
            with self.subTest(changes=changes), fake_ollama({"/api/chat": envelope(ANSWER, **changes)}) as (url, calls):
                with self.assertRaises(adapter.DeepEvalError):
                    self.bridge(url).generate("Prüfen", schema=SCHEMA)
                self.assertEqual(1, sum(c["path"] == "/api/chat" for c in calls))

    def test_duplicate_nonfinite_or_embedded_json_is_rejected_without_repair(self):
        for content in ('{"score":0,"score":1,"reason":"x"}', '{"score":NaN,"reason":"x"}',
                        '{"score":1e999,"reason":"x"}',
                        '```json\n{"score":1,"reason":"x"}\n```', "not json"):
            reply = envelope(ANSWER)
            reply["message"]["content"] = content
            with self.subTest(content=content), fake_ollama({"/api/chat": reply}) as (url, calls):
                with self.assertRaises(adapter.DeepEvalError):
                    self.bridge(url).generate("Prüfen", schema=SCHEMA)
                self.assertEqual(1, sum(c["path"] == "/api/chat" for c in calls))

    def test_remote_destination_and_model_switch_are_rejected_at_construction(self):
        for change in ({"base_url": "https://remote.example"}, {"model": "another:model"},
                       {"expected_digest": "another-digest"}, {"num_ctx": 8192}, {"num_predict": 1201}):
            with self.subTest(change=change), self.assertRaises(adapter.DeepEvalError):
                adapter.BoundedOllamaBridge({**settings("http://127.0.0.1:11434"), **change})

    def test_importing_controller_needs_no_deepeval_package(self):
        command = [sys.executable, "-c", "import sys; sys.modules['deepeval']=None; "
                   "sys.path.insert(0,sys.argv[1]); import guardrails_local.deepeval_adapter; "
                   "assert not any(k.startswith('deepeval.') for k in sys.modules)", str(ROOT / "src")]
        result = subprocess.run(command, capture_output=True, text=True, timeout=10)
        self.assertEqual(0, result.returncode, result.stderr)

    def test_factory_returns_schema_instance_and_async_uses_same_bridge(self):
        with fake_ollama({"/api/chat": envelope(ANSWER)}) as (url, calls), patch.dict(sys.modules, fake_deepeval_modules()):
            bridge = self.bridge(url)
            model = adapter.make_deepeval_model(bridge)
            result = model.generate("Synchron", schema=_ReasonScore)
            async_result = asyncio.run(model.a_generate("Asynchron", schema=_ReasonScore))
            plain = model.generate("Rohtext")
        self.assertIsInstance(result, _ReasonScore)
        self.assertEqual(1, result.score)
        self.assertIsInstance(async_result, _ReasonScore)
        self.assertEqual(ANSWER, json.loads(plain))
        self.assertEqual(3, bridge.calls_attempted)
        self.assertEqual(3, sum(c["path"] == "/api/chat" for c in calls))
        self.assertEqual(MODEL, model.get_model_name())

    def test_schema_typeerror_does_not_trigger_deepeval_raw_text_fallback(self):
        class FailedBridge:
            calls_attempted = 0

            def generate(self, *args, **kwargs):
                self.calls_attempted += 1
                raise TypeError("Schema transport failed after entering generate")

        for asynchronous in (False, True):
            with self.subTest(asynchronous=asynchronous), patch.dict(sys.modules, fake_deepeval_modules()):
                bridge = FailedBridge()
                model = adapter.make_deepeval_model(bridge)
                with self.assertRaises(Exception):
                    if asynchronous:
                        asyncio.run(model.a_generate_with_schema("Prüfen", schema=_ReasonScore))
                    else:
                        model.generate_with_schema("Prüfen", schema=_ReasonScore)
                self.assertEqual(1, bridge.calls_attempted)


class DeepEvalWorkerTests(unittest.TestCase):
    def test_fresh_checkout_has_all_synthetic_smoke_cases(self):
        for name in ('deepeval-smoke.json', 'nli-smoke.json'):
            self.assertTrue((ROOT / 'examples/evals' / name).is_file(), name)
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            shutil.copytree(ROOT / 'examples/evals', root / 'examples/evals')
            self.assertEqual(4, len(adapter._smoke_cases(root)))
            self.assertFalse((root / 'work').exists())

    def test_expected_verdict_is_pinned_to_case_id(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = ROOT / 'examples/evals/deepeval-smoke.json'
            if not source.exists():
                source = ROOT / 'work/deepeval-preparation/smoke-cases.draft.json'
            document = dict(schema_version=1, cases=json.loads(source.read_text(encoding='utf-8'))['cases'])
            document['cases'][-1].update(expected_verdict='PASS', actual_output='Berlin ist die Hauptstadt Deutschlands.')
            path = root / 'examples/evals/deepeval-smoke.json'
            path.parent.mkdir(parents=True)
            path.write_text(json.dumps(document), encoding='utf-8')
            runtime = root / 'work/evals-runtime/.venv/Scripts/python.exe'
            runtime.parent.mkdir(parents=True)
            runtime.touch()
            (root / 'deepeval-worker.py').touch()
            with patch.object(adapter, 'run_worker', return_value=dict(status='PASS')) as worker:
                report = adapter.run_deepeval_smoke(root)
            self.assertEqual('ERROR', report['status'])
            worker.assert_not_called()

    def test_modified_case_content_is_rejected_before_measurement(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = ROOT / 'examples/evals/deepeval-smoke.json'
            if not source.exists():
                source = ROOT / 'work/deepeval-preparation/smoke-cases.draft.json'
            document = dict(schema_version=1, cases=json.loads(source.read_text(encoding='utf-8'))['cases'])
            document['cases'][-1]['source_context'] = ['Bonn ist die Hauptstadt Deutschlands.']
            (root / 'config').mkdir()
            shutil.copyfile(ROOT / 'config/settings.json', root / 'config/settings.json')
            path = root / 'examples/evals/deepeval-smoke.json'
            path.parent.mkdir(parents=True)
            path.write_text(json.dumps(document), encoding='utf-8')
            with patch.dict(os.environ), patch.object(adapter, 'BoundedOllamaBridge',
                    side_effect=AssertionError('Invalid cases must stop before bridge creation')) as bridge:
                report = adapter._smoke_worker(root)
            bridge.assert_not_called()
            self.assertEqual('ERROR', report['status'])
            self.assertIn('Prüffall', report['error'])

    def setUp(self):
        self.assertIsNotNone(adapter, "The bounded DeepEval adapter is not implemented.")

    def test_smoke_worker_keeps_project_profile_before_optional_imports(self):
        captured = {}

        def inspect_environment(_settings):
            captured.update(os.environ)
            raise adapter.DeepEvalError("Stop before imports or network")

        with patch.dict(os.environ, {"HOME": "foreign-home", "USERPROFILE": "foreign-profile",
                                     "APPDATA": "foreign-config", "LOCALAPPDATA": "foreign-cache"}), \
                patch.object(adapter, "BoundedOllamaBridge", side_effect=inspect_environment):
            result = adapter._smoke_worker(ROOT)
        home = ROOT / "work/evals-runtime/home"
        self.assertEqual("ERROR", result["status"])
        self.assertEqual(0, result["calls_attempted"])
        self.assertEqual(str(home), captured.get("HOME"))
        self.assertEqual(str(home), captured.get("USERPROFILE"))
        self.assertEqual(str(home / "AppData/Roaming"), captured.get("APPDATA"))
        self.assertEqual(str(home / "AppData/Local"), captured.get("LOCALAPPDATA"))

    def test_worker_socket_guard_blocks_external_dns_before_resolution(self):
        code = ("import sys,socket,json; sys.path.insert(0,sys.argv[1]); "
                "from guardrails_local.deepeval_adapter import _install_network_guard,DeepEvalError; "
                "events=[]; _install_network_guard('http://127.0.0.1:11434',events); "
                "local=bool(socket.getaddrinfo('127.0.0.1',11434)); blocked=False\n"
                "try: socket.getaddrinfo('example.invalid',443)\n"
                "except DeepEvalError: blocked=True\n"
                "print(json.dumps({'local':local,'blocked':blocked,'events':len(events)}))")
        result = adapter.run_worker([sys.executable, '-I', '-c', code, str(ROOT / 'src')],
                                    cwd=ROOT, timeout_seconds=10)
        self.assertEqual({'local': True, 'blocked': True, 'events': 1}, result)

    def test_child_environment_cannot_inherit_cloud_credentials_or_python_path(self):
        parent = {"SystemRoot": os.environ.get("SystemRoot", r"C:\Windows"),
                  "PATH": "allowed-os-path", "TEMP": tempfile.gettempdir(),
                  "CONFIDENT_API_KEY": "private-confident", "OPENAI_API_KEY": "private-openai",
                  "TYPESAFE_API_KEY": "private-typesafe", "AWS_SECRET_ACCESS_KEY": "private-aws",
                  "AZURE_OPENAI_API_KEY": "private-azure", "PYTHONPATH": "foreign-packages",
                  "HTTP_PROXY": "http://external.invalid", "HTTPS_PROXY": "http://external.invalid",
                  "DEEPEVAL_TELEMETRY_OPT_OUT": "0", "CONFIDENT_TRACING_ENABLED": "YES",
                  "DEEPEVAL_EVAL_MODE": "system_one", "UNREVIEWED_SECRET": "private-other"}
        result = adapter.build_worker_environment(parent)
        for key in ("CONFIDENT_API_KEY", "OPENAI_API_KEY", "TYPESAFE_API_KEY", "AWS_SECRET_ACCESS_KEY",
                    "AZURE_OPENAI_API_KEY", "PYTHONPATH", "HTTP_PROXY", "HTTPS_PROXY", "UNREVIEWED_SECRET"):
            self.assertNotIn(key, result)
        self.assertEqual("1", result["DEEPEVAL_TELEMETRY_OPT_OUT"])
        self.assertEqual("1", result["DEEPEVAL_DISABLE_DOTENV"])
        self.assertEqual("1", result["DEEPEVAL_DISABLE_LEGACY_KEYFILE"])
        self.assertEqual("NO", result["CONFIDENT_TRACING_ENABLED"])
        self.assertEqual("0", result["CONFIDENT_TRACE_INTERNAL"])
        self.assertEqual("0", result["DEEPEVAL_UPDATE_WARNING_OPT_IN"])
        self.assertEqual("1", result["DEEPEVAL_RETRY_MAX_ATTEMPTS"])
        self.assertEqual("llm", result["DEEPEVAL_EVAL_MODE"])
        self.assertEqual("allowed-os-path", result["PATH"])
        self.assertEqual("private-confident", parent["CONFIDENT_API_KEY"])

    def test_worker_actually_receives_only_local_configuration(self):
        code = ("import os,json; print(json.dumps({'cloud':os.getenv('CONFIDENT_API_KEY'),"
                "'telemetry':os.getenv('DEEPEVAL_TELEMETRY_OPT_OUT'),"
                "'tracing':os.getenv('CONFIDENT_TRACING_ENABLED')}))")
        with patch.dict(os.environ, {"CONFIDENT_API_KEY": "MUST_NOT_CROSS_BOUNDARY"}):
            report = adapter.run_worker([sys.executable, "-c", code], cwd=ROOT, timeout_seconds=5)
        self.assertEqual({"cloud": None, "telemetry": "1", "tracing": "NO"}, report)

    def test_parent_kills_only_its_worker_at_the_total_deadline_without_retry(self):
        with tempfile.TemporaryDirectory() as directory:
            marker = Path(directory) / "worker-starts.txt"
            code = ("from pathlib import Path; import sys,time; p=Path(sys.argv[1]); "
                    "p.write_text(p.read_text()+'start\\n' if p.exists() else 'start\\n'); time.sleep(20)")
            started = time.monotonic()
            with self.assertRaises(adapter.DeepEvalError):
                adapter.run_worker([sys.executable, "-c", code, str(marker)], cwd=ROOT, timeout_seconds=0.5)
            self.assertLess(time.monotonic() - started, 6)
            self.assertEqual("start\n", marker.read_text())

    def test_worker_nonzero_or_invalid_json_is_an_error(self):
        for code in ("raise SystemExit(3)", "print('invalid JSON')", "print('[]')"):
            with self.subTest(code=code), self.assertRaises(adapter.DeepEvalError):
                adapter.run_worker([sys.executable, "-c", code], cwd=ROOT, timeout_seconds=5)

    def test_worker_deadline_cannot_exceed_180_seconds(self):
        for timeout in (181, 0, -1, True, float("inf"), float("nan")):
            with self.subTest(timeout=timeout), self.assertRaises(adapter.DeepEvalError):
                adapter.run_worker([sys.executable, "-c", "print('{}')"], cwd=ROOT, timeout_seconds=timeout)


if __name__ == "__main__":
    unittest.main()
