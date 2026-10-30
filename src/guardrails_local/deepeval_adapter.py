"""Opt-in DeepEval integration, isolated from the live answer hook.

Importing this controller needs only the standard library. DeepEval and
Pydantic are imported only inside the dedicated evaluation worker. The
Python socket audit guard is process-local enforcement, not an OS sandbox.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import threading
from typing import Any
from urllib.parse import urlsplit

from .critic import CriticError, EXPECTED_DIGEST, MAX_INPUT_BYTES, MODEL, OllamaCritic, _json_loads


MAX_CALLS = 4
WORKER_TIMEOUT_SECONDS = 180
MAX_WORKER_OUTPUT_BYTES = 262144


class DeepEvalError(CriticError):
    """A bounded evaluation failed; never infer approval or retry from this."""


def _finite_json(value: Any) -> Any:
    if isinstance(value, float) and not math.isfinite(value):
        raise DeepEvalError("DeepEval-Antwort enthält eine nicht endliche Zahl.")
    if isinstance(value, dict):
        for item in value.values():
            _finite_json(item)
    elif isinstance(value, list):
        for item in value:
            _finite_json(item)
    return value


def _strict_json(text: str, label: str) -> Any:
    try:
        return _finite_json(_json_loads(text, label))
    except DeepEvalError:
        raise
    except (CriticError, TypeError, ValueError, RecursionError) as exc:
        raise DeepEvalError(f"{label}: ungültiges, mehrdeutiges oder nicht endliches JSON.") from exc


class BoundedOllamaBridge:
    """A shared, serial, at-most-four-call ledger over the pinned transport."""

    def __init__(self, settings: dict, *, max_calls: int = MAX_CALLS):
        if type(max_calls) is not int or not 1 <= max_calls <= MAX_CALLS:
            raise DeepEvalError("DeepEval erlaubt ein gemeinsames Budget von höchstens vier Aufrufen.")
        try:
            self.transport = OllamaCritic(settings)
        except (CriticError, TypeError, ValueError) as exc:
            raise DeepEvalError("Unzulässige lokale DeepEval-Transportkonfiguration: " + str(exc)) from exc
        self.max_calls = max_calls
        self.calls_attempted = 0
        self.audit: list[dict] = []
        self._lock = threading.Lock()

    def generate(self, prompt: str, schema: dict | None = None) -> str:
        if not isinstance(prompt, str) or not prompt.strip():
            raise DeepEvalError("DeepEval benötigt einen vollständigen nichtleeren Prüf-Prompt.")
        if schema is not None and not isinstance(schema, dict):
            raise DeepEvalError("DeepEval-Schema muss ein JSON-Objekt sein.")
        try:
            prompt_bytes = len(prompt.encode("utf-8", errors="strict"))
            json.dumps(schema, allow_nan=False)
        except (TypeError, ValueError, UnicodeError, RecursionError) as exc:
            raise DeepEvalError("DeepEval-Prompt oder Schema ist ungültig.") from exc
        # This is the complete rendered DeepEval prompt, not a shortened draft.
        # A byte approximation does not prove an exact 4096-token context fit.
        if prompt_bytes > MAX_INPUT_BYTES:
            raise DeepEvalError("Vollständiger DeepEval-Prompt überschreitet 8500 UTF-8-Bytes; keine Kürzung.")
        with self._lock:
            if self.calls_attempted >= self.max_calls:
                raise DeepEvalError("Gemeinsames DeepEval-Aufrufbudget erschöpft; keine Wiederholung.")
            try:
                self.transport._preflight()
            except Exception as exc:
                raise DeepEvalError("DeepEval-Modellvorprüfung blockiert: " + str(exc)) from exc
            self.calls_attempted += 1
            event = dict(call=self.calls_attempted, status="ATTEMPTED", input_utf8_bytes=prompt_bytes,
                         prompt_sha256=hashlib.sha256(prompt.encode("utf-8")).hexdigest())
            self.audit.append(event)
            try:
                response = self.transport._request("/api/chat", {
                    "model": MODEL, "stream": False, "think": "low", "keep_alive": 0,
                    "options": {"num_ctx": 4096, "num_predict": self.transport.num_predict, "temperature": 0},
                    "format": schema if schema is not None else "json",
                    "messages": [{"role": "user", "content": prompt}],
                })
                if response.get("done") is not True or response.get("model") != MODEL:
                    raise DeepEvalError("DeepEval-Modellantwort ist unvollständig oder stammt vom falschen Modell.")
                if response.get("done_reason") == "length":
                    raise DeepEvalError("DeepEval-Ausgabe wurde am Tokenlimit abgeschnitten.")
                if "done_reason" in response and not isinstance(response["done_reason"], str):
                    raise DeepEvalError("DeepEval-Abschlussgrund ist ungültig.")
                message = response.get("message")
                if (not isinstance(message, dict) or message.get("role") != "assistant"
                        or not isinstance(message.get("content"), str)):
                    raise DeepEvalError("DeepEval erhielt keine gültige Assistant-Antwort.")
                content = message["content"]
                _strict_json(content, "DeepEval-Antwort")
                metrics = {}
                for key in ("total_duration", "load_duration", "prompt_eval_count", "prompt_eval_duration",
                            "eval_count", "eval_duration"):
                    if key in response:
                        if type(response[key]) is not int or response[key] < 0:
                            raise DeepEvalError("DeepEval-Antwort enthält ungültige Leistungsmetadaten.")
                        metrics[key] = response[key]
                event.update(status="COMPLETED", metrics=metrics)
                return content
            except Exception as exc:
                event["status"] = "ERROR"
                if isinstance(exc, DeepEvalError):
                    raise
                raise DeepEvalError("Lokaler DeepEval-Aufruf fehlgeschlagen; kein Wiederholungsversuch.") from exc


def make_deepeval_model(bridge):
    """Construct a schema-aware custom model after the worker privacy setup."""
    from deepeval.models import DeepEvalBaseLLM
    from pydantic import BaseModel

    class LocalDeepEvalModel(DeepEvalBaseLLM):
        def __init__(self):
            super().__init__(model=MODEL)

        def load_model(self):
            # This only binds the existing HTTP client; no model is loaded here.
            return bridge

        def get_model_name(self):
            return MODEL

        def generate(self, prompt: str, schema=None):
            try:
                if schema is not None and (not isinstance(schema, type) or not issubclass(schema, BaseModel)):
                    raise DeepEvalError("DeepEval übergab keine Pydantic-Schemaklasse.")
                result = bridge.generate(prompt, schema=None if schema is None else schema.model_json_schema())
                if schema is None:
                    return result
                parsed = _strict_json(result, "DeepEval-Schemaantwort")
                validated = schema.model_validate(parsed, strict=True)
                if schema.__name__ == "ReasonScore" and schema.__module__.startswith("deepeval.metrics.g_eval"):
                    # GEval strict_mode casts the score to int. Reject a fractional
                    # upstream score before that cast could silently change it.
                    if (type(validated.score) not in (int, float) or not math.isfinite(validated.score)
                            or validated.score not in {0, 1}):
                        raise DeepEvalError("G-Eval lieferte keinen unveränderten binären Rohwert.")
                    if not validated.reason.strip() or len(validated.reason) > 2000:
                        raise DeepEvalError("G-Eval lieferte keine gültige begrenzte Rohbegründung.")
                return validated
            except DeepEvalError:
                raise
            except Exception as exc:
                # Upstream catches TypeError and can call generate a second time.
                raise DeepEvalError("DeepEval-Schema oder Modellaufruf fehlgeschlagen; keine Wiederholung.") from exc

        async def a_generate(self, prompt: str, schema=None):
            return self.generate(prompt, schema=schema)

        def generate_with_schema(self, prompt: str, schema=None, **kwargs):
            if kwargs:
                raise DeepEvalError("Zusätzliche DeepEval-Generierungsoptionen sind nicht freigegeben.")
            return self.generate(prompt, schema=schema)

        async def a_generate_with_schema(self, prompt: str, schema=None, **kwargs):
            if kwargs:
                raise DeepEvalError("Zusätzliche DeepEval-Generierungsoptionen sind nicht freigegeben.")
            return await self.a_generate(prompt, schema=schema)

        def generate_raw_response(self, *args, **kwargs):
            # 4.3.1 GEval falls back on AttributeError, before any model call.
            raise AttributeError("Local bounded adapter does not expose log probabilities")

        async def a_generate_raw_response(self, *args, **kwargs):
            raise AttributeError("Local bounded adapter does not expose log probabilities")

        def supports_log_probs(self):
            return False

        def supports_structured_outputs(self):
            return True

        def supports_json_mode(self):
            return True

    return LocalDeepEvalModel()


def build_worker_environment(parent_env: dict) -> dict:
    """Copy OS essentials only, then pin local evaluation settings before import."""
    allowed = {"systemroot", "windir", "path", "temp", "tmp", "comspec", "pathext",
               "systemdrive", "number_of_processors", "processor_architecture"}
    environment = {key: value for key, value in parent_env.items()
                   if key.lower() in allowed and isinstance(value, str)}
    environment.update({
        "DEEPEVAL_TELEMETRY_OPT_OUT": "1", "DEEPEVAL_DISABLE_DOTENV": "1",
        "DEEPEVAL_DISABLE_LEGACY_KEYFILE": "1", "CONFIDENT_TRACING_ENABLED": "NO",
        "CONFIDENT_TRACE_INTERNAL": "0", "DEEPEVAL_UPDATE_WARNING_OPT_IN": "0",
        "DEEPEVAL_RETRY_MAX_ATTEMPTS": "1", "DEEPEVAL_EVAL_MODE": "llm",
        "DEEPEVAL_MODE": "stable", "DEEPEVAL_FILE_SYSTEM": "READ_ONLY",
        "CONFIDENT_OPEN_BROWSER": "0", "DEEPEVAL_NO_INSPECT_PROMPT": "1",
        "ENABLE_DEEPEVAL_CACHE": "0", "IGNORE_DEEPEVAL_ERRORS": "0",
        "SKIP_DEEPEVAL_MISSING_PARAMS": "0", "PYTHONNOUSERSITE": "1",
        "PYTHONIOENCODING": "utf-8", "HF_HUB_OFFLINE": "1", "TRANSFORMERS_OFFLINE": "1",
        "TOKENIZERS_PARALLELISM": "false",
        "HF_HUB_DISABLE_TELEMETRY": "1", "DO_NOT_TRACK": "1",
        "OTEL_SDK_DISABLED": "true", "LITELLM_LOCAL_MODEL_COST_MAP": "True",
    })
    return environment


def run_worker(command: list[str], *, cwd: Path, timeout_seconds=WORKER_TIMEOUT_SECONDS) -> dict:
    """Run an internally constructed command once; kill only this owned child."""
    if (type(timeout_seconds) not in (int, float) or not math.isfinite(timeout_seconds)
            or not 0 < timeout_seconds <= WORKER_TIMEOUT_SECONDS):
        raise DeepEvalError("DeepEval-Worker benötigt ein hartes Zeitlimit von höchstens 180 Sekunden.")
    if not isinstance(command, list) or not command or any(not isinstance(item, str) or not item for item in command):
        raise DeepEvalError("Ungültiger interner DeepEval-Worker-Aufruf.")
    environment = build_worker_environment(os.environ)
    home = Path(cwd).resolve() / 'work/evals-runtime/home'
    for key, path in {'HOME': home, 'USERPROFILE': home,
                      'APPDATA': home / 'AppData/Roaming', 'LOCALAPPDATA': home / 'AppData/Local'}.items():
        path.mkdir(parents=True, exist_ok=True)
        environment[key] = str(path)
    options = dict(cwd=Path(cwd), env=environment, stdin=subprocess.DEVNULL,
                   stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, shell=False)
    if os.name == "nt":
        options["creationflags"] = subprocess.CREATE_NO_WINDOW
    process = None
    try:
        process = subprocess.Popen(command, **options)
        try:
            output, _ = process.communicate(timeout=timeout_seconds)
        except subprocess.TimeoutExpired as exc:
            process.kill()
            process.communicate(timeout=5)
            raise DeepEvalError("DeepEval-Worker am harten Gesamtzeitlimit beendet; keine Wiederholung. "
                                "Der separate Ollama-Server wird nicht beendet.") from exc
        if process.returncode != 0:
            raise DeepEvalError("DeepEval-Worker fehlgeschlagen; keine automatische Wiederholung.")
        if len(output) > MAX_WORKER_OUTPUT_BYTES:
            raise DeepEvalError("DeepEval-Workerbericht überschreitet die zulässige Größe.")
        result = _strict_json(output.decode("utf-8", errors="strict"), "DeepEval-Workerbericht")
        if not isinstance(result, dict):
            raise DeepEvalError("DeepEval-Worker lieferte kein Berichtsobjekt.")
        return result
    except DeepEvalError:
        raise
    except (OSError, ValueError, UnicodeError, subprocess.SubprocessError) as exc:
        raise DeepEvalError("DeepEval-Worker oder sein Bericht ist technisch fehlgeschlagen.") from exc
    finally:
        if process is not None and process.poll() is None:
            process.kill()
            process.communicate(timeout=5)


def _install_network_guard(base_url: str, audit: list[dict]) -> None:
    """Fail closed for audited Python DNS/connect/sendto outside the pinned loopback."""
    parsed = urlsplit(base_url)
    expected_host, expected_port = parsed.hostname, parsed.port or 80
    if expected_host not in {"127.0.0.1", "::1"} or parsed.scheme != "http":
        raise DeepEvalError("Ungültiges Loopback-Ziel für die Python-Netzwerkprüfung.")

    def allowed(host, port):
        if isinstance(host, bytes):
            host = host.decode("ascii", errors="strict")
        return host == expected_host and str(port) == str(expected_port)

    def audit_hook(event, args):
        if event == "socket.getaddrinfo":
            host, port = args[:2]
            if not allowed(host, port):
                audit.append(dict(event=event, allowed=False))
                raise DeepEvalError("Externe oder nichtnumerische Python-DNS-Anfrage im DeepEval-Worker blockiert.")
        elif event in {"socket.gethostbyname", "socket.gethostbyname_ex"}:
            if args[0] != expected_host:
                audit.append(dict(event=event, allowed=False))
                raise DeepEvalError("Python-DNS-Auflösung im DeepEval-Worker blockiert.")
        elif event in {"socket.gethostbyaddr", "socket.getnameinfo"}:
            audit.append(dict(event=event, allowed=False))
            raise DeepEvalError("Python-Reverse-DNS im DeepEval-Worker blockiert.")
        elif event in {"socket.connect", "socket.sendto"}:
            address = args[1] if event == "socket.connect" else args[-1]
            accepted = isinstance(address, tuple) and len(address) >= 2 and allowed(address[0], address[1])
            audit.append(dict(event=event, allowed=accepted))
            if not accepted:
                raise DeepEvalError("Python-Netzwerkaufruf außerhalb des festgelegten Ollama-Loopbacks blockiert.")

    sys.addaudithook(audit_hook)


def _error_report(message: str, *, calls_attempted=0, cases=None, audit=None, network_audit=None) -> dict:
    return dict(status="ERROR", framework="deepeval", version="4.3.1", error=message,
                model=MODEL, model_digest=EXPECTED_DIGEST, max_calls=MAX_CALLS,
                calls_attempted=calls_attempted, cases=cases or [], audit=audit or [],
                network_audit=network_audit or [], verified=False,
                scope="Vier synthetische Integrationsfälle; keine allgemeine Judge- oder Qualitätsabnahme.")


def _smoke_cases(root: Path) -> list:
    path = Path(root) / 'examples/evals/deepeval-smoke.json'
    try:
        if not path.is_file() or path.stat().st_size > 65536:
            raise DeepEvalError('Versionierte DeepEval-Prüffalldatei fehlt oder ist zu groß.')
        document = _strict_json(path.read_text(encoding='utf-8'), 'DeepEval-Prüffälle')
        canonical = json.dumps(document, ensure_ascii=False, sort_keys=True,
                               separators=(',', ':'), allow_nan=False).encode('utf-8')
        if hashlib.sha256(canonical).hexdigest() != 'd528a636de4263a22a98a5cffb58b7e0194785f05bad6f7e049352ee40b87d52':
            raise DeepEvalError('DeepEval-Prüffallinhalt, Schema oder feste Sollurteile wurden verändert.')
        return document['cases']
    except (OSError, ValueError, TypeError, KeyError) as exc:
        raise DeepEvalError('DeepEval-Prüffallprüfung fehlgeschlagen: ' + str(exc)) from exc


def _smoke_worker(root: Path) -> dict:
    environment = build_worker_environment(os.environ)
    home = root.resolve() / 'work/evals-runtime/home'
    for key, path in {'HOME': home, 'USERPROFILE': home,
                      'APPDATA': home / 'AppData/Roaming', 'LOCALAPPDATA': home / 'AppData/Local'}.items():
        path.mkdir(parents=True, exist_ok=True)
        environment[key] = str(path)
    os.environ.clear()
    os.environ.update(environment)
    bridge = None
    results, network_audit = [], []
    try:
        cases = _smoke_cases(root)
        configuration = _strict_json((root / "config/settings.json").read_text(encoding="utf-8"), "Critic-Konfiguration")
        bridge = BoundedOllamaBridge(configuration)
        _install_network_guard(bridge.transport.base_url, network_audit)
        # This is intentionally after environment scrubbing and network admission.
        from importlib.metadata import version
        if version("deepeval") != "4.3.1":
            raise DeepEvalError("Nur die geprüfte DeepEval-Version 4.3.1 ist freigegeben.")
        from deepeval.config.settings import get_settings
        from deepeval.confident.api import is_confident
        from deepeval.metrics import GEval, PromptAlignmentMetric
        from deepeval.test_case import LLMTestCase, SingleTurnParams
        if is_confident() or not get_settings().DEEPEVAL_TELEMETRY_OPT_OUT:
            raise DeepEvalError("DeepEval-Privatsphäreeinstellungen wurden nicht wirksam.")
        judge = make_deepeval_model(bridge)
        for case in cases:
            if (any(not isinstance(case.get(key), str) or not case[key].strip()
                    for key in ("input", "actual_output", "criterion"))
                    or case.get("expected_verdict") not in {"PASS", "FAIL"}):
                raise DeepEvalError("Vorbereiteter DeepEval-Fall ist unvollständig.")
            context = case.get("source_context")
            if context is not None and (not isinstance(context, list) or not context
                                        or any(not isinstance(item, str) or not item.strip() for item in context)):
                raise DeepEvalError("DeepEval-Quellenkontext ist ungültig.")
            test_case = LLMTestCase(input=case["input"], actual_output=case["actual_output"], retrieval_context=context)
            if case["id"].startswith("instruction_"):
                metric = PromptAlignmentMetric(prompt_instructions=[case["criterion"]], model=judge, eval_mode="llm",
                                               include_reason=False, async_mode=False, strict_mode=True)
            else:
                metric = GEval(name="Quellendeckung", model=judge, async_mode=False, strict_mode=True,
                               evaluation_params=[SingleTurnParams.INPUT, SingleTurnParams.ACTUAL_OUTPUT,
                                                  SingleTurnParams.RETRIEVAL_CONTEXT],
                               evaluation_steps=[
                                   "Prüfe jede Tatsachenbehauptung in actual_output ausschließlich gegen retrieval_context zur Frage input.",
                                   "Jede Behauptung muss durch retrieval_context gedeckt sein. Ein Widerspruch oder eine unbelegte Behauptung ergibt 0; vollständige Deckung ergibt 1. Nutze kein externes Wissen.",
                               ])
            before = bridge.calls_attempted
            metric.measure(test_case, _show_indicator=False)
            if any(event.get("allowed") is False for event in network_audit):
                raise DeepEvalError("Mindestens ein nicht freigegebener Python-Netzwerkversuch wurde blockiert.")
            if bridge.calls_attempted != before + 1:
                raise DeepEvalError("DeepEval hat nicht genau einen Modellaufruf für diesen Prüffall verwendet.")
            score = metric.score
            if type(score) not in (int, float) or not math.isfinite(score) or score not in {0, 1}:
                raise DeepEvalError("DeepEval meldete keinen endlichen binären Prüfwert.")
            if case["id"].startswith("instruction_"):
                if len(metric.verdicts) != 1:
                    raise DeepEvalError("DeepEval meldete nicht genau ein Anweisungsurteil.")
                reasons = [verdict.reason for verdict in metric.verdicts if verdict.reason is not None]
                if any(not isinstance(reason, str) or not reason.strip() or len(reason) > 2000 for reason in reasons):
                    raise DeepEvalError("DeepEval meldete eine ungültige Anweisungsbegründung.")
                reason = reasons[0] if reasons else None
            else:
                reason = metric.reason
                if not isinstance(reason, str) or not reason.strip() or len(reason) > 2000:
                    raise DeepEvalError("DeepEval meldete keine gültige begrenzte Quellenbegründung.")
            verdict = "PASS" if score == 1 else "FAIL"
            results.append(dict(id=case["id"], metric=metric.__class__.__name__, score=score, verdict=verdict,
                                expected_verdict=case["expected_verdict"], matched=verdict == case["expected_verdict"],
                                reason=reason, verified=False))
        return dict(status="PASS" if all(item["matched"] for item in results) else "FAIL", framework="deepeval",
                    version="4.3.1", model=MODEL, model_digest=EXPECTED_DIGEST, max_calls=MAX_CALLS,
                    calls_attempted=bridge.calls_attempted, cases=results, audit=bridge.audit,
                    network_audit=network_audit, privacy=dict(telemetry_opt_out=True, cloud_login=False,
                    dotenv_disabled=True, legacy_keyfile_disabled=True, tracing_enabled=False,
                    network_enforcement="Process-local audited Python sockets restricted to fixed numeric loopback",
                    os_network_sandbox=False), verified=False,
                    context_budget=dict(max_input_utf8_bytes=8500, num_ctx=4096, num_predict=1200,
                                        exact_token_count_verified=False),
                    scope="Vier synthetische Integrationsfälle; keine allgemeine Judge- oder Qualitätsabnahme.")
    except Exception as exc:
        return _error_report("DeepEval-Prüfung beendet: " + str(exc), calls_attempted=bridge.calls_attempted if bridge else 0,
                             cases=results, audit=bridge.audit if bridge else [], network_audit=network_audit)


def run_deepeval_smoke(root: Path) -> dict:
    """Explicit setup action; this function is never called from the answer hook."""
    root = Path(root).resolve()
    try:
        _smoke_cases(root)
    except DeepEvalError as exc:
        return _error_report(str(exc))
    interpreter = root / "work/evals-runtime/.venv/Scripts/python.exe"
    wrapper = root / "deepeval-worker.py"
    if not interpreter.is_file() or not wrapper.is_file():
        return _error_report("Dedizierte lokale DeepEval-Laufzeit oder Workerdatei fehlt; kein Modellaufruf.")
    command = [str(interpreter), "-I", str(wrapper), "--root", str(root)]
    try:
        return run_worker(command, cwd=root, timeout_seconds=WORKER_TIMEOUT_SECONDS)
    except DeepEvalError as exc:
        return _error_report(str(exc))


def worker_main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Explizite lokale DeepEval-Integrationsprüfung")
    parser.add_argument("--root", required=True)
    args = parser.parse_args(argv)
    report = _smoke_worker(Path(args.root).resolve())
    sys.stdout.reconfigure(encoding="utf-8", errors="strict")
    print(json.dumps(report, ensure_ascii=False, allow_nan=False))
    return 0
