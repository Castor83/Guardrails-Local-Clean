"""Bounded, full-pair native Provenance NLI with a stdlib-only controller.

Only the dedicated worker imports ML libraries.  PASS means entailment of the
complete answer by the explicitly supplied source bundle within this model's
limited scope; it is not a general truth or sentence-by-sentence guarantee.
"""

import hashlib
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import threading
import uuid


MODEL_REPO = "MoritzLaurer/multilingual-MiniLMv2-L6-mnli-xnli"
MODEL_REVISION = "0a71e92a985b6e1ad1828cf67ce9c459639c1dca"
WEIGHTS_SHA256 = "91b323ccf247ec1e3b5925d566230bae7c52de8147e6062b42e250089a3fc80b"
TOKENIZER_SHA256 = "098c131bb4423163db239755e309facaa6850059f850f9f3d88a78344a4b631c"
LABELS = {0: "entailment", 1: "neutral", 2: "contradiction"}
MAX_TOKENS = 512
MAX_VALUE_BYTES = 32768
MAX_SOURCE_BYTES = 65536
WORKER_TIMEOUT_SECONDS = 180
SCOPE = ("Native Provenance NLI: vollständige Antwort gegen vollständiges explizites "
         "Quellenbündel, höchstens 512 Paar-Tokens, CPU/offline; keine allgemeine "
         "Faktengarantie oder satzweise Qualitätsabnahme.")
NETWORK_SCOPE = ("Python-Socket-Audithook im eigenen NLI-Worker; "
                 "keine Betriebssystem-Sandbox.")
_NETWORK_ATTEMPTS = []
_NETWORK_GUARD_INSTALLED = False
_IPV6_PROBE_THREAD = None


class NliUnverified(ValueError):
    """Required evidence or the complete bounded input is unavailable."""


def _report(status, reason=None, **fields):
    result = dict(status=status, scope=SCOPE, **fields)
    if reason:
        result["reason"] = reason
    return result


