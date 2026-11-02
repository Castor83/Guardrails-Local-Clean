# DeepEval und LLMCritic: Entscheidung vom 23.10.2026

DeepEval bleibt der vorhandene Bewertungsrahmen. Diese Entscheidung betrifft die
Offline-Fortführung, keine Aktivierung, Installation oder Modellfreigabe.

| Baustein | Fähigkeiten und Vorteil | Nachteil und offene Grenze |
| --- | --- | --- |
| DeepEval | Kriterienbewertung, Prompt Alignment und Task Completion auf Ablaufdaten; vorhandener lokaler Adapter wird weiterverwendet. | Vollständiger Traceadapter fehlt. Der gespeicherte lokale Modellaufruf scheiterte am Backend; Urteilsgüte und native Wirkung sind nicht abgenommen. |
| Hub LLMCritic | Antwortbewertung anhand frei vorgegebener Kriterien und Schwellen über LiteLLM. | Kein belegter zusätzlicher Nutzen für Auftragsbindung, Rechte oder Korrekturbudget. Beide unten geprüften Versionen verlangen eine ältere LiteLLM-Version als der Controller. |

Die Auswahl beruht auf vorhandenem Anschluss und fehlendem belegtem Wechselnutzen,
nicht auf einer nachgewiesenen Genauigkeitsrangliste. Ein Frameworkwechsel mit
demselben fehlerhaften Modellbackend ist keine belegte Backend-Reparatur.

## Aktueller Quellenabgleich

- [DeepEval Task Completion](https://deepeval.com/docs/metrics-task-completion):
  Bewertung des Auftragsabschlusses aus dem vollständigen Trace; kein Beweis,
  dass unser Adapter diesen Trace bereits liefert.
- [Hub LLMCritic](https://guardrailsai.com/hub/validator/guardrails/llm_critic):
  Kriterien, Scores und Schwellen für die erzeugte Antwort, konfigurierter
  LiteLLM-Anbieter. Cloudbeispiele beweisen keine allgemeine Cloudpflicht.
- PyPI-Metadaten für [0.1.0](https://pypi.org/pypi/guardrails-ai-llm-critic/0.1.0/json)
  und [0.2.1a1](https://pypi.org/pypi/guardrails-ai-llm-critic/0.2.1a1/json):
  Python >=3.10,<4; guardrails-ai>=0.4.2; litellm<1.82.6.
  Die Vorabversion wurde am 23.10.2026 direkt per öffentlichem JSON gelesen.
- Controller-Metadaten erneut gelesen: LiteLLM 1.105.1 unter
  `C:\Users\REDACTED_USER\.venv\Lib\site-packages\litellm-1.105.1.dist-info\METADATA`.
  Keine Herabstufung, kein Import und keine Installation durchgeführt.

## Chatverhalten als ausdrückliches Prüfziel

Später sollen neben Antwortinhalten auch folgende Verhaltensfehler geprüft werden:

- Freigegebene Arbeit nach Zwischenfrage oder Chatwechsel unbegründet anhalten.
- Bestätigte Entscheidungen verlieren oder ohne entscheidende neue Belege umwerfen.
- Recherche, Tests oder Chattitel ohne passende tatsächliche Belege behaupten.
- Unnötige Rückfragen stellen oder neue echte Nutzerbeiträge aussperren.
- Eine echte Pause oder einen Widerruf ignorieren.

Dafür werden Originalauftrag, bestätigte Entscheidungen, vollständiger relevanter
Verlauf und tatsächliche Werkzeugbelege benötigt. Eine berechtigte Unsicherheit
ist kein automatisch korrigierbarer Fehler. Ein Score verbessert das Verhalten
erst zusammen mit beleggebundenem Feedback und überprüfter begrenzter Korrektur.
Das ist weder Nachtraining noch ein Auftrag, globale Erinnerungen umzuschreiben.

## Tatsächlicher Stand

Gespeicherte Belege vom 18.10.2026:
`work/quality-stack-20261018/live-prompt-alignment.json` enthält ERROR nach einem
versuchten Call und `native_deepeval_executed=false`.
`ollama-blocker.json` dokumentiert HTTP 500 beim Warm-up und Runner-Exit
0xc0000409; die exakte CUDA-Ursache bleibt unbewiesen. Beide Dateien wurden erneut
gelesen, der Modelllauf wurde nicht wiederholt.

Gesamtstatus bleibt NOT_ACCEPTED. Native Task Completion, allgemeine
Entscheidungsablage, Datenflussisolation und tatsächliche Hostkorrektur bleiben
getrennte offene Kriterien.
