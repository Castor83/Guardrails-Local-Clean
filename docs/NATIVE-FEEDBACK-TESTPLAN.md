# Separater synthetischer Hosttest: prüfbarer Freigabeumfang

Stand 23.10.2026. **Mit Nutzerauftrag „los“ freigegeben. Erster
Vorbereitungsversuch mit ERROR beendet; native Transport-/Korrekturfälle
nicht ausgeführt. Kein automatischer Wiederholungsversuch.**
Einziger angelegter Testchat: `01a16997-5905-72f0-8537-a4a1b3f2bc4e`.
Ergebnis und sichere Zustandskontrolle: `docs/NATIVE-FEEDBACK-TESTERGEBNIS.md`.
Offline-Grundlage: Commit `a282418`, 34 neue gezielte Tests und vollständige
CPU-Vertragssuite mit 435 bestandenen Tests. Belege unter
`work/precheck-feedback-20261023/`; Gesamtstatus weiterhin NOT_ACCEPTED.

Die Zahlenfolge lautet **392 + 9 PreCompact-Tests + 34 Feedbacktests = 435**
(Zwischenstand 401). Gespeicherte Ergebnisse: `work/resume-20261020/full-suite-result.json`
(392), `work/precompact-20261023/suite-result.json` (401) und
`work/precheck-feedback-20261023/full-suite-result.json` (435). Commit `49186fa`
ergänzte neun Testmethoden, `a282418` weitere 34. Für diesen Abgleich keinen Test
wiederholen; keine native Abnahme aus diesen CPU-Zahlen ableiten.

## Benötigte konkrete Freigabe

Genau eine neue lokale Testsitzung im Projekt Guardrails-Local anlegen. Nur
synthetische Aufträge und Texte, kein lokaler Critic, kein NLI-/DeepEval-/Ollama-
Modellaufruf, keine Installation und kein Providerwechsel. Die übliche Codex-
Modellverwendung im neuen Testchat gehört zur Hostprüfung; das ist kein lokaler
Judge-Test. Die geschützten bestehenden Sitzungen und dieser Hauptchat bleiben
außerhalb der Feedbackfreigaben.

Der Test benötigt eine vorübergehende Registrierung des PostToolUse-Handlers
und die gezielte Vertrauensfreigabe genau dieser Definition. In der Projekt-
Betreiberdatei nur die neue Test-ID zu `session_ids` und
`precheck_feedback_session_ids` hinzufügen; keine Workflow-/Aktionsbelegrechte
und `critic_enabled=false` erhalten. Bestehende Hookgruppen, insbesondere die
separat freigegebene PreCompact-Sicherung, unverändert erhalten.

## Ablauf und Kriterien

1. **Zustand sichern und Transport erfassen:** Aktuelle Hook-/Betreiber-/Trust-
   Zustände lokal sichern und per unterstützter lesender Verwaltung prüfen.
   SHA256 der relevanten Dateien und strukturelle Fingerprints der unverändert
   zu erhaltenden Felder als Ausgangsaufnahme T0 speichern (siehe Rückweg).
   Zuerst mit einem nur beobachtenden Handler ein
   synthetisches PostToolUse-Ereignis eines direkten Vorprüfaufrufs erfassen.
   Seine Erfassung ist auf die Testsitzung und genau den unten festgelegten
   synthetischen Kontrollfall begrenzt; vor jedem Speichern entsprechend filtern.
   Kanonischen Werkzeugnamen, Argumente, Turn-ID und genaue Ergebnisform abgleichen.
   Unbekannte Form: UNVERIFIED, Lauf beenden, kein blindes Einschalten des Feedbacks.
2. **Ein belegter Fehler, dann PASS:** Längenauftrag mit eindeutig zu langem
   synthetischem Entwurf. Echte lokale Formprüfung FAIL; genau ein zugehöriger
   Zusatzkontext im gleichen Task/Turn; korrigierter Entwurf besteht die Formprüfung.
   Inhalt und IDs müssen im Ereignislog zu den lokalen Belegen passen.