def _sha(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _labels(mapping):
    if not isinstance(mapping, dict) or len(mapping) != 3:
        raise NliUnverified("Eine vollständige dreiklassige id2label-Zuordnung fehlt.")
    normalized = {}
    for key, value in mapping.items():
        if type(key) is int:
            index = key
        elif isinstance(key, str) and key in {"0", "1", "2"}:
            index = int(key)
        else:
            raise NliUnverified("Ungültiger Klassenindex.")
        if index in normalized or value not in LABELS.values():
            raise NliUnverified("Unbekannte oder doppelte Klassenbezeichnung.")
        normalized[index] = value
    if set(normalized) != {0, 1, 2} or set(normalized.values()) != set(LABELS.values()):
        raise NliUnverified("id2label muss entailment, neutral und contradiction eindeutig abbilden.")
    return normalized


def evaluate_prediction(logits, id2label, *, min_confidence=0.5):
    """Interpret all three logits using the actual model labels, never a binary zip."""
    try:
        labels = _labels(id2label)
        if (not isinstance(logits, (list, tuple)) or len(logits) != 3
                or any(type(x) not in (int, float) or not math.isfinite(x) for x in logits)
                or type(min_confidence) not in (int, float)
                or not math.isfinite(min_confidence) or not 0 < min_confidence <= 1):
            raise NliUnverified("Logits oder Konfidenzgrenze sind ungültig.")
        peak = max(logits)
        exponentials = [math.exp(x - peak) for x in logits]
        denominator = sum(exponentials)
        scores = {labels[i]: value / denominator for i, value in enumerate(exponentials)}
        label = max(scores, key=scores.get)
        confidence = scores[label]
        supported = label == "entailment" and confidence > min_confidence
        return _report("PASS" if supported else "FAIL", label=label,
                       confidence=confidence, scores=scores, min_confidence=min_confidence)
    except (NliUnverified, TypeError, ValueError, OverflowError) as exc:
        return _report("UNVERIFIED", str(exc))


def _local_model_path(value):
    if not isinstance(value, (str, os.PathLike)):
        raise NliUnverified("Ein absoluter lokaler Modellpfad fehlt.")
    raw = os.fspath(value)
    if not isinstance(raw, str) or raw.startswith(("\\\\", "//")) or "://" in raw:
        raise NliUnverified("Remote-Modellpfade und Inferenzendpunkte sind nicht zulässig.")
    path = Path(raw)
    if not path.is_absolute() or not path.is_dir():
        raise NliUnverified("Der absolute lokale Modellordner ist nicht vorhanden.")
    return path.resolve()


def admit_request(value, sources, model_path, *, token_count=None, max_tokens=MAX_TOKENS):
    """Pure admission; the worker must still tokenize the complete pair before inference."""
    binding = {}
    try:
        if (not isinstance(value, str) or not value.strip()
                or len(value.encode("utf-8")) > MAX_VALUE_BYTES):
            raise NliUnverified("Die vollständige, nichtleere Antwort fehlt oder ist zu groß.")
        binding["answer_sha256"] = _sha(value)
        if (not isinstance(sources, list) or not 1 <= len(sources) <= 8
                or any(not isinstance(x, str) or not x.strip() for x in sources)):
            raise NliUnverified("Explizite nichtleere Quellen fehlen; es werden keine Quellen erfunden.")
        bundle = "\n\n".join(sources)
        if len(bundle.encode("utf-8")) > MAX_SOURCE_BYTES:
            raise NliUnverified("Das vollständige Quellenbündel überschreitet die Bytegrenze.")
        binding["source_sha256"] = _sha(bundle)
        model = _local_model_path(model_path)
        if type(max_tokens) is not int or max_tokens != MAX_TOKENS:
            raise NliUnverified("Die feste Grenze beträgt 512 Paar-Tokens.")
        if token_count is not None and (
                type(token_count) is not int or token_count <= 0 or token_count > max_tokens):
            raise NliUnverified("Das vollständige Eingabepaar passt nicht in 512 Tokens; keine Kürzung.")
        return _report("PASS", "Eingabe zugelassen; noch kein semantisches Prüfergebnis.",
                       value=value, sources=list(sources), source_bundle=bundle,
                       model_path=str(model), token_count=token_count,
                       source_sha256=_sha(bundle), answer_sha256=_sha(value),
                       max_tokens=MAX_TOKENS, truncation=False)
    except (NliUnverified, OSError, TypeError, ValueError, UnicodeError) as exc:
        return _report("UNVERIFIED", str(exc), token_count=token_count, truncation=False, **binding)


def _default_model(root):
    return Path(root).resolve() / "work/evals-runtime/model"


def _offline_environment(root=None):
    from .deepeval_adapter import build_worker_environment
    env = build_worker_environment(os.environ)
    home = (Path(root).resolve() if root is not None else Path(__file__).resolve().parents[2]) / 'work/evals-runtime/home'
    env.update(HOME=str(home), USERPROFILE=str(home), APPDATA=str(home / 'AppData/Roaming'),
               LOCALAPPDATA=str(home / 'AppData/Local'))
    env.update(HF_HUB_OFFLINE="1", TRANSFORMERS_OFFLINE="1",
               HF_HUB_DISABLE_TELEMETRY="1", DO_NOT_TRACK="1",
               OTEL_SDK_DISABLED="true", TOKENIZERS_PARALLELISM="false",
               CUDA_VISIBLE_DEVICES="", PYTHONIOENCODING="utf-8",
               GUARDRAILS_RUN_SYNC="true", TORCHINDUCTOR_CACHE_DIR=str(home / "torchinductor"))
    candidates = [home.parent / "nltk_data"]
    for key in ("NLTK_DATA", "APPDATA", "USERPROFILE"):
        value = os.environ.get(key)
        if value and not value.startswith(("\\\\", "//")) and "://" not in value:
            candidate = Path(value)
            if candidate.is_absolute():
                candidates.append(candidate if key == "NLTK_DATA" else candidate / "nltk_data")
    candidates.append(Path(sys.base_prefix) / "nltk_data")
    for candidate in candidates:
        if (candidate / "tokenizers/punkt").is_dir():
            env["NLTK_DATA"] = str(candidate.resolve())
            break
    for name in ("HF_TOKEN", "HUGGING_FACE_HUB_TOKEN", "OPENAI_API_KEY",
                 "CONFIDENT_API_KEY", "ANTHROPIC_API_KEY", "GROQ_API_KEY"):
        env.pop(name, None)
    return env


def _initialize_http_dependencies():
    """Admit urllib3's import-time IPv6 probe only on this synchronous thread."""
    global _IPV6_PROBE_THREAD
    if _IPV6_PROBE_THREAD is not None:
        raise NliUnverified("Das begrenzte HTTP-Importfenster ist bereits geöffnet.")
    _IPV6_PROBE_THREAD = threading.get_ident()
    try:
        import urllib3  # noqa: F401 -- initialize its local IPv6 capability probe
    finally:
        _IPV6_PROBE_THREAD = None


def _offline_socket_audit(event, args):
    """Deny network attempts before optional-library imports in the worker."""
    # urllib3's import-time IPv6 availability probe binds ::1:0 and closes it.
    # It creates neither an outgoing connection nor a listening server. Keep
    # every connect/DNS/sendto and every other bind denied below.
    if (event == "socket.bind" and _IPV6_PROBE_THREAD == threading.get_ident()
            and len(args) > 1 and args[1] == ("::1", 0)):
        return
    if event in {"socket.connect", "socket.connect_ex", "socket.sendto", "socket.bind",
                 "socket.getaddrinfo", "socket.gethostbyname", "socket.gethostbyaddr"}:
        if len(_NETWORK_ATTEMPTS) < 16:
            _NETWORK_ATTEMPTS.append(event)
        raise PermissionError("NLI-Worker: Netzwerkoperation gesperrt: " + event)


def validation_worker(root, request):
    """Launch exactly one dedicated local worker; never retry or use global Python."""
    root = Path(root).resolve()
    admission = admit_request(request.get("value"), request.get("sources"),
                              request.get("model_path"), max_tokens=request.get("max_tokens", MAX_TOKENS))
    if admission["status"] != "PASS":
        return admission
    if Path(admission["model_path"]) != _default_model(root).resolve():
        return _report("UNVERIFIED", "Der Worker akzeptiert nur den festen projektbezogenen Modellordner.")
    runtime = root / "work/evals-runtime/.venv/Scripts/python.exe"
    wrapper = root / "nli-worker.py"
    if not runtime.is_file() or not wrapper.is_file():
        return _report("UNVERIFIED", "Der separate lokale NLI-Worker ist noch nicht eingerichtet.")
    try:
        environment = _offline_environment(root)
        if not environment.get("NLTK_DATA"):
            return _report("UNVERIFIED", "Vorhandene lokale NLTK-Punkt-Ressource fehlt; kein Download und kein Modellaufruf.")
        directory = root / "work/evals-runtime/runs" / ("nli-" + uuid.uuid4().hex)
        directory.mkdir(parents=True, exist_ok=False)
        request_path, response_path = directory / "request.json", directory / "response.json"
        request_path.write_text(json.dumps(request, ensure_ascii=False, allow_nan=False), encoding="utf-8")
        for name in ('HOME', 'APPDATA', 'LOCALAPPDATA'):
            Path(environment[name]).mkdir(parents=True, exist_ok=True)
        options = dict(cwd=str(root), stdin=subprocess.DEVNULL, capture_output=True,
                       text=True, encoding="utf-8", errors="replace", timeout=WORKER_TIMEOUT_SECONDS,
                       check=False, env=environment)
        if os.name == "nt":
            options["creationflags"] = subprocess.CREATE_NO_WINDOW
        completed = subprocess.run([str(runtime), "-I", str(wrapper),
                                    "--request", str(request_path), "--response", str(response_path)], **options)
        if completed.returncode != 0 or not response_path.is_file():
            return _report("ERROR", "Der eigene NLI-Worker lieferte kein gültiges Ergebnis.",
                           worker_exit_code=completed.returncode, audit_directory=str(directory))
        if response_path.stat().st_size > 131072:
            return _report("ERROR", "NLI-Workerergebnis überschreitet die feste Grenze.")
        result = json.loads(response_path.read_text(encoding="utf-8"))
        if not isinstance(result, dict) or result.get("status") not in {"PASS", "FAIL", "UNVERIFIED", "ERROR"}:
            return _report("ERROR", "Ungültiges NLI-Workerergebnis.")
        result["audit_directory"] = str(directory)
        return result
    except subprocess.TimeoutExpired:
        return _report("ERROR", "Der eigene NLI-Worker wurde nach 180 Sekunden beendet; keine Wiederholung.")
    except (OSError, TypeError, ValueError, UnicodeError) as exc:
        return _report("ERROR", "NLI-Worker konnte nicht abgeschlossen werden: " + str(exc)[:1000])


def check_nli(root, value, source_file=None, *, model_path=None):
    """Check an answer only when an explicit full source file is supplied."""
    if source_file is None:
        return _report("UNVERIFIED", "Keine explizite Quelldatei angegeben; keine NLI-Prüfung ausgeführt.")
    try:
        raw_path = os.fspath(source_file)
        if not isinstance(raw_path, str) or raw_path.startswith(("\\\\", "//")) or "://" in raw_path:
            raise NliUnverified("Eine lokale Quelldatei ist erforderlich.")
        path = Path(source_file).resolve()
        if not path.is_file() or path.stat().st_size > MAX_SOURCE_BYTES:
            raise NliUnverified("Die vollständige Quelldatei fehlt oder überschreitet die Grenze.")
        source = path.read_bytes().decode("utf-8")
        selected_model = _default_model(root) if model_path is None else model_path
        admission = admit_request(value, [source], selected_model)
        if admission["status"] != "PASS":
            return admission
        request = dict(value=value, sources=[source], source_file=str(path),
                       model_path=admission["model_path"], max_tokens=MAX_TOKENS,
                       truncation=False)
        result = validation_worker(root, request)
        if not isinstance(result, dict) or result.get("status") not in {"PASS", "FAIL", "UNVERIFIED", "ERROR"}:
            return _report("ERROR", "Ungültiges NLI-Workerergebnis.")
        if result["status"] == "PASS" and not _bound_pass(result, admission):
            return _report("UNVERIFIED", "NLI-PASS fehlt ein vollständiger nativer Eingabe-/Modellbeleg.")
        return result
    except TimeoutError:
        return _report("ERROR", "Der eigene NLI-Worker überschritt sein Zeitlimit; keine Wiederholung.")
    except (OSError, ValueError, TypeError, UnicodeError) as exc:
        return _report("UNVERIFIED", str(exc)[:1000])


def _bound_pass(result, admission):
    if not isinstance(result.get("model"), dict):
        return False
    return (result.get("native_validator") is True and result.get("mode") == "full_pair"
            and result.get("network_guard_installed") is True
            and result.get("blocked_network_operations") == []
            and result.get("source_sha256") == admission["source_sha256"]
            and result.get("answer_sha256") == admission["answer_sha256"]
            and type(result.get("token_count")) is int and 0 < result["token_count"] <= MAX_TOKENS
            and result.get("truncation") is False
            and result.get("model", {}).get("repo") == MODEL_REPO
            and result.get("model", {}).get("revision") == MODEL_REVISION
            and result.get("model", {}).get("weights_sha256") == WEIGHTS_SHA256)


def _file_hash(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _verify_model(root, model_path):
    model = _local_model_path(model_path)
    if model != _default_model(root).resolve():
        raise NliUnverified("Unbekannter Modellpfad; kein Modellwechsel.")
    manifest_path = model / "manifest.json"
    if not manifest_path.is_file() or manifest_path.stat().st_size > 65536:
        raise NliUnverified("Der gepinnte lokale Modellnachweis fehlt.")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    expected = dict(repo=MODEL_REPO, revision=MODEL_REVISION, weights_sha256=WEIGHTS_SHA256)
    if not isinstance(manifest, dict) or any(manifest.get(key) != value for key, value in expected.items()):
        raise NliUnverified("Modellherkunft oder Revision weicht vom festen Nachweis ab.")
    for filename in ("config.json", "model.safetensors", "tokenizer.json", "tokenizer_config.json",
                     "special_tokens_map.json", "sentencepiece.bpe.model"):
        candidate = model / filename
        if not candidate.is_file() or candidate.is_symlink():
            raise NliUnverified("Eine vollständige lokale Modelldatei fehlt: " + filename)
    if (model / "model.safetensors").stat().st_size != 427997022 or _file_hash(model / "model.safetensors") != WEIGHTS_SHA256:
        raise NliUnverified("Modellgewichte stimmen nicht mit der gepinnten SHA256 überein.")
    if _file_hash(model / "tokenizer.json") != TOKENIZER_SHA256:
        raise NliUnverified("Tokenizer stimmt nicht mit dem gepinnten Modell überein.")
    return expected


def create_native_validator(model_path, *, tokenizer=None):
    """Worker-only factory for an actual registered ProvenanceNLI subclass."""
    model_path = _local_model_path(model_path)
    import torch
    from transformers import AutoModelForSequenceClassification, AutoTokenizer
    from guardrails_ai.provenance_nli import ProvenanceNLI
    from guardrails.validator_base import Validator, PassResult, FailResult, register_validator
    from guardrails.settings import settings

    settings.rc.enable_metrics = False

    @register_validator(name="local/offline-full-pair-provenance-nli", data_type="string")
    class OfflineFullPairProvenanceNLI(ProvenanceNLI):
        def __init__(self):
            Validator.__init__(self, on_fail="noop", use_local=True, validation_method="full",
                               top_k=1, max_length=MAX_TOKENS, model_name=str(model_path))
            self._inference_endpoint = None
            self._model_name = str(model_path)
            self._model_checkpoint_path = None
            self._top_k = 1
            self._max_length = MAX_TOKENS
            self._min_confidence = 0.5
            self._device = "cpu"
            self._tokenizer = tokenizer or AutoTokenizer.from_pretrained(
                str(model_path), local_files_only=True, trust_remote_code=False, use_fast=True)
            self._model = AutoModelForSequenceClassification.from_pretrained(
                str(model_path), local_files_only=True, trust_remote_code=False, use_safetensors=True)
            if not self._tokenizer.is_fast or self._tokenizer.model_max_length != MAX_TOKENS:
                raise NliUnverified("Der erwartete vollständige lokale Fast-Tokenizer fehlt.")
            if _labels(self._model.config.id2label) != LABELS or self._model.config.num_labels != 3:
                raise NliUnverified("Die tatsächlichen Modellklassen weichen vom gepinnten Vertrag ab.")
            self._label_names = [LABELS[i] for i in range(3)]
            self._model.to("cpu")
            self._model.eval()
            self.last_prediction = None

        def get_query_function(self, metadata):
            query = metadata.get("query_function")
            if not callable(query):
                raise NliUnverified("Eine explizite vollständige Quellenfunktion ist erforderlich.")
            return query

        def _get_model_prediction_from_inference_endpoint(self, *args, **kwargs):
            raise NliUnverified("Externe Inferenz ist für diesen nativen Validator gesperrt.")

        def _get_model_prediction_from_local_model(self, premise, hypothesis):
            encoded = self._tokenizer(premise, hypothesis, truncation=False,
                                      return_token_type_ids=False, return_tensors="pt")
            token_count = int(encoded["input_ids"].shape[-1])
            admitted = admit_request(hypothesis, [premise], model_path, token_count=token_count)
            if admitted["status"] != "PASS":
                raise NliUnverified(admitted.get("reason", "Das vollständige Eingabepaar ist nicht zugelassen."))
            inputs = {key: value.to("cpu") for key, value in encoded.items()
                      if key in {"input_ids", "attention_mask"}}
            with torch.inference_mode():
                output = self._model(**inputs)
            logits = output.logits[0].detach().cpu().tolist()
            prediction = evaluate_prediction(logits, self._model.config.id2label,
                                             min_confidence=self._min_confidence)
            if prediction["status"] == "UNVERIFIED":
                raise NliUnverified(prediction.get("reason", "Klassenbewertung ist unbestätigt."))
            self.last_prediction = dict(prediction, token_count=token_count)
            return prediction["label"], prediction["confidence"]

        def validate_each_sentence(self, value, query_function, metadata):
            # Native validate() calls this method unconditionally.  The explicit
            # override evaluates the unchanged full answer, without NLTK chunking.
            supported = self.get_nli_evaluation(value, query_function, metadata)
            if supported:
                return PassResult(metadata={"mode": "full_pair"})
            return FailResult(metadata={"mode": "full_pair"}, fix_value=None,
                              error_message="Die vollständige Antwort ist durch das vollständige Quellenbündel nicht gestützt.")

    return OfflineFullPairProvenanceNLI()


def _worker_evaluate(root, request):
    global _NETWORK_GUARD_INSTALLED
    admission = admit_request(request.get("value"), request.get("sources"),
                              request.get("model_path"), max_tokens=request.get("max_tokens", MAX_TOKENS))
    if admission["status"] != "PASS":
        return admission
    if request.get("truncation") is not False:
        raise NliUnverified("Stille Kürzung ist nicht freigegeben.")
    model_identity = _verify_model(root, admission["model_path"])
    if request.get("source_file"):
        raw_source_path = request["source_file"]
        if (not isinstance(raw_source_path, str) or raw_source_path.startswith(("\\\\", "//"))
                or "://" in raw_source_path):
            raise NliUnverified("Die gebundene Quelle muss eine lokale Datei sein.")
        source_path = Path(raw_source_path)
        if (not source_path.is_absolute() or not source_path.is_file()
                or source_path.stat().st_size > MAX_SOURCE_BYTES
                or source_path.read_bytes().decode("utf-8") != admission["source_bundle"]):
            raise NliUnverified("Die vollständige Quelldatei hat sich gegenüber dem gebundenen Auftrag verändert.")

    # This irreversible audit hook belongs exclusively to this short-lived worker.
    offline_env = _offline_environment(root)
    if not offline_env.get("NLTK_DATA"):
        raise NliUnverified("Gebundene lokale NLTK-Punkt-Ressource fehlt; kein Download und kein Modellaufruf.")
    os.environ.clear()
    os.environ.update(offline_env)
    sys.addaudithook(_offline_socket_audit)
    _NETWORK_GUARD_INSTALLED = True
    _initialize_http_dependencies()
    import torch
    from transformers import AutoTokenizer

    torch.set_num_threads(2)
    tokenizer = AutoTokenizer.from_pretrained(admission["model_path"], local_files_only=True,
                                             trust_remote_code=False, use_fast=True)
    encoded = tokenizer(admission["source_bundle"], admission["value"], truncation=False,
                        return_token_type_ids=False)
    token_count = len(encoded["input_ids"])
    bounded = admit_request(admission["value"], admission["sources"], admission["model_path"],
                            token_count=token_count)
    if bounded["status"] != "PASS":
        return bounded
    validator = create_native_validator(admission["model_path"], tokenizer=tokenizer)

    def complete_source(*, text, k):
        if text != admission["value"] or k != 1:
            raise NliUnverified("Die native Quellenanfrage weicht vom vollständigen Paar ab.")
        return [admission["source_bundle"]]

    native_result = validator.validate(admission["value"], {"query_function": complete_source})
    prediction = validator.last_prediction
    if not isinstance(prediction, dict):
        raise NliUnverified("Der native Validator lieferte keine tatsächliche NLI-Klassenbewertung.")
    native_pass = getattr(native_result, "outcome", None) == "pass"
    if native_pass != (prediction["status"] == "PASS"):
        raise NliUnverified("Native Validatorentscheidung und tatsächliche Klassenbewertung widersprechen sich.")
    return dict(prediction, native_validator=True, native_result=type(native_result).__name__,
                mode="full_pair", truncation=False, source_sha256=admission["source_sha256"],
                answer_sha256=admission["answer_sha256"], model=model_identity,
                id2label={str(key): value for key, value in LABELS.items()},
                source_count=len(admission["sources"]),
                local_resources=dict(nltk_data=offline_env["NLTK_DATA"], downloaded=False))


def worker_main(root, request_path, response_path):
    """Fixed wrapper entry; both control files must be inside the runtime runs area."""
    root = Path(root).resolve()
    area = root / "work/evals-runtime/runs"
    try:
        request_file, response_file = Path(request_path).resolve(), Path(response_path).resolve()
        if not request_file.is_relative_to(area) or not response_file.is_relative_to(area):
            raise NliUnverified("Workerdateien liegen außerhalb des festen Laufzeitbereichs.")
        if not request_file.is_file() or request_file.stat().st_size > 262144:
            raise NliUnverified("Der vollständige Workerauftrag fehlt oder ist zu groß.")
        request = json.loads(request_file.read_text(encoding="utf-8"))
        if not isinstance(request, dict):
            raise NliUnverified("Ungültiger Workerauftrag.")
        result = _worker_evaluate(root, request)
    except NliUnverified as exc:
        result = _report("UNVERIFIED", str(exc)[:1000])
    except Exception as exc:
        result = _report("ERROR", type(exc).__name__ + ": " + str(exc)[:1000])
    result["network_scope"] = NETWORK_SCOPE
    result["network_guard_installed"] = _NETWORK_GUARD_INSTALLED
    result["blocked_network_operations"] = list(_NETWORK_ATTEMPTS)
    if _NETWORK_ATTEMPTS:
        result["status"] = "UNVERIFIED"
        result["reason"] = "Eine Netzwerkoperation wurde im NLI-Worker blockiert; keine vollständige Freigabe."
    try:
        # The response path is already scope checked; no arbitrary output targets.
        if not Path(response_path).resolve().is_relative_to(area):
            return 2
        Path(response_path).write_text(json.dumps(result, ensure_ascii=False, allow_nan=False), encoding="utf-8")
    except (OSError, TypeError, ValueError):
        return 2
    return 0


def smoke_nli(root, cases_path=None):
    """Run only the two explicit synthetic source cases, once each, without retries."""
    root = Path(root).resolve()
    path = Path(cases_path) if cases_path is not None else root / "examples/evals/nli-smoke.json"
    try:
        if not path.is_file() or path.stat().st_size > 131072:
            raise NliUnverified("Die begrenzten NLI-Prüffälle fehlen.")
        document = json.loads(path.read_text(encoding="utf-8"))
        canonical = json.dumps(document, ensure_ascii=False, sort_keys=True,
                               separators=(',', ':'), allow_nan=False).encode('utf-8')
        if hashlib.sha256(canonical).hexdigest() != '969d7934a8cf4d02ff2f6cab9d6136085918152dbf19ff9384537716165bacdd':
            raise NliUnverified('NLI-Prüffallinhalt, Schema oder feste Sollurteile wurden verändert.')
        if not isinstance(document, dict):
            raise NliUnverified("Ungültige NLI-Prüffalldatei.")
        cases = document.get("cases")
        if (not isinstance(cases, list) or len(cases) != 2
                or any(not isinstance(case, dict) or not isinstance(case.get("id"), str) for case in cases)
                or {case.get("id") for case in cases} != {"source_supported", "source_contradiction"}):
            raise NliUnverified("Es sind genau der belegte und der widersprechende Quellenfall erforderlich.")
        reports = []
        for case in cases:
            expected = "PASS" if case["id"] == "source_supported" else "FAIL"
            if case.get("expected_verdict") != expected:
                raise NliUnverified("Die vorgegebenen NLI-Sollergebnisse wurden verändert.")
            result = validation_worker(root, dict(value=case.get("actual_output"), sources=case.get("sources"),
                                                  model_path=str(_default_model(root)),
                                                  max_tokens=MAX_TOKENS, truncation=False))
            reports.append(dict(id=case["id"], expected=expected, result=result,
                                matched=result.get("status") == expected and result.get("native_validator") is True))
        return _report("PASS" if all(item["matched"] for item in reports) else "FAIL",
                       "Genau zwei synthetische native NLI-Fälle; keine allgemeine Qualitätsabnahme.", cases=reports)
    except (OSError, TypeError, ValueError, KeyError) as exc:
        return _report("UNVERIFIED", str(exc)[:1000])
