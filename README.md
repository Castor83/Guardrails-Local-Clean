# Guardrails Local

Verbindliche Datenflussentscheidung vom 20.10.2026:
[Private Verarbeitung und öffentliche Recherche](docs/DATENFLUSS-REGELN.md).
Die Regeln sind dokumentiert; vollständige technische Durchsetzung und Abnahme
sind damit noch nicht nachgewiesen.

Ausführbarer lokaler Prototyp für die Qualitätskontrolle von Modell- und
API-Empfehlungen. Projekt: `E:\Guardrails-Local`, Stand 16.10.2026.
Guardrails AI prüft harte Regeln, gpt-oss ergänzt eine lokale semantische Prüfung.
Die Freigabe liegt im Python-Orchestrator. ChatGPT-Ausgaben können bewusst
eingefügt oder als Datei importiert werden.

**Wichtiger realer Befund:** Der vorhandene gpt-oss-Critic hat den absichtlich
falschen GPT-4o-Cloudvorschlag als `pass` bewertet. Die deterministische Prüfung
hat die Freigabe trotzdem verhindert. Der Critic ist damit technisch integriert,
seine fachliche Zuverlässigkeit ist nicht abgenommen.
Auch in einem realen `fail`-Ergebnis schlug der Critic unbrauchbare Korrekturen
wie bloßes Ändern von Faktenflags vor. Solche Vorschläge bleiben im Audit als
unverifizierte Modellhinweise erhalten; automatische Korrekturaufträge übernehmen
sie nicht. Korrekturaufträge stammen aus den Hostregeln und verlangen bei
semantischen Bedenken eine erneute Prüfung tatsächlicher Belege.

## Starten

Die vorhandene Umgebung wird weiterverwendet, es wurde nichts installiert.

```powershell
Set-Location 'E:\Guardrails-Local'
& 'C:\Users\REDACTED_USER\.venv\Scripts\python.exe' main.py serve
```

Alternativ `Start-Guardrails.ps1` ausführen. Die Konsole gibt eine lokale URL mit
einem zufälligen Zugriffstoken aus. Diese vollständige URL im Browser öffnen,
die gewünschte Antwort selbst einfügen und „Lokal prüfen“ wählen. `Strg+C` beendet
den lokalen Dienst. Es erfolgt kein automatischer Browserstart.

Erst eine tatsächliche Prüfung ruft das festgelegte lokale Modell auf.
Der Dienst lauscht ausschließlich auf `127.0.0.1`. Der Token bleibt im
Browserfragment und wird nach Einlesen aus der Adresszeile entfernt. Eine
Neuladung der Seite erfordert erneut die vollständige Start-URL.

`--offline` startet die Oberfläche ohne Critic. Dann ist vollständiges `PASS`
ausgeschlossen. Harte Verstöße werden weiterhin abgelehnt.

## Datei prüfen

```powershell
& 'C:\Users\REDACTED_USER\.venv\Scripts\python.exe' main.py check --input examples\cloud.txt --json
& 'C:\Users\REDACTED_USER\.venv\Scripts\python.exe' main.py check --input examples\local.txt --json
& 'C:\Users\REDACTED_USER\.venv\Scripts\python.exe' main.py check --input 'C:\Pfad\Antwort.txt' --source chatgpt --json
```

Die letzte Zeile setzt einen real vorhandenen UTF-8-Text voraus. `--source`
kennzeichnet die behauptete Herkunft, beweist sie nicht. JSON-Dateien enthalten
ein strukturiertes Entwurfsobjekt; Beispiel:

```json
{
  "text": "Verwende huihui_ai/gpt-oss-abliterated:20b-mxfp4 lokal über Ollama mit Kontext 16384.",
  "source": "manual",
  "task": "Modell- und API-Empfehlung prüfen",
  "recommendations": [
    {
      "model": "huihui_ai/gpt-oss-abliterated:20b-mxfp4",
      "execution": "local",
      "context_tokens": 16384,
      "estimated_vram_gb": null,
      "evidence_quote": "Verwende huihui_ai/gpt-oss-abliterated:20b-mxfp4 lokal über Ollama mit Kontext 16384."
    }
  ]
}
```

