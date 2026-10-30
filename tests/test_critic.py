"""Contract tests against a real, local fake Ollama HTTP service (no model)."""

import copy
import json
import os
import socket
import sys
import threading
import time
import unittest
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from guardrails_local.critic import CriticError, OllamaCritic


MODEL = "gpt-oss:20b"
DIGEST = "f38aa0c53da5f8c49d08c43a99df24ff53167fe68e24664a7777288e7656fdfe"
DRAFT = {"text": "Verwende huihui_ai/gpt-oss-abliterated:20b-mxfp4 lokal über Ollama mit Kontext 4096.",
         "source": "fixture", "task": "Empfehlung prüfen"}
REQUIREMENTS = [{"requirement_id": "LOCAL_ONLY", "description": "Nur lokale Inferenz"}]
FACTS = {"models": []}
FINDING = {
    "requirement_id": "LOCAL_ONLY", "severity": "critical",
    "description": "Cloud-Aufruf", "evidence": "Nutzt eine externe API",
    "correction": "Vorhandenes lokales Modell einsetzen",
}


def envelope(content=None, **changes):
    result = {
        "model": MODEL, "created_at": "2026-10-16T17:00:00Z", "done": True,
        "done_reason": "stop", "total_duration": 100, "load_duration": 20,
        "prompt_eval_count": 30, "prompt_eval_duration": 40,
        "eval_count": 12, "eval_duration": 40,
        "message": {"role": "assistant", "content": json.dumps(
            content if content is not None else {"status": "pass", "findings": []}),
            "thinking": "PRIVATE_REASONING_MUST_NOT_BE_RETURNED"},
    }
    result.update(changes)
    return result


@contextmanager
def fake_ollama(responses=None):
    """Serve controlled HTTP replies; record actual requests crossing the boundary."""
    routes = {
        "/api/tags": {"models": [{"name": MODEL, "model": MODEL, "digest": DIGEST}]},
        "/api/ps": {"models": []},
        "/api/chat": envelope(),
    }
    routes.update(responses or {})
    calls = []

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_GET(self):
            self.reply()

        def do_POST(self):
            self.reply()

        def reply(self):
            data = self.rfile.read(int(self.headers.get("Content-Length", "0")))
            calls.append({"method": self.command, "path": self.path,
                          "body": json.loads(data) if data else None})
            item = routes[self.path]
            if callable(item):
                item = item()
            status, headers, body, delay = 200, {}, item, 0
            if isinstance(item, tuple):
                status, headers, body, delay = item
            if delay:
                time.sleep(delay)
            body = body if isinstance(body, bytes) else json.dumps(body).encode()
            try:
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                for key, value in headers.items():
                    self.send_header(key, value)
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            except (BrokenPipeError, ConnectionResetError):
                pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    server.daemon_threads = True
    thread = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.01}, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}", calls
    finally:
        server.shutdown()
        server.server_close()
        thread.join(2)


def settings(base_url, **updates):
    result = {"base_url": base_url, "model": MODEL, "expected_digest": DIGEST,
              "timeout_seconds": 1, "num_ctx": 4096, "num_predict": 1200}
    result.update(updates)
    return result


