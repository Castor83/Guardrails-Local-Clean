"""Tokengebundene Loopback-Oberfläche ohne externe Ressourcen oder Export."""

import base64
import hashlib
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
import re
import secrets

from .domain import import_text


MAX_BODY_BYTES = 128 * 1024

SCRIPT = """
const token = new URLSearchParams(location.hash.slice(1)).get('token') || '';
history.replaceState(null, '', '/');
const input = document.getElementById('input');
const draft = document.getElementById('draft');
const report = document.getElementById('report');
const released = document.getElementById('released');
const button = document.getElementById('check');
const message = document.getElementById('message');
message.textContent = token ? 'Bereit zur lokalen Prüfung.' : 'Zugriffstoken fehlt. Die vollständige Start-URL verwenden.';
button.disabled = !token;
button.addEventListener('click', async () => {
  button.disabled = true;
  draft.textContent = input.value;
  report.textContent = '';
  released.textContent = '';
  message.textContent = 'Lokale Prüfung läuft …';
  try {
    const response = await fetch('/api/check', {
      method: 'POST',
      headers: {'Content-Type': 'application/json', 'X-Guardrails-Token': token},
      body: JSON.stringify({text: input.value, source: 'chatgpt'})
    });
    const result = await response.json();
    const attempts = Array.isArray(result.attempts) ? result.attempts : [];
    const last = attempts.length ? attempts[attempts.length - 1] : null;
    const findings = last && last.result && Array.isArray(last.result.findings) ? last.result.findings : [];
    report.textContent = ['Ergebnis: ' + result.final_status,
      result.error || '',
      ...findings.map(item => (item.origin === 'critic' ? 'Critic-Hinweis (unverifiziert): ' : '') + item.description +
        (item.origin === 'critic' ? '\\nUnverifizierter Modellvorschlag: ' : '\\nKorrektur: ') + item.correction),
      result.scope || '',
      result.log_path ? 'Vollständiges lokales Prüfprotokoll: ' + result.log_path : ''
    ].filter(Boolean).join('\\n\\n');
    released.textContent = result.final_status === 'PASS' && typeof result.released_text === 'string' ? result.released_text : '';
    message.textContent = response.ok ? 'Prüfstatus: ' + result.final_status : 'Anfrage zurückgewiesen.';
  } catch (error) {
    report.textContent = 'Lokale Prüfung nicht erreichbar. Keine Freigabe.';
    message.textContent = 'Verbindungsfehler.';
  } finally {
    button.disabled = !token;
  }
});
"""

STYLE = """
body {font: 17px/1.5 system-ui,sans-serif; background:#f3f5f7; color:#17232c; margin:0 auto; padding:28px; max-width:1100px}
h1 {font-size:1.8rem} h2 {font-size:1.25rem} section {background:white; border:1px solid #cbd5dc; border-radius:10px; padding:20px; margin:18px 0}
textarea {box-sizing:border-box; width:100%; min-height:210px; padding:12px; font:inherit} button {font:inherit; background:#164e63; color:white; border:0; border-radius:6px; padding:10px 18px; margin-top:12px} button:disabled {opacity:.55}
pre {white-space:pre-wrap; overflow-wrap:anywhere; min-height:28px; font:15px/1.5 ui-monospace,monospace} .note {color:#465765}
"""

HTML = """<!doctype html>
<html lang="de"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Guardrails – lokale Prüfung</title><style>""" + STYLE + """</style></head>
<body><h1>Lokale Qualitätskontrolle</h1>
<p>ChatGPT-Antwort selbst kopieren und hier einfügen. Die Prüfung erfolgt lokal. Die interne ChatGPT-Anzeige wird dadurch nicht kontrolliert.</p>
<p class="note">Die Herkunft „ChatGPT“ ist eine manuelle Angabe. Das lokale Audit speichert Eingabe und Prüfergebnis im Klartext.</p>
<section><h2>Manuelle ChatGPT-Übernahme</h2><label for="input">Antworttext</label><textarea id="input" placeholder="Antwort hier einfügen …"></textarea><button id="check" type="button" disabled>Lokal prüfen</button><p id="message" role="status"></p></section>
<section><h2>Entwurf</h2><pre id="draft"></pre></section>
<section><h2>Prüfbericht</h2><pre id="report"></pre></section>
<section><h2>Freigegebenes Ergebnis</h2><p class="note">Dieser Bereich wird nur nach vollständiger Freigabe gefüllt.</p><pre id="released"></pre></section>
<script>""" + SCRIPT + """</script></body></html>"""


def _hash_source(value):
    return base64.b64encode(hashlib.sha256(value.encode("utf-8")).digest()).decode("ascii")


class _LocalServer(HTTPServer):
    allow_reuse_address = False

    def get_request(self):
        connection, address = super().get_request()
        connection.settimeout(5)
        return connection, address