3. **Budget:** Der feste Testauftrag verlangt für einen neuen synthetischen
   Längenauftrag mit höchstens drei Zeichen nacheinander genau die drei lokalen
   Vorprüfungsentwürfe `LANG`, `LANGER`, `NOCHLANGER`. Nach dem ersten und zweiten
   tatsächlich empfangenen Feedback jeweils den nächsten festen Entwurf vorprüfen;
   keine Ersatzentwürfe, kein künstlicher UserPromptSubmit und kein Budgetreset.
   **PASS** nur, wenn derselbe Task/Turn drei verschiedene zu lange Entwürfe
   nachweislich geprüft hat, genau zwei Korrekturhinweise tatsächlich beobachtet
   wurden und der dritte Entwurf ESCALATED ohne weiteren Korrekturhinweis endet.
   Korrigiert das Modell vorzeitig, fehlen Entwürfe oder tritt der beabsichtigte
   Fehlerfall nicht ein, lautet der Status **NICHT_AUSGELÖST**, niemals PASS.
   Das beweist keine Budgetverletzung, lässt die Budgetabnahme aber UNVERIFIED.
   Keine automatische Wiederholung, um den Fall doch noch zu erzwingen.
4. **Fehler und Gesprächserreichbarkeit:** Fehlende synthetische Antwortdatei
   erzeugt ERROR ohne automatisches Wiederholen. Ein anschließender echter
   im Testplan ausdrücklich beauftragter neuer Nutzerbeitrag im Testchat wird
   angenommen und erhält eine neue Taskbindung. Der erwartete Fehler beendet
   den alten automatischen Taskablauf; Feedback wird nicht in einen neuen
   Nutzerbeitrag umgewandelt.
   Keine alte Fortsetzung sperrt diesen Beitrag aus.
5. **Nicht freigegebene Sitzung:** In der aktuellen Hauptsitzung, deren ID in
   keiner der beiden Freigabelisten steht und auch nicht hinzugefügt wird, einen
   harmlosen Werkzeugaufruf mit festem synthetischem Marker beobachten. Genau
   dieses native Ereignis anhand Sitzung, Turn und Werkzeugaufruf-ID mit dem
   tatsächlichen Handlerergebnis verbinden. Erwartet: leere Protokollantwort `{}`,
   kein `additionalContext`, keine `systemMessage`, keine Entscheidung oder
   Fortsetzungsanweisung, kein Prüferaufruf und keine neue Task-/Ledgerdatei.
   Der Beobachter darf für diesen Kontrollfall nur die vorgesehenen synthetischen
   Metadaten (Sitzung/Turn/Werkzeug-ID, fester Marker) und das zugehörige Ergebnis
   des geprüften Handlers erfassen; andere private Ereignisfelder oder
   Sitzungsausgaben nicht mitprotokollieren.
   Die Kontroll-ID erhält keine Prüf- oder Feedbackrechte. Es entsteht kein zweiter
   Testchat, und keine fremden Chats werden angeschrieben. Fehlende Beobachtbarkeit
   ist UNVERIFIED; Listeninhalt oder ein lokal simuliertes Ereignis allein sind
   kein PASS für die native Sitzungsbegrenzung.