class CriticTests(unittest.TestCase):
    def review(self, base_url, **updates):
        return OllamaCritic(settings(base_url, **updates)).review(DRAFT, REQUIREMENTS, FACTS)

    def test_sends_bounded_schema_chat_after_exact_model_preflight(self):
        configuration = json.loads((Path(__file__).resolve().parents[1] /
                                    "config/settings.json").read_text(encoding="utf-8"))
        with fake_ollama() as (url, calls):
            configuration.update(base_url=url, timeout_seconds=1)
            try:
                result = OllamaCritic(configuration).review(DRAFT, REQUIREMENTS, FACTS)
            except CriticError as exc:
                self.fail("Project settings must admit the approved exact model package: " + str(exc))
        self.assertEqual("pass", result["status"])
        self.assertEqual([], result["findings"])
        self.assertEqual(MODEL, result["model"])
        self.assertEqual(DIGEST, result["model_digest"])
        self.assertEqual(30, result["metrics"]["prompt_eval_count"])
        self.assertEqual({"status": "pass", "findings": []}, result["response"])
        self.assertNotIn("PRIVATE_REASONING", json.dumps(result))
        self.assertEqual(["/api/tags", "/api/ps", "/api/chat"], [c["path"] for c in calls])
        request = calls[-1]["body"]
        self.assertEqual("POST", calls[-1]["method"])
        self.assertEqual(MODEL, request["model"])
        self.assertIs(False, request["stream"])
        self.assertEqual("low", request["think"])
        self.assertEqual(0, request["keep_alive"])
        self.assertEqual({"num_ctx": 4096, "num_predict": 1200, "temperature": 0}, request["options"])
        self.assertEqual("object", request["format"]["type"])
        self.assertIs(False, request["format"]["additionalProperties"])
        self.assertEqual(["status", "findings"], request["format"]["required"])
        self.assertIn("LOCAL_ONLY", json.dumps(request["format"]))
        self.assertIn("Empfehlung", request["messages"][-1]["content"])

    def test_preserves_well_formed_raw_findings_without_inventing_evidence_binding(self):
        cases = [
            {"status": "fail", "findings": [FINDING], "verified": False},
            {"status": "unverified", "findings": [{**FINDING, "requirement_id": "TECHNICAL_EVIDENCE", "severity": "warning"}]},
            {"status": "unverified", "findings": [{**FINDING, "requirement_id": "SEMANTIC_REVIEW", "severity": "info"}]},
            {"status": "unverified", "findings": [{**FINDING, "requirement_id": "INDEPENDENCE", "severity": "error"}]},
        ]
        for content in cases:
            with self.subTest(content=content), fake_ollama({"/api/chat": envelope(content)}) as (url, _):
                result = self.review(url)
                self.assertEqual("unverified", result["status"])
                self.assertEqual(content, result["response"])
                self.assertTrue(all(f["severity"] == "warning" for f in result["findings"]))

    def test_rejects_invalid_or_contradictory_critic_json(self):
        bad = [
            {"status": "pass"}, {"findings": []}, {"status": "PASS", "findings": []},
            {"status": "pass", "findings": [FINDING]}, {"status": "fail", "findings": []},
            {"status": "unverified", "findings": []}, {"status": "pass", "findings": [], "verified": True},
            {"status": "pass", "findings": [], "unexpected": "field"},
            {"status": "pass", "findings": "none"}, {"status": "pass", "findings": None},
            {"status": "fail", "findings": [{**FINDING, "requirement_id": "MADE_UP"}]},
            {"status": "fail", "findings": [{**FINDING, "severity": "catastrophic"}]},
            {"status": "fail", "findings": [{**FINDING, "description": " "}]},
            {"status": "fail", "findings": [{**FINDING, "correction": 123}]},
            {"status": "fail", "findings": [{**FINDING, "verified": False}]},
            {"status": "fail", "findings": [{k: v for k, v in FINDING.items() if k != "evidence"}]},
            [], "pass", None,
        ]
        for content in bad:
            reply = envelope()
            reply["message"]["content"] = json.dumps(content)
            with self.subTest(content=content), fake_ollama({"/api/chat": reply}) as (url, calls):
                with self.assertRaises(CriticError):
                    self.review(url)
                self.assertEqual(1, sum(c["path"] == "/api/chat" for c in calls))

    def test_rejects_unparseable_duplicate_key_and_nonfinite_json(self):
        for content in ["not json", '```json\n{"status":"pass","findings":[]}\n```',
                        '{"status":"fail","status":"pass","findings":[]}',
                        '{"status":"pass","findings":[],"verified":NaN}']:
            reply = envelope()
            reply["message"]["content"] = content
            with self.subTest(content=content), fake_ollama({"/api/chat": reply}) as (url, _):
                with self.assertRaises(CriticError):
                    self.review(url)

    def test_rejects_protocol_failures_and_truncation(self):
        replies = [
            envelope(done=False), envelope(done=1), envelope(done_reason="length"),
            envelope(model="foreign:model"), envelope(message={"role": "assistant"}),
            envelope(message={"role": "user", "content": '{"status":"pass","findings":[]}'}),
            envelope(message={"role": "assistant", "content": {"status": "pass", "findings": []}}),
            envelope(error="out of memory"), envelope(prompt_eval_count=-1),
            b'{"done":',
        ]
        for reply in replies:
            with self.subTest(reply=reply), fake_ollama({"/api/chat": reply}) as (url, _):
                with self.assertRaises(CriticError):
                    self.review(url)

    def test_rejects_remote_or_ambiguous_base_url_before_any_request(self):
        bad = ["https://127.0.0.1:11434", "http://localhost:11434", "http://example.com", "http://127.1",
               "http://127.0.0.2", "http://2130706433", "http://0x7f000001", "http://[::ffff:127.0.0.1]",
               "http://user:pass@127.0.0.1", "http://127.0.0.1/api", "http://127.0.0.1/?a=1",
               "http://127.0.0.1/#fragment", "http://127.0.0.1?", "http://127.0.0.1#", " http://127.0.0.1",
               "http://127.0.0.1:0", "http://127.0.0.1:65536", "http://127.0.0.1\n"]
        for url in bad:
            with self.subTest(url=url), self.assertRaises(CriticError):
                OllamaCritic(settings(url))

    def test_accepts_numeric_ipv6_loopback_configuration(self):
        self.assertIsInstance(OllamaCritic(settings("http://[::1]:11434")), OllamaCritic)

    def test_ignores_environment_proxy(self):
        with fake_ollama() as (url, calls), fake_ollama() as (proxy_url, proxy_calls):
            with patch.dict(os.environ, {"HTTP_PROXY": proxy_url, "HTTPS_PROXY": proxy_url,
                                         "ALL_PROXY": proxy_url, "NO_PROXY": "", "no_proxy": ""}):
                result = self.review(url)
        self.assertEqual("pass", result["status"])
        self.assertEqual(3, len(calls))
        self.assertEqual([], proxy_calls)

    def test_rejects_redirect_without_contacting_destination_or_retry(self):
        for status in (301, 302, 303, 307, 308):
            with self.subTest(status=status), fake_ollama() as (destination, destination_calls):
                with fake_ollama({"/api/tags": (status, {"Location": destination + "/api/tags"}, {}, 0)}) as (url, calls):
                    with self.assertRaises(CriticError):
                        self.review(url)
                    self.assertEqual(["/api/tags"], [c["path"] for c in calls])
                self.assertEqual([], destination_calls)

    def test_rejects_missing_or_changed_model_before_inference(self):
        for models in ([], [{"name": MODEL, "digest": "0" * 64}],
                       [{"name": "huihui_ai/gpt-oss-abliterated:20b-mxfp4",
                         "digest": "81c701845c4945940852ba02e3fda8b919cd513da988eec9e3b4cd7bde243b4c"}],
                       [{"name": MODEL + "x", "digest": DIGEST}],
                       [{"name": MODEL, "digest": DIGEST}, {"name": MODEL, "digest": "0" * 64}]):
            with self.subTest(models=models), fake_ollama({"/api/tags": {"models": models}}) as (url, calls):
                with self.assertRaises(CriticError):
                    self.review(url)
                self.assertEqual(["/api/tags"], [c["path"] for c in calls])

    def test_foreign_loaded_model_blocks_and_own_loaded_model_is_allowed(self):
        for loaded in ([{"name": "foreign:model", "digest": "0" * 64}],
                       [{"name": MODEL, "digest": "0" * 64}], [{}]):
            with self.subTest(loaded=loaded), fake_ollama({"/api/ps": {"models": loaded}}) as (url, calls):
                with self.assertRaises(CriticError):
                    self.review(url)
                self.assertEqual(["/api/tags", "/api/ps"], [c["path"] for c in calls])
        with fake_ollama({"/api/ps": {"models": [{"name": MODEL, "digest": DIGEST}]}}) as (url, calls):
            self.assertEqual("pass", self.review(url)["status"])
            self.assertEqual(3, len(calls))

    def test_timeout_and_http_failure_are_not_retried(self):
        for route, reply in [("/api/tags", (503, {}, {"error": "down"}, 0)),
                             ("/api/chat", (200, {}, envelope(), 0.15))]:
            with self.subTest(route=route), fake_ollama({route: reply}) as (url, calls):
                with self.assertRaises(CriticError):
                    self.review(url, timeout_seconds=0.03)
                self.assertEqual(1, sum(c["path"] == route for c in calls))

    def test_connection_failure_is_a_defined_critic_error(self):
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            port = sock.getsockname()[1]
        with self.assertRaises(CriticError):
            self.review(f"http://127.0.0.1:{port}", timeout_seconds=0.05)

    def test_rejects_oversized_input_before_contacting_model_server(self):
        with fake_ollama() as (url, calls):
            with self.assertRaises(CriticError):
                OllamaCritic(settings(url)).review({**DRAFT, "text": "ä" * 8500}, REQUIREMENTS, FACTS)
            self.assertEqual([], calls)

    def test_input_validation_does_not_mutate_caller_objects(self):
        draft, requirements, facts = copy.deepcopy((DRAFT, REQUIREMENTS, FACTS))
        with fake_ollama() as (url, _):
            OllamaCritic(settings(url)).review(draft, requirements, facts)
        self.assertEqual((DRAFT, REQUIREMENTS, FACTS), (draft, requirements, facts))

    def test_rejects_malformed_settings_and_input_before_network(self):
        for overrides in ({"timeout_seconds": 0}, {"num_ctx": 8192}, {"num_predict": 0},
                          {"num_predict": 1201}, {"expected_digest": "bad"}, {"model": "foreign:model"},
                          {"model": "huihui_ai/gpt-oss-abliterated:20b-mxfp4",
                           "expected_digest": "81c701845c4945940852ba02e3fda8b919cd513da988eec9e3b4cd7bde243b4c"},
                          {"timeout_seconds": True}, {"timeout_seconds": float("inf")}):
            with self.subTest(overrides=overrides), self.assertRaises(CriticError):
                OllamaCritic(settings("http://127.0.0.1:11434", **overrides))
        inputs = [(None, REQUIREMENTS, FACTS), (DRAFT, {}, FACTS), (DRAFT, REQUIREMENTS, []),
                  (DRAFT, [], FACTS), (DRAFT, [{"requirement_id": ""}], FACTS),
                  (DRAFT, REQUIREMENTS * 2, FACTS), (DRAFT, REQUIREMENTS, {"x": float("nan")})]
        with fake_ollama() as (url, calls):
            for args in inputs:
                with self.subTest(args=args), self.assertRaises(CriticError):
                    OllamaCritic(settings(url)).review(*args)
            self.assertEqual([], calls)

    def test_response_size_limit_stops_before_inference(self):
        with fake_ollama({"/api/tags": b" " * (262144 + 1)}) as (url, calls):
            with self.assertRaises(CriticError):
                self.review(url)
            self.assertEqual(["/api/tags"], [c["path"] for c in calls])

    def test_malformed_chunked_transport_is_reported_as_critic_error(self):
        with fake_ollama({"/api/chat": (200, {"Transfer-Encoding": "chunked"}, b"not-a-chunk\r\n", 0)}) as (url, calls):
            with self.assertRaises(CriticError):
                self.review(url)
            self.assertEqual(1, sum(c["path"] == "/api/chat" for c in calls))

    def test_huge_timeout_integer_is_a_defined_configuration_error(self):
        with self.assertRaises(CriticError):
            OllamaCritic(settings("http://127.0.0.1:11434", timeout_seconds=10 ** 1000))


if __name__ == "__main__":
    unittest.main()
