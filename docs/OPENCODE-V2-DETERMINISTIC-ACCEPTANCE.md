# Guard V2: deterministische Pfade — ACCEPTED

Abnahmeumfang vom 24.10.2026: **Guard V2 für die nachgewiesenen deterministischen
Pfade unter OpenCode 2.1.4 ist ACCEPTED und abgeschlossen.**
Die Teilabnahme gilt ausschließlich für die vorhandenen synthetischen Unitfälle
und nativen gescripteten Stubpfade. **Natürliche Modellläufe und produktiver Betrieb
sind damit nicht abgenommen.** Es ist keine zusätzliche menschliche Zweitabnahme.
Gesamtprojekt weiterhin NOT_ACCEPTED; der historische natürliche Modelllauf behält
seinen eigenen Status.

## Abgeschlossene Kriterien

| Kriterium | Vorhandener Nachweis | Ergebnis |
| --- | --- | --- |
| Nutzerbindung über den tatsächlichen Promise-SDK-Vertrag | Quellenabgleich, Array-/Hüllenregression, ID-/Auftragsbindung in den Guard-Unitfällen | PASS |
| Gültigen Testbeleg annehmen | Nativer gescripteter Positivfall: echter Test Exit 0, EVIDENCE-Quittung, passende Erfolgsaussage unverändert | PASS |
| Falschen Testerfolg zurückweisen | Nativer gescripteter Negativfall: echter Test Exit 1, UNVERIFIED-Quittung, falsche Aussage sichtbar ersetzt | PASS |
| Belegtypen getrennt halten | Zwei Kreuztyp-Unitfälle mit jeweils passender Positivkontrolle | PASS |
| Leeren sichtbaren Abschluss begrenzt zurückweisen | 134/134 Guard-Unitfälle; nativer SSE-Fall nach gültiger Testquittung: statisches 422, zwei Completions insgesamt, null zusätzliche POSTs | PASS |

Die 134 Fälle sind die betroffenen Guard-Suiten, keine 134 isolierten Tests allein
für den ursprünglichen SDK-Fehler. Es gibt zwei native Beleg-/Aussagefälle und
einen späteren nativen Leerabschlussfall. Die Varianten bleiben auf die geprüften
Bindungs-, Ausgabe- und Sprachformen sowie die eingerichtete lokale HTTP-Route begrenzt.

## Bindung an Code und Belege

Verhaltensstand: `7e43a7620f77f973d5b28cce95c018028d149e5a`.
Die beiden ersten nativen Fälle liefen mit `15d7ed3`; der spätere Fall mit `7e43a76`.
Der tatsächlich gelesene Diff der Guardmodule zwischen diesen Ständen enthält nur
die zusätzliche Leerabschlussprüfung nach der Toolcallvalidierung. Die Belegengine
blieb unverändert. Keine erneuten nativen Positiv-/Negativläufe nur für die Teilabnahme.

- `work/opencode-evidence-20261024-stub-corrected/verification.json`:
  `PASS_TWO_NATIVE_STUB_CRITERIA`, beide nativen Beleg-/Aussagefälle.
- `work/opencode-crosskind-20261024/verification.json`: Kreuztypfälle mit Positivkontrollen.
- `work/opencode-empty-response-20261024/verification.json`, `green-combined.tap`:
  134/134, 0 Fehler, 0 übersprungen, Exit 0.
- `work/opencode-empty-native-20261024-corrected/verification.json`:
  `PASS_NATIVE_EMPTY_FINAL_GUARD422_SCOPE`, statischer 422 und gezählte Anfragen.

Die damaligen NOT_ACCEPTED-Gesamtwerte in diesen Belegdateien werden nicht
umgeschrieben. Diese Entscheidung setzt einen ausdrücklich begrenzten neuen
Abnahmeumfang, keine rückwirkend erfolgreiche natürliche Modellprobe.

## Entscheidung zu finish_reason:length

`length` wird nicht als Vollständigkeits- oder Erledigungsbeleg gewertet und
erhält keine zusätzliche Sonderbehandlung im Adapter. Bei vorhandenem Text
werden die erkannten Erfolgsaussagen weiterhin nach den aktuellen Belegen geprüft;
der Abschlussgrund bleibt erhalten. Ohne nutzbaren Text, Refusal oder gültige
Toolcalls greift auch hier die vorhandene Leerabschlussprüfung mit 422.

Bewusste Abdeckungslücke: Es gibt keinen eigenständigen length-Unitfall und keine
native length-Abnahme. Die Einordnung beruht auf dem vorhandenen Quellcode.
Ein zusätzlicher length-Fall ist kein weiteres
Abschlusskriterium dieser Teilabnahme. Der Guard erteilt keine allgemeine Zusage,
dass eine Modellantwort vollständig ist oder ein beliebiger Auftrag erledigt wurde.

## Bewusst getrennte offene Themen und Ende

Die allgemeine Zielakte `work/codex/assistant-goal.json` bleibt insgesamt
NOT_ACCEPTED. Über den abgenommenen Guardumfang hinaus fehlen dort:

- **Anforderungen:** vollständiger, quellengebundener Auftragsvertrag mit Regelzuordnung.
- **Entscheidungen:** allgemeine Ablage bestätigter Entscheidungen mit Geltungsbereich,
  Quelle und nachgewiesener Widerspruchsprüfung.
- **Zurückweisung:** allgemein verbindliche Hostdurchsetzung über die geprüften
  Beleg-, Ausgabe- und Sprachformen hinaus.
- **Korrektur:** nachgewiesene allgemeine Fehlerkorrektur mit erneuter Prüfung im nativen Host.
- **Abschluss:** allgemeine Bindung von Fertigmeldungen an auftragsspezifische Abschlussbelege.

Die produktive Host-/Datenflussabnahme bleibt ebenfalls getrennt. Diese Kriterien
werden durch die Teilabnahme weder erfüllt noch gelöscht. Natürliche Modellqualität
und die historische Ursachenfrage sind nicht Gegenstand dieses Guardabschlusses.

Die Ursachenfrage bleibt ein optionaler separater Diagnosepunkt und wird derzeit
nicht weiterverfolgt. Ein erneutes Auftreten im Alltag kann einen konkreten Anlass
für eine neue Entscheidung geben, startet aber keine Diagnose automatisch. Ein möglicher
einmaliger natürlicher Proxyversuch benötigt eine eigene ausdrückliche Freigabe;
er ist keine Voraussetzung für diesen Abschluss. Seine vorab festgelegten
Ergebnis- und Logregeln stehen im [Leerabschlussvertrag](OPENCODE-EMPTY-RESPONSE-CONTRACT.md).
Eine normale Antwort bedeutet dort Fehler nicht reproduziert, ohne Wiederholung.

Keine weiteren Tests, automatisierten Review-Runden, natürlichen Modellaufrufe,
globalen Aktivierungen oder Veröffentlichungen aus dieser Teilabnahme ableiten.
Für diesen Abschluss wurden nur vorhandene Artefakte und Quellen abgeglichen.
