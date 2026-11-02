# Auswahl der offiziellen Guardrails-Bausteine

Am 18.10.2026 wurden die offizielle OSS-Homepage, der Validator Hub und die
zugehörigen offiziellen Beschreibungen erneut geprüft. Die Homepage verweist
für wiederverwendbare Prüfbausteine auf den Hub. Die aktuelle Einrichtungsseite
nennt öffentliche PyPI-Pakete ohne benötigten Hub-Schlüssel. Ein neuer Account
oder eine neue Cloudverbindung ist für diese lokalen Bausteine unnötig.

Quellen: [Guardrails OSS](https://guardrailsai.com/guardrailsoss),
[Validator Hub](https://guardrailsai.com/hub),
[aktuelle Einrichtung](https://guardrailsai.com/hub/keys).

Für den beauftragten lokalen Stack bleibt diese konkrete Auswahl bestehen:

| Baustein | Einsatz im Projekt | Nachweisgrenze |
| --- | --- | --- |
| ValidLength und ValidURL | Bereits vorhandene originale Hub-Module 0.1.0 aus geprüften Wheels, geladen über `conversation_profiles.py`; Herkunft und Hashes in `work/profile-components/manifest.json`. | Länge und URL-Syntax, keine Wahrheit oder tatsächliche Recherche. |
| ProvenanceNLI | Vorhandener offizieller Validator in der getrennten Eval-Laufzeit; `provenance_nli.py` bindet vollständige explizite Quelle und Antwort an das vorhandene lokale mehrsprachige Modell. | Quellenbezug benötigt tatsächlich bereitgestellten Kontext; allgemeine Wahrheit und Werkzeugausführung werden damit nicht belegt. Installation, vorhandenes Modell und echte Inferenz sind getrennte Nachweise. |
| Guard und Validator | Bereits vorhandenes Guardrails AI 0.11.0 führt die projektspezifische Belegprüfung und die Zusammenführung von Hostregeln und DeepEval-Urteil aus. | Welche Regeln gelten und ob der Host Antworten rechtzeitig abfängt, muss die eigene Einbindung festlegen. |

Offizielle Details: [ValidLength](https://guardrailsai.com/hub/validator/guardrails/valid_length),
[ValidURL](https://guardrailsai.com/hub/validator/guardrails/valid_url),
[ProvenanceNLI](https://github.com/guardrails-ai/guardrails-hub-monorepo/blob/main/provenance_nli/py/README.md).

Die zusätzlich geprüfte Hub-Komponente
[LLM Critic](https://guardrailsai.com/hub/validator/guardrails/llm_critic)
bewertet Antworten anhand vorgegebener Kriterien und verwendet LiteLLM.
Ihre Aufgabe ist im beauftragten Stack bereits durch DeepEval mit festem
lokalem Modell und festem Aufrufbudget abgedeckt. Ein zweiter semantischer
Prüfer würde weitere Modellaufrufe verursachen. Daher wird dafür kein weiteres
Paket installiert und kein Anbieter aus dem offiziellen Cloudbeispiel übernommen.

Weitere geprüfte stabile Hub-Pakete würden zusätzlich Versionskonflikte im
Controller erzeugen: `ResponsivenessCheck` 0.0.3 verlangt LiteLLM bis 1.82.6,
`ResponseEvaluator` 0.1.0 verlangt LiteLLM unter 1.82.6. Dort ist bereits
1.105.1 vorhanden. Die stabilen Paketmetadaten sind die Grundlage dieser
Feststellung; neuere Alpha-Quellen im Monorepo sind damit nicht gleichgesetzt.
Quellen: [ResponsivenessCheck-Metadaten](https://pypi.org/pypi/guardrails-ai-responsiveness-check/0.0.3/json),
[ResponseEvaluator-Metadaten](https://pypi.org/pypi/guardrails-ai-response-evaluator/0.1.0/json).

Die Entscheidung gilt für den jetzigen Auftrag. Weitere Hub-Pakete werden
erst dann benötigt, wenn eine konkrete ungedeckte Anforderung hinzukommt.
Die Herkunft einer tatsächlich ausgeführten Chatsuche muss weiterhin durch
den Host belegt werden; ein sprachlicher Validator kann sie nicht erzeugen.

Bedienung, Regressionen und aktueller Prüfstand: `QUALITY-STACK.md`.