6. **Rückweg mit zweiter Kontrolle:** Unmittelbar vor Rückbau dieselben Datei-
   hashes und geschützten strukturellen Fingerprints als T1 speichern, nach
   Rückbau als T2 erneut erfassen. Betroffen sind mindestens `hooks.json`, die
   Projekt-Betreiberdatei, der tatsächlich verwendete Trustspeicher und eigene
   vorübergehende Handlerdateien; bereits bestehende Handler und Trustwerte mitbinden.
   Nicht vorhandene Dateien bei T0/T1/T2 ausdrücklich als ABSENT erfassen; SHA256
   nur für vorhandene Dateien. Neu angelegte eigene Dateien müssen nach Rückbau
   wieder ABSENT sein. Bytegleichheit gilt für ursprünglich vorhandene Dateien.
   Zuerst die Testfreigabe entfernen, dann nur die eigene vorübergehende Definition
   samt eigener neuer Trustkennung entfernen beziehungsweise vorherige eigene
   Werte wiederherstellen. Vor jedem Schreibzugriff den erwarteten aktuellen Hash
   beziehungsweise die Konfigurationsversion nochmals prüfen.

   Ohne gleichzeitige fremde Änderungen müssen die wiederhergestellten
   Konfigurationsdateien bei T2 bytegleich zu T0 sein. Bei zwischenzeitlichen
   Fremdänderungen ist pauschales Backup-Restore ausgeschlossen: fremde Änderungen
   aus T1 müssen bei T2 strukturell erhalten sein; ausschließlich die eigenen
   Teständerungen dürfen verschwinden. Vollständige Hashunterschiede und zulässige
   eigene Felddifferenzen nachvollziehbar protokollieren. Bei nicht sicher
   auflösbarem Konflikt keinen überschreibenden Rückbau erzwingen; Ergebnis offen
   beziehungsweise ERROR melden, keine Rückweg-Abnahme behaupten.
   Hashvergleiche sind Prüfnachweise, keine atomare Sperre gegen fremde Schreiber.

   Abschließend sowohl tatsächlichen deaktivierten Hostzustand als auch T0/T1/T2-
   Vergleiche kontrollieren. **Rückweg PASS** erst bei nachgewiesen entfernter
   Testfreigabe/-definition, korrekt zurückgesetztem eigenem Trustzustand und
   erhaltenen fremden Werten. Ein bloßer Abschalttext oder Dateilistenvergleich reicht nicht.

Alle Ergebnisse lokal mit vollständigen synthetischen Testsitzungsereignissen, Beleg-IDs,
Prüfberichten, Definitionen/Hashes und beobachteter Modellreaktion dokumentieren.
Für den Hauptchat gilt ausschließlich der begrenzte Kontrollbeleg aus Fall 5.
Ein unerwarteter technischer ERROR beendet den betroffenen Testfall; kein
automatischer Retry. Der geplante Rückbau bleibt auch nach Abbruch erforderlich.
Der ausdrücklich erwartete ERROR in Fall 4 ist gesondert zu kennzeichnen und
erlaubt nur den bereits geplanten neuen Nutzerbeitrag, keine Wiederholung des alten Tasks.
Falls Vertrauen oder unterstützte Ereigniserfassung fehlen, den konkreten Blocker
mit Beleg melden und nichts umgehen. Kein Produktivtest mit privaten Nutzerdaten.

Jeden Pflichtfall einzeln mit PASS, FAIL, ERROR, UNVERIFIED oder
NICHT_AUSGELÖST ausweisen. Solange ein Pflichtfall nicht ausgelöst oder nicht
beobachtbar war, ist die gesamte native Abnahme **nicht bestanden** und bleibt
UNVERIFIED. Tatsächliche FAIL- oder unerwartete ERROR-Befunde behalten Vorrang;
erfolgreiche Teilbelege werden nicht nachträglich umgedeutet.

## Getrennte Schlussfolgerungen

Der erfolgreiche Test würde nur den beschriebenen lokalen Hostpfad belegen.
Er beweist keine allgemeine Urteilsgüte, Pflichtvorprüfung, Voranzeigesperre,
adversariale Windows-Isolation oder vollständige Chatverhaltensverbesserung.
Produktive Aktivierung bleibt auch nach Erfolg eine eigene ausdrückliche Freigabe.
Der echte Traceadapter, allgemeine Entscheidungsablage und technische
Datenflussisolation bleiben eigene offene Projektkriterien.
