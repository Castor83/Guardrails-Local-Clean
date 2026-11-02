"""Lokale Importgrenzen; echte Orchestrierung ohne Modellaufruf."""

import base64
import contextlib
import hashlib
import http.client
import io
import json
from pathlib import Path
import re
import shutil
import socket
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from guardrails_local import cli
from guardrails_local.orchestrator import Orchestrator
from guardrails_local.webapp import create_server


class LocalImportTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        shutil.copytree(ROOT / "config", self.root / "config")

    def invoke(self, arguments):
        output = io.StringIO()
        errors = io.StringIO()
        with patch.object(cli, "_project_root", return_value=self.root):
            with contextlib.redirect_stdout(output), contextlib.redirect_stderr(errors):
                code = cli.main(arguments)
        return code, output.getvalue(), errors.getvalue()

    def test_cli_text_import_is_audited_and_never_offline_pass(self):
        path = self.root / "entwurf.txt"
        path.write_text("Eine noch nicht belegte Empfehlung: Grüße aus Köln.", encoding="utf-8")
        code, output, errors = self.invoke(["check", "--input", str(path), "--offline", "--source", "chatgpt", "--json"])
        self.assertEqual(code, 2, errors)
        report = json.loads(output)
        self.assertNotEqual(report["final_status"], "PASS")
        self.assertIsNone(report["released_text"])
        draft = report["attempts"][0]["draft"]
        self.assertEqual(draft["source"], "chatgpt")
        self.assertIn("Grüße aus Köln", draft["text"])
        self.assertIn("Grüße", output)
        self.assertTrue(Path(report["log_path"]).is_file())

    def test_cli_structured_json_import(self):
        path = self.root / "entwurf.json"
        path.write_text(json.dumps({"text": "Unbelegt", "source": "manual", "task": "Prüfen", "recommendations": []}), encoding="utf-8")
        code, output, errors = self.invoke(["check", "--input", str(path), "--offline", "--json"])
        self.assertEqual(code, 2, errors)
        self.assertEqual(json.loads(output)["attempts"][0]["draft"]["text"], "Unbelegt")

    def test_cli_rejects_more_than_two_fixture_corrections(self):
        draft = self.root / "draft.txt"
        draft.write_text("Entwurf", encoding="utf-8")
        corrections = self.root / "corrections.json"
        corrections.write_text(json.dumps([{"text": "x"}] * 3), encoding="utf-8")
        code, output, errors = self.invoke(["check", "--input", str(draft), "--offline", "--corrections", str(corrections), "--json"])
        self.assertEqual(code, 3)
        self.assertIn("höchstens zwei", json.loads(output)["error"])

    def test_cli_missing_file_is_error_without_traceback(self):
        code, output, errors = self.invoke(["check", "--input", str(self.root / "missing.txt"), "--offline", "--json"])
        self.assertEqual(code, 3)
        self.assertEqual(json.loads(output)["final_status"], "ERROR")
        self.assertNotIn("Traceback", output + errors)

    def test_fixture_corrector_is_explicitly_labelled(self):
        callback = cli.FixtureCorrector([{"text": "Korrektur", "recommendations": []}])
        result = callback({"text": "Alt"}, {"findings": []}, 1)
        self.assertTrue(result["fixture_generated"])
        self.assertEqual(result["source"], "fixture-correction")
        self.assertIn("keine KI", callback.description)

    def test_cli_fixture_corrections_do_not_override_unverified_required_critic(self):
        path = self.root / "entwurf.txt"
        path.write_text("Installiere GPT-4o über die OpenAI-API.", encoding="utf-8")
        corrections = self.root / "corrections.json"
        corrections.write_text(json.dumps([{"text": "Installiere GPT-4o über die OpenAI-API.", "recommendations": []}] * 2), encoding="utf-8")
        code, output, errors = self.invoke(["check", "--input", str(path), "--offline", "--corrections", str(corrections), "--json"])
        self.assertEqual(code, 2, errors)
        report = json.loads(output)
        self.assertEqual(len(report["attempts"]), 1)
        self.assertEqual('FAIL', report['final_status'])
        self.assertEqual('unverified', report['attempts'][0]['critic']['status'])
        self.assertIn("keine KI", report["fixture_corrector"])
        self.assertFalse(report['attempts'][0]['draft'].get('fixture_generated', False))
        self.assertNotEqual('fixture-correction', report['attempts'][0]['draft']['source'])


class LocalHTTPTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        shutil.copytree(ROOT / "config", root / "config")
        self.server = create_server(Orchestrator(root, critic=None), port=0, token="unit-test-token")
        self.host = f"127.0.0.1:{self.server.server_port}"
        self.origin = f"http://{self.host}"
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.addCleanup(self.stop_server)

    def stop_server(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)

    def request(self, method="POST", path="/api/check", payload=None, headers=None):
        body = json.dumps(payload if payload is not None else {"text": "Ungeprüfte ChatGPT-Antwort", "source": "chatgpt"}).encode("utf-8") if method == "POST" else None
        request_headers = {"Host": self.host, "Origin": self.origin, "X-Guardrails-Token": self.server.access_token, "Content-Type": "application/json"}
        if headers:
            request_headers.update(headers)
        connection = http.client.HTTPConnection("127.0.0.1", self.server.server_port, timeout=4)
        try:
            connection.request(method, path, body=body, headers=request_headers)
            response = connection.getresponse()
            return response.status, dict(response.getheaders()), response.read().decode("utf-8")
        finally:
            connection.close()

    def raw_request(self, headers):
        with socket.create_connection(("127.0.0.1", self.server.server_port), timeout=4) as connection:
            connection.sendall(("POST /api/check HTTP/1.0\r\n" + f"Host: {self.host}\r\nOrigin: {self.origin}\r\nX-Guardrails-Token: {self.server.access_token}\r\nContent-Type: application/json\r\n" + headers + "\r\n\r\n").encode("ascii"))
            return connection.recv(4096).decode("utf-8").split("\r\n")[0]

    def test_authenticated_manual_chatgpt_import(self):
        status, headers, body = self.request()
        self.assertEqual(status, 200, body)
        report = json.loads(body)
        self.assertNotEqual(report["final_status"], "PASS")
        self.assertIsNone(report["released_text"])
        self.assertEqual(report["attempts"][0]["draft"]["source"], "chatgpt")
        self.assertNotIn("Access-Control-Allow-Origin", headers)

    def test_html_payload_stays_unreleased_data(self):
        malicious = '<img src=x onerror="alert(1)"><script>alert(2)</script>'
        status, headers, body = self.request(payload={"text": malicious, "source": "chatgpt"})
        self.assertEqual(status, 200, body)
        report = json.loads(body)
        self.assertEqual(report["attempts"][0]["draft"]["text"], malicious)
        self.assertIsNone(report["released_text"])
        self.assertEqual(headers["X-Content-Type-Options"], "nosniff")
        self.assertIn("application/json", headers["Content-Type"])

    def test_wrong_token_origin_and_host_are_rejected(self):
        for headers in ({"X-Guardrails-Token": "wrong"}, {"X-Guardrails-Token": "böse"}, {"Origin": "https://chatgpt.com"}, {"Origin": "null"}, {"Host": "attacker.example"}):
            with self.subTest(headers=headers):
                status, _, body = self.request(headers=headers)
                self.assertEqual(status, 403, body)
                self.assertNotIn(self.server.access_token, body)

    def test_missing_invalid_duplicate_and_oversize_length_are_rejected(self):
        for content_headers, code in (("", "411"), ("Content-Length: -1", "400"), ("Content-Length: nope", "400"), ("Content-Length: 0\r\nContent-Length: 0", "400"), ("Content-Length: 131073", "413"), ("Transfer-Encoding: chunked\r\nContent-Length: 0", "400")):
            with self.subTest(headers=content_headers):
                self.assertIn(f" {code} ", self.raw_request(content_headers))

    def test_invalid_payload_and_media_type_are_rejected(self):
        for payload in ({}, {"text": 123}, {"draft": []}, {"text": "x", "draft": {}}):
            with self.subTest(payload=payload):
                self.assertEqual(self.request(payload=payload)[0], 400)
        self.assertEqual(self.request(headers={"Content-Type": "text/plain"})[0], 415)

    def test_only_root_page_and_check_endpoint_exist(self):
        self.assertEqual(self.request(method="GET", path="/unknown")[0], 404)
        self.assertEqual(self.request(path="/other")[0], 404)
        self.assertEqual(self.request(method="GET", headers={"Host": "localhost"})[0], 403)

    def test_page_has_strict_csp_and_safe_separate_output_areas(self):
        status, headers, body = self.request(method="GET", path="/")
        self.assertEqual(status, 200)
        self.assertNotIn(self.server.access_token, body)
        self.assertIn("textContent", body)
        self.assertNotIn("innerHTML", body)
        for element_id in ("draft", "report", "released"):
            self.assertIn(f'id="{element_id}"', body)
        self.assertIn("default-src 'none'", headers["Content-Security-Policy"])
        scripts = re.findall(r"<script>(.*?)</script>", body, re.DOTALL)
        self.assertEqual(len(scripts), 1)
        digest = base64.b64encode(hashlib.sha256(scripts[0].encode("utf-8")).digest()).decode("ascii")
        self.assertIn(f"'sha256-{digest}'", headers["Content-Security-Policy"])
        self.assertNotIn("https://", body)


if __name__ == "__main__":
    unittest.main()
