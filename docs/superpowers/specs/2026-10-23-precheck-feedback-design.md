# Gebundenes Vorprüfungsfeedback, Offline-Entwurf

Stand 23.10.2026. Grundlage: `work/resume-20261020/STAND-UND-VORGEHEN.md` und
die ausdrücklich beauftragte direkte Offline-Fortsetzung. Produktivfreigabe fehlt.

## Ziel und gewählter Ansatz

Belegte korrigierbare Hostverstöße sollen nach einer expliziten Vorprüfung im
bereits laufenden Turn an das Modell zurückgegeben werden können. Der gespeicherte
Originalauftrag, bestehende Rechte und höchstens zwei Korrekturen bleiben bindend.
Normale Nutzerkommunikation und ehrliche Unsicherheit müssen erreichbar bleiben.

Gewählt: vorhandene Vorprüfung plus synchrones PostToolUse-Feedback mit dauerhaftem
Taskzustand. Das vermeidet einen künstlichen Benutzerbeitrag. Stop bleibt die
vorhandene Nachkontrolle ohne Reinjektion. Ein zusätzlicher LLMCritic ersetzt
weder Herkunftsbindung noch Zustandsverwaltung; ein Stop-/Textreplay wurde wegen
unklarer Herkunft verworfen. DeepEval bleibt separat gemäß `docs/EVAL-AUSWAHL.md`.

## Umfang und Grenzen

- Standardmäßig abgeschaltet: neue optionale Freigabeliste
  `precheck_feedback_session_ids`, eine eindeutige Teilmenge von `session_ids`.
  Fehlendes Feld bedeutet leere Liste. Keine bestehende Konfiguration ändern.
- Keine Modelle, Installationen, Downloads, Providerwechsel, Hookregistrierung,
  Vertrauensänderung, globalen Memories oder fremden Referenzquellen.
- Bestehende Sitzungsliste und `critic_enabled=false` erhalten.
- Vorbereitete Logik, Offline-Vertragstests und native Hostabnahme getrennt halten.
- Keine Garantie einer Pflichtvorprüfung, Voranzeigesperre, Feedbackbefolgung oder
  Isolation gegenüber demselben Windows-Benutzer. Kein Cloud-Fallback.

## Auftrags- und Rechtebindung

Der bestehende Task wird ausschließlich aus dem aktiven gespeicherten
UserPromptSubmit-Zustand übernommen: Sitzungs-UUID, Task-UUID, nichtleere Turn-UUID,
exakte Originalauftragsdatei und deren Inhaltshash, Prüfumfang, Profilregeln.
Für den neuen Anschluss sind explizites passendes `--turn-id` und die genaue
gespeicherte `--task-file` Pflicht. Textgleichheit allein genügt nicht.

Eine gewöhnliche neue Nutzernachricht erzeugt nach bestehendem Vertrag einen neuen
Task und archiviert den alten. Feedbacktext wird nie als Herkunftsmarker benutzt.
Ein semantischer Gesamtauftrag über mehrere echte Nutzerturns ist damit noch nicht
implementiert. Ein vom Host gewechselter Feedback-Turn bleibt UNVERIFIED.

Regeln, Prüfcode und aktuell erlaubte Konfiguration werden durch einen lokalen
Fingerprint gebunden. Vor und nach einer Prüfung sowie vor Feedbackverbrauch
erneut prüfen. Veränderung oder Widerruf schließt den alten automatischen Ablauf;
kein stilles Neubinden und kein neues Budget. Diese Hashbindung schützt den
kooperativen Ablauf, nicht vor Manipulation durch denselben Benutzerprozess.

## Dauerhafter Zustand und Beleg

Neue fokussierte Komponente `precheck_feedback.py`, Aufruf nur unter vorhandener
Sitzungssperre. Pro Task `precheck-feedback.json`, atomar geschrieben, begrenzt.
Maximal drei verschiedene feedbackverwaltete Vorprüfungen und zwei reservierte
Korrekturen. Stop bleibt eine getrennte Nachkontrolle ohne Korrekturfeedback;
keine globale Modellaufrufgrenze über Stop und alle manuellen Pipelines behaupten. Keine
automatische Rückerstattung, Löschung oder Migration eines beschädigten Zustands.

Vor dem Prüfen eine Reservierung speichern. Ein nach Absturz ausstehender Eintrag
endet ohne erneuten Prüferaufruf mit ERROR. Jede abgeschlossene Prüfung erhält eine
zufällige Beleg-ID. Separater lokaler Bericht und Ledger binden Antwortdatei,
Antwortinhalt, Originalauftrag, Turn, Fingerprint, Ergebnis und Ergebnishash.
CLI-Ausgabe enthält diese Beleg-ID. Gleicher Entwurf verwendet denselben Beleg.
Der Entwurfschlüssel umfasst Task/Turn, Antwortinhalt und Fingerprint. Der erste
kanonische Antwortpfad bleibt gebunden; eine andere Datei erzeugt keinen weiteren
Beleg für denselben Text. Wiederholung liefert den gespeicherten Bericht exakt.

