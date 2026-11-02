# Kooperativer unittest-Nachweis

`src/guardrails_local/test_runner.py` führt die feste unittest-Discovery aus und
schreibt deren Resultat getrennt von stdout/stderr atomar in eine neue JSON-Datei.
Textzeilen wie `Ran 128 tests` und Ausgaben aus `atexit` liefern keine Testanzahl.

Inneres Schema 1: `completed`, gebundene `invocation_id`, `tests_run`,
`test_count`, `failures`, `errors`, `skipped`, `expected_failures`,
`unexpected_successes`, `evidence_scope="cooperative-unit-tests"`,
`tamper_resistant=false`. `test_count=tests_run-skipped`; erwartete Fehlschläge
werden getrennt ausgewiesen. Alle Zähler sind nichtnegative ganze Zahlen.

Hostschema 2 bindet Ergebnis- und Logdatei, deren Hashes, Runnerdatei, Aufruf-ID,
Auftrag, Policy und Dateistand vor/nach dem Lauf. Ein kooperativer Erfolg
erfordert ein vollständiges gültiges Ergebnis, Exit 0, keine Fehler,
Fehlschläge oder unerwarteten Erfolge und die Mindestzahl ohne Skips.
Alte textbasierte Hostberichte liefern keinen gültigen Abschlussbeleg.

Eine widersprüchliche Meldung `Arbeitsstatus: OFFEN` mit erkannter positiver
Abschlussbehauptung bleibt `UNVERIFIED`. Die Sprachprüfung deckt nur die
implementierten deutschen Muster ab; Zitate, Beispiele und Verneinungen sind
keine Ausführungsbehauptungen.

Der Runner und Tests laufen unter demselben Windows-Benutzer. Beliebiger Testcode
kann Dateien, Prozesszustand und Python-Objekte manipulieren. JSON und Hashes
sind keine getrennte Vertrauensdomäne. Der Bericht erklärt ausdrücklich
`general_completion_verified=false`; er ist keine allgemeine Projektabnahme,
keine adversariale Beleggarantie und keine Sperre vor der Antwortanzeige.
