# Lokale Qualitätskontrolle – Entwurf vom 16.10.2026

Verbindliche Spezifikation: ORIGINALAUFTRAG.txt, unverändert übernommen.
Der Auftrag verlangt unmittelbare eigenständige Implementierung. Zusätzliche
Freigaberunden für diesen darin beschriebenen Prototyp entfallen.

## Architektur
Python 3.12, vorhandene Guardrails AI 0.11.0 und Pydantic 2; keine Installation.
JSON-Regelablage mit unveränderlichen Pflichtregeln im Programm und ergänzenden
Projektregeln. Ein JSON-Katalog enthält vom Betreiber recherchierte Fakten mit
Quellen und lokaler Messung; Eingabedaten können diesen Katalog nicht verändern.
Ein eigener Guardrails-Validator prüft strukturierte Empfehlungen gegen diese
Fakten. Nicht belegte Behauptungen ergeben UNVERIFIED, sichere Verstöße FAIL.

Draft: text, source, task, developer_family (optional), recommendations (Liste
aus model, execution, context_tokens, estimated_vram_gb, evidence_quote).
Nur belegte Katalogeinträge können Modellherkunft/Abliteration bestätigen.
Natürlichsprachige Importe werden nur in eng begrenzten Mustern extrahiert;
unklare Zuordnung bleibt UNVERIFIED und kann vom Critic nicht freigegeben werden.

OllamaCritic.review(draft: dict, requirements: list, facts: dict) -> dict:
status pass/fail/unverified; findings mit requirement_id, severity, description,
evidence, correction. Keine Selbstverifizierung. JSON-Schema und semantische
Konsistenz werden geprüft. Nur numerisches Loopback-HTTP ohne Proxy/Redirects;
explizites vorhandenes Modell/Digest; kein Download. 4096 Kontext, begrenzte
Ausgabe, Timeout, keine automatischen Transport-Retries. Nur eigener Request
keep_alive=0. Kein Entladen fremder Modelle.

Orchestrator: FAIL hat Vorrang, danach ERROR, UNVERIFIED, dann PASS. Ohne Critic
kein vollständiges PASS. Unabhängigkeit wird bei lokaler Entwicklerfamilie
gegen gpt-oss geprüft; ChatGPT-Familie gilt nicht als nachgewiesen unabhängig.
PASS bezeichnet nur die im Bericht genannten Prüfbereiche, keine allgemeine
Faktengarantie. Maximal zwei Korrekturen zusätzlich zum ersten Entwurf.
Mangels eingerichtetem unabhängigem Entwickler wird ein klar als Testgenerator
bezeichneter lokaler Fixture-Korrektor verwendet. Kein gpt-oss-Selbstkorrektor.

Audit: je Lauf lokale JSONL-Datei, UUID, Zeit, Regel-/Faktenhash, Originalentwurf,
alle Prüfungen und Korrekturaufträge. Keine Freigabe ohne erfolgreiche Speicherung.
Keine Export-/Cloudfunktion. Dateien enthalten absichtlich vertraulichen Klartext.

CLI für JSON/Text/Dateiimporte und lokale HTTP-Oberfläche (127.0.0.1). Oberfläche
mit manuellem Einfügen, zufälligem Zugriffstoken, Host/Origin/Größenprüfung,
ohne externe Ressourcen. In eigener Oberfläche getrennte Bereiche Entwurf und
freigegebenes Ergebnis. Keine Kontrolle über interne ChatGPT-Anzeige.

## Abgrenzung
ARGUS und Forge bleiben unverändert. Kein neues Modell, keine Änderung der .venv.
Automatische ChatGPT-DOM-Erfassung wird wegen der geprüften Bedingungen nicht
implementiert. Offizielle Mechanismen werden gesondert quellenbasiert bewertet.

## Abnahme
Die neun vorgegebenen Fälle plus fehlende Fakten, manipulierte Eingaben,
Schemafehler, Timeout, Protokollfehler und lokale HTTP-Grenzen werden getestet.
Ein echter gpt-oss-Aufruf prüft den ursprünglichen Cloudfehler. Ein zweiter
lokaler Aufruf prüft eine nachweislich aus ChatGPT stammende Antwort.
Fixture-Korrekturen und echte Inferenz werden in den Berichten getrennt.

## Ergänzung aus dem realen ChatGPT-Sample
Der Benutzer lieferte inzwischen eine Installationsanleitung mit einem
Guardrails-Codefragment. Der aktuelle Import wurde real geprüft, der Critic
übersah aber die lokal belegte fehlende Methode Guard.from_string. Eine enge
statische AST-Prüfung ergänzt deshalb den bestehenden deterministischen Kern:
abgegrenzte Pythonfragmente, gesicherte Guardrails-Importaliase, bekannte
API-Verfügbarkeit aus dem Betreiberkatalog. Keine Ausführung des Benutzertexts,
keine neue Installation, keine Behauptung vollständiger Pythonprüfung.
Regressionen: echter Originaltext, korrigierter Methodenname, bloße Erwähnung,
Kommentar, überschriebener Alias, fehlende Fakten und unterbundene Seiteneffekte.
Die Rolle als empfohlenes ausführbares Beispiel ist für den unveränderten
Originaltext anhand der positiven Einleitung manuell überprüft und im
Betreiberkatalog mit Texthash und wortgetreuem Zitat gebunden. Ein API-Befund
allein beweist bei beliebigen anderen Texten keinen Verstoß: Negativbeispiele
oder unbestätigte Rollen bleiben UNVERIFIED statt fälschlichem FAIL.