Eingabeflags wie `abliterated_verified` sind unzulässig. Verifizierte Fakten
stammen ausschließlich aus dem lokalen Betreiberkatalog. Alle erkannten
Textkonfigurationen werden zusätzlich geprüft; JSON kann Textangaben nicht
ausblenden.

Exitcodes: `0` PASS, `2` FAIL/UNVERIFIED/ESCALATED, `3` ERROR.

## Grenzen der Freigabe

- `PASS` gilt für den ausgewiesenen Prüfumfang, nicht für beliebige Behauptungen.
- Der Textimport versteht derzeit nur die dokumentierten engen Satzformen in
  `examples/` sowie das vorgegebene Negativ- und Umbenennungsbeispiel. Andere
  Texte oder uneindeutige Warnungs-/Zitatkontexte bleiben `UNVERIFIED`.
- Ein gültiges Critic-JSON beweist keine fachliche Richtigkeit.
- Ein enger statischer AST-Prüfer erkennt im übernommenen Originalbeispiel den
  lokal nicht vorhandenen Aufruf `Guard.from_string`. Er führt keinen Code aus.
  Harte Ablehnung setzt zusätzlich einen im Betreiberkatalog mit Texthash
  gebundenen Beleg für die Rolle als ausführbare Empfehlung voraus; andere
  Rollen bleiben `UNVERIFIED`. Das ist keine allgemeine Pythonprüfung.
- ChatGPTs interne Erzeugerfamilie ist nicht nachgewiesen; ein als `chatgpt`
  markierter Import erhält deshalb keine vollständige Unabhängigkeitsfreigabe.
  Sichere Regelverstöße bleiben unabhängig davon `FAIL`.
- Es gibt keine interne Kontrolle der ChatGPT-Anzeige. Die eigene Oberfläche
  hält nur ihren eigenen Bereich „Freigegebenes Ergebnis“ zurück.
- Ein vom Benutzer unverändert eingefügter ChatGPT-Antwortausschnitt wurde
  manuell übernommen und mit echtem lokalem Critic geprüft. Wortlaut, SHA256,
  Übernahmeart und Ergebnisse stehen in `docs/CHATGPT-ORIGINALPRUEFUNG.md`.
  Die Herkunft beruht auf der Benutzerangabe, nicht auf einer Authentifizierung
  des internen ChatGPT-Modells.
- Kein unabhängiges lokales Entwicklermodell wurde neu installiert oder
  eingerichtet. Die Korrekturschnittstelle wird mit kontrollierten Fixtures
  geprüft; das ist keine reale KI-Korrektur.

## Korrekturen und Audit

`Orchestrator.run(draft, corrector=None, max_corrections=0)` erlaubt höchstens
zwei Korrekturen nach dem ersten Entwurf. Der aufrufbare Korrektor erhält
`(draft, correction_order, correction_index)` mit Index 1 oder 2. Auftrag,
Regeln, Fakten und ursprüngliche Erzeugeridentität werden nicht vom Korrektor
ersetzt. Ausbleibende Freigabe nach ausgeschöpftem Budget ergibt `ESCALATED`.

Für kontrollierte Tests kann die CLI `--corrections examples\corrections.json`
verwenden. Sie kennzeichnet den Fixture-Korrektor ausdrücklich als „keine KI“.

Pro Lauf entsteht `logs/<UUID>.jsonl` mit Originalentwurf, Anforderungs- und
Faktensnapshot samt SHA256, jedem Versuch, Korrekturauftrag und Abschluss.
Die Dateischreibvorgänge werden vor einer Freigabe geflusht und mit `fsync`
bestätigt. Ein Auditfehler verhindert `PASS`.

Diese Dateien enthalten Eingaben im Klartext. Die Hashes helfen bei der
Zuordnung; sie bilden keinen manipulationssicheren externen Vertrauensanker.
Der eigene Benutzeraccount kann Programm, Katalog und Logs verändern.

## Konfiguration