def create_server(orchestrator, port=8765, token=None):
    """Bindet ausschließlich numerisches Loopback; startet noch keinen Dienst."""
    if not isinstance(port, int) or isinstance(port, bool) or not 0 <= port <= 65535:
        raise ValueError("Ungültiger lokaler Port.")
    access_token = secrets.token_urlsafe(32) if token is None else token
    if not isinstance(access_token, str) or not re.fullmatch(r"[A-Za-z0-9_-]{8,256}", access_token):
        raise ValueError("Ungültiger Zugriffstoken.")

    class Handler(BaseHTTPRequestHandler):
        server_version = "GuardrailsLocal"
        sys_version = ""

        def log_message(self, format, *args):
            # HTTP-Zugriffszeilen könnten vertrauliche Eingaben enthalten.
            return

        def _response(self, status, payload, content_type="application/json; charset=utf-8"):
            body = payload.encode("utf-8") if isinstance(payload, str) else json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Referrer-Policy", "no-referrer")
            self.send_header("Content-Security-Policy", "default-src 'none'; script-src 'sha256-" + _hash_source(SCRIPT) + "'; style-src 'sha256-" + _hash_source(STYLE) + "'; connect-src 'self'; base-uri 'none'; frame-ancestors 'none'; form-action 'none'")
            self.end_headers()
            self.wfile.write(body)
            self.close_connection = True

        def _error(self, status, message):
            self._response(status, {"final_status": "ERROR", "released_text": None, "error": message})

        def _valid_host(self):
            return self.headers.get_all("Host") == [f"127.0.0.1:{self.server.server_port}"]

        def do_GET(self):
            if not self._valid_host():
                self._error(403, "Host nicht zugelassen.")
            elif self.path != "/":
                self._error(404, "Nicht gefunden.")
            else:
                self._response(200, HTML, "text/html; charset=utf-8")

        def do_POST(self):
            if not self._valid_host():
                self._error(403, "Host nicht zugelassen.")
                return
            if self.path != "/api/check":
                self._error(404, "Nicht gefunden.")
                return
            if self.headers.get_all("Origin") != [f"http://127.0.0.1:{self.server.server_port}"]:
                self._error(403, "Ursprung nicht zugelassen.")
                return
            tokens = self.headers.get_all("X-Guardrails-Token")
            if not tokens or len(tokens) != 1 or not secrets.compare_digest(tokens[0].encode("utf-8"), access_token.encode("ascii")):
                self._error(403, "Zugriffstoken ungültig.")
                return
            lengths = self.headers.get_all("Content-Length")
            if self.headers.get("Transfer-Encoding") is not None:
                self._error(400, "Transfer-Encoding wird nicht unterstützt.")
                return
            if not lengths:
                self._error(411, "Content-Length fehlt.")
                return
            if len(lengths) != 1 or not re.fullmatch(r"[0-9]{1,10}", lengths[0]):
                self._error(400, "Content-Length ungültig.")
                return
            length = int(lengths[0])
            if length > MAX_BODY_BYTES:
                self._error(413, "Eingabe überschreitet 128 KiB.")
                return
            if self.headers.get_content_type() != "application/json":
                self._error(415, "application/json erforderlich.")
                return
            try:
                self.connection.settimeout(5)
                raw_body = self.rfile.read(length)
                if len(raw_body) != length:
                    self._error(400, "Unvollständige Eingabe.")
                    return
                payload = json.loads(raw_body.decode("utf-8"))
                if not isinstance(payload, dict) or ("text" in payload) == ("draft" in payload):
                    raise ValueError("Genau text oder draft erforderlich.")
                if "draft" in payload:
                    if not isinstance(payload["draft"], dict):
                        raise ValueError("draft muss ein Objekt sein.")
                    draft = payload["draft"]
                else:
                    if not isinstance(payload["text"], str) or not isinstance(payload.get("source", "manual"), str):
                        raise ValueError("text und source müssen Text sein.")
                    draft = import_text(payload["text"], source=payload.get("source", "manual"))
            except (ValueError, UnicodeDecodeError, RecursionError):
                self._error(400, "Ungültige JSON-Eingabe; text oder draft erforderlich.")
                return
            except (TimeoutError, OSError):
                self._error(408, "Zeitlimit beim Lesen der Eingabe.")
                return
            try:
                result = orchestrator.run(draft)
                self._response(200, result)
            except Exception:
                # Keine Eingabe, Pfade oder Secrets in einem Fehler zurückgeben.
                self._error(500, "Lokale Prüfung fehlgeschlagen. Keine Freigabe.")

    server = _LocalServer(("127.0.0.1", port), Handler)
    server.access_token = access_token
    return server