Nur ein tatsächlich gespeicherter Bericht mit endgültigem FAIL und einem
nichtleeren Hostbefund aus Profil-, Aktions-, deterministischer oder mechanischer
Workflowprüfung ist korrigierbar. Critic-only FAIL und SKIPPED sind keine
Korrekturgrundlage. Ein technischer Teilfehler überstimmt die Korrekturbarkeit.
ERROR/UNVERIFIED/ESCALATED schließen den automatischen Ablauf und lösen keine
erneute Prüfung oder Modellkorrektur aus. PASS beendet diesen Ablauf ebenfalls.

## PostToolUse-Verbrauch

Nur der exakt erkannte direkte Vorprüfungsaufruf wird betrachtet: kanonischer
Hook-Werkzeugname Bash, festgelegter Interpreter und Wrapper, genau die Optionen
`--precheck`, `--session-id`, `--task-file`, `--turn-id`. Keine zusammengesetzten
Shellbefehle, fremden Interpreter, doppelten Optionen oder Zusatzargumente.
Die bestehende Workflow-Allowlist muss denselben Aufruf zulassen.

Erste enge Ergebnisform: `tool_response` als Objekt mit `stdout` (ein einziges
JSON-Prüfergebnis) und `exit_code` (zum Ergebnis passender ganzzahliger CLI-Code).
Nicht unterstützte Formen liefern kein Korrekturfeedback. Diese Form ist ein
Offline-Vertrag; tatsächliche native Hostform und Hosttransport sind UNVERIFIED.
Status/Exitcode oder kopierter Text allein reichen nie: gespeicherte Beleg-ID,
vollständiger Bericht, Fingerprint und noch identische Antwortdatei müssen stimmen.
Fremde Werkzeugereignisse bleiben wirkungslos.

Vor Rückgabe des Feedbacks Beleg und Tool-use-ID dauerhaft verbrauchen und
Korrekturzähler erhöhen. Doppelte Ereignisse erzeugen kein erneutes Feedback,
auch mit anderer Tool-ID nicht für denselben Beleg. Geändertes Ergebnis unter
gleicher ID oder widersprüchliche Belegbindung schließt den Ablauf.
Nach Crash zwischen Verbrauch und Rückgabe kein erneutes Senden; konservativ
höchstens einmal pro Beleg, keine behauptete atomare Zustellung.
Prüfungen nach einer FAIL-Prüfung müssen deren Feedbackverbrauch abwarten.

Feedback verwendet statischen begrenzten Text, IDs, Hostbefundbereiche und den
gebundenen lokalen Auditpfad. Kein ungeprüfter Critictext als Handlungsanweisung.
Es erteilt keine Werkzeugrechte und ist kein neuer Nutzerauftrag.
Nur `hookSpecificOutput.additionalContext`, kein künstlicher Prompt, kein
`decision:block` und kein `continue:false` im neuen PostToolUse-Erfolgsweg.

## Gezielte Offline-Abnahme

Nachweisen: zwei Korrekturen und dritter FAIL eskaliert; echte Länge-FAIL/PASS;
Duplikate mit gleicher/fremder Tool-ID; geänderte Antwort/Regeln/Rechte; falsche
Sitzung/Task/Turn und gleichlautender abgelöster Auftrag; falscher Vorprüfaufruf;
stdout ohne Beleg; Critic-only FAIL; ERROR/UNVERIFIED/SKIPPED; ausstehende
Reservierung nach Neustart; konkurrierende Verbraucher unter Sitzungssperre;
kopierter Feedbacktext als normaler neuer Nutzerbeitrag; Default bleibt inaktiv.

Erst danach getrennt freizugebender nativer synthetischer Versuch mit Log und
Rückweg. Produktivaktivierung benötigt dessen Erfolg und konkrete Nutzerfreigabe.
Allgemeine Verhaltenskriterien und echter Traceadapter bleiben eigene offene Arbeit.

## Umsetzungspräzisierungen nach unabhängigem Entwurfscheck

- Nur für Feedbacksitzungen den Kontextaufruf um das passende `--turn-id` ergänzen.
- Feedback- und Aktionsbelegfreigabe unabhängig prüfen; keine impliziten Rechte.
- Fingerprint: aktive Task-/Turnbindung, Profilregeln, Quellhashes der Prüflogik,
  vorhandene Regel-/Katalog-/Modellkonfiguration, Workflow-Policy und aktuelle
  Betreiberkonfiguration. Tatsächlich referenzierte Profilkomponenten mitbinden.
- Erkannter Vorprüfaufruf mit unpassender Ausgabe schließt den Ablauf lokal mit
  UNVERIFIED; fremde Werkzeuge/Kommandos bleiben ohne Wirkung.
- Fehler lokal erhalten und den Feedbackablauf schließen, aber im neuen
  PostToolUse-Zweig niemals in den allgemeinen `continue:false`-Fehlerfang fallen.

Quelle für den dokumentierten Kontextweg:
[OpenAI Hooks / PostToolUse](https://learn.chatgpt.com/docs/hooks#posttooluse),
am 23.10.2026 gelesen. Dokumentation ist kein Nachweis des lokalen Hostdurchlaufs.