`config/requirements.json` enthält globale, technische, Projekt- und
Qualitätsregeln. Die acht Pflichtregeln und ihre Prüfmethoden sind im Code
festgelegt; Entfernen oder Abschalten ergibt `ERROR`. Zusätzliche
`deny_model`-Regeln können Modelle ausschließen. Unbekannte Prüfmethoden
bleiben `UNVERIFIED`. Es gibt keinen Modellzugriff zum Ändern dieser Dateien.

`config/catalog.json` dokumentiert Herkunft und exakte Variante mit Quellen,
lokalem Digest und dem historischen Hardwarebeleg aus der Benutzerübergabe.
Die Abliterationsherkunft ist durch Anbieterangaben und Paketmetadaten belegt;
eine vollständige eigene Gewichtsanalyse wurde nicht ausgeführt.

`config/settings.json` pinnt seit der Nutzerfreigabe vom 23.10.2026 das vorhandene
`gpt-oss:20b` mit Digest
`f38aa0c53da5f8c49d08c43a99df24ff53167fe68e24664a7777288e7656fdfe`.
Die vorherige Huihui-Prüfmodellbindung ist abgelöst; historische Katalogbelege
und Empfehlungs-Testfälle bleiben erhalten. Das neue Prüfmodell wird nicht
als abliteriert oder unabhängig abgenommen bezeichnet. Andere Modelle werden
abgewiesen. Feste 4096 Kontexttoken, bis zu 1200 Ausgabetoken, `think=low`,
`keep_alive=0`. Fremde geladene Ollama-Modelle blockieren den Start und werden
nicht entladen. Es gibt keine automatischen Transportwiederholungen.

Der Client verwendet numerisches Loopback-HTTP, keine Proxys oder Redirects.
Guardrails-Servermodus und Telemetrie sind im eigenen Prozess deaktiviert;
die vorhandene globale Guardrails-Konfiguration wird nicht verändert.
8500 UTF-8-Bytes sind eine Eingabegrenze, keine exakte Tokenzählung. Der
Socket-Timeout begrenzt einzelne Operationen; es gibt noch keinen harten
externen Wallclock-Wächter. Ollamas Vorprüfung ist keine atomare Serversperre.

## Anschluss an einen Codex-Chat

Der ergänzte lokale Anschluss verbindet eine Vorprüfung des Antwortentwurfs
mit einer automatischen Nachprüfung über Codex-Hooks. Er verwendet die
vorhandenen Regeln und optional den ausdrücklich freigegebenen lokalen Critic.
Herkunft, Unsicherheiten und die Grenze zur bereits sichtbaren Antwort bleiben
erhalten. Einrichtung, Sitzungsbegrenzung und getrennte Ausführungsnachweise:
[`docs/CODEX-INTEGRATION.md`](docs/CODEX-INTEGRATION.md).

## Reproduzierbare Tests

Der explizite lokale Qualitätsauftrag mit DeepEval, Guardrails AI und echten
Promptfoo-Regressionen ist in [docs/QUALITY-STACK.md](docs/QUALITY-STACK.md)
beschrieben. Er aktiviert keine abgeschalteten Chats.

```powershell
Set-Location 'E:\Guardrails-Local'
& 'C:\Users\REDACTED_USER\.venv\Scripts\python.exe' -m unittest discover -s tests -v
```

Die automatisierte Suite benötigt keinen Modellaufruf. Sie verwendet echte
lokale HTTP-Testserver für den Ollama-Protokollvertrag und getrennte Testdoubles
für die semantische Modellantwort. Echte Inferenz wurde zusätzlich separat
ausgeführt und dokumentiert. Guardrails 0.11.0 erzeugt dabei bekannte
Deprecation-Warnungen; die Umgebung wurde dafür nicht aktualisiert.

Details: `docs/ABNAHME.md`, `docs/CHATGPT-INTEGRATION.md`, `docs/FORTSCHRITT.md`.
Die vollständige deutsche Originalanforderung bleibt in
`docs/ORIGINALAUFTRAG.txt` unverändert erhalten.
