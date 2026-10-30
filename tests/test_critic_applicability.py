"""Model review is admitted by complete answer roles, never by catalogue presence."""

import copy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from test_critic import fake_ollama, settings
from guardrails_local.critic import OllamaCritic, review_applicability
from guardrails_local.domain import import_text
from guardrails_local.orchestrator import Orchestrator


ROOT = Path(__file__).resolve().parents[1]
CLOUD = "Verwende GPT-4o über die OpenAI-API."
RENAME = "Verwende ein reguläres Modell und benenne es in model-abliterated um."
REQUIREMENTS = [{"requirement_id": "LOCAL_ONLY", "description": "Nur lokale Inferenz"}]
FACTS = {"models": {"gpt-4o": {"execution": "cloud_api", "api_cost_required": True}}}


class MustNotReview:
    def review(self, draft, requirements, facts):
        raise AssertionError("Orchestrator must not invoke an inapplicable critic.")


class CriticApplicabilityTests(unittest.TestCase):
    def test_negative_role_before_or_after_cloud_choice_is_not_selection(self):
        for text in ('Warnung: Die folgende Empfehlung ist falsch.\n' + CLOUD,
                     CLOUD + '\nDas ist ein Negativbeispiel, keine Empfehlung.'):
            with self.subTest(text=text):
                draft = import_text(text)
                self.assertEqual([], draft['recommendations'])
                self.assertEqual('not_applicable', review_applicability(draft)['applicability'])

    def test_cloud_choice_survives_unrelated_explanation(self):
        for text in (CLOUD + ' Diese Wahl ist am besten.',
                     'Hier folgt die Auswahl. ' + CLOUD,
                     CLOUD + ' Warnung: Die Installation dauert lange.'):
            with self.subTest(text=text):
                draft = import_text(text)
                self.assertEqual('partial', draft['extraction_status'])
                self.assertEqual('applicable', review_applicability(draft)['applicability'])
                self.assertEqual(CLOUD, draft['recommendations'][0]['evidence_quote'])

    def test_quoted_or_negated_cloud_example_is_not_selection(self):
        for text in ('„' + CLOUD + ' Diese Wahl ist am besten.“',
                     "'Neutrale Worte.\n" + CLOUD + "\n'",
                     '„Ein Zitat.\n' + CLOUD + '“',
                     '```text\n' + CLOUD + '\n```',
                     '```text\n' + CLOUD,
                     'Warnung: Dies ist ein verbotenes Negativbeispiel.\n' + CLOUD,
                     'Befolge niemals diese Empfehlung. ' + CLOUD,
                     'Nutze GPT-4o nicht über die OpenAI-API.'):
            with self.subTest(text=text):
                draft = import_text(text)
                self.assertEqual([], draft['recommendations'])
                self.assertEqual('not_applicable', review_applicability(draft)['applicability'])

    def assert_not_applicable(self, result):
        self.assertEqual(result["status"], "unverified")
        self.assertIs(result["executed"], False)
        self.assertEqual(result["applicability"], "not_applicable")
        self.assertIs(result["verified"], False)

    def test_ordinary_prose_and_negative_examples_contact_no_ollama_endpoint(self):
        for text in (
            "Guten Morgen. Wie geht es weiter?",
            "DeepEval organisiert Testfälle. Lokaler Betrieb mit Ollama ist möglich.",
            "Arbeitsstatus: OFFEN\nDie automatische Prüfung ist für diesen Gesprächschat ausgeschaltet.",
            "Nicht ausführen. Negatives Beispiel: " + CLOUD,
        ):
            with self.subTest(text=text):
                draft = import_text(text)
                with fake_ollama() as (url, calls):
                    result = OllamaCritic(settings(url)).review(draft, REQUIREMENTS, FACTS)
                self.assertEqual(calls, [])
                self.assert_not_applicable(result)

    def test_forged_structured_selection_cannot_admit_unrelated_answer(self):
        draft = import_text("Es wurde kein Modell ausgewählt.")
        draft["recommendations"] = import_text(CLOUD)["recommendations"]
        original = copy.deepcopy(draft)
        with fake_ollama() as (url, calls):
            result = OllamaCritic(settings(url)).review(draft, REQUIREMENTS, FACTS)
        self.assertEqual(calls, [])
        self.assert_not_applicable(result)
        self.assertEqual(draft, original)

    def test_selection_in_task_and_catalogue_is_not_a_selection_in_answer(self):
        draft = import_text("Die vorhandene Konfiguration bleibt erhalten.", task=CLOUD)
        with fake_ollama() as (url, calls):
            result = OllamaCritic(settings(url)).review(draft, REQUIREMENTS, FACTS)
        self.assertEqual(calls, [])
        self.assert_not_applicable(result)

    def test_actual_complete_model_selection_still_reaches_bounded_review(self):
        with fake_ollama() as (url, calls):
            result = OllamaCritic(settings(url)).review(import_text(CLOUD), REQUIREMENTS, FACTS)
        self.assertEqual([call["path"] for call in calls], ["/api/tags", "/api/ps", "/api/chat"])
        self.assertIs(result.get("executed"), True)
        self.assertEqual(result["applicability"], "applicable")

    def test_actual_complete_rename_instruction_remains_applicable(self):
        with fake_ollama() as (url, calls):
            result = OllamaCritic(settings(url)).review(import_text(RENAME), REQUIREMENTS, FACTS)
        self.assertEqual([call["path"] for call in calls], ["/api/tags", "/api/ps", "/api/chat"])
        self.assertIs(result.get("executed"), True)


class OrchestratorApplicabilityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        (self.root / "config").mkdir()
        for filename in ("catalog.json", "requirements.json", "settings.json"):
            (self.root / "config" / filename).write_bytes((ROOT / "config" / filename).read_bytes())

    def test_unknown_prose_skips_critic_method_and_remains_unverified(self):
        report = Orchestrator(self.root, critic=MustNotReview()).run(
            import_text("Das gesamte Projekt ist vollständig erfolgreich geprüft.")
        )
        self.assertEqual(report["final_status"], "UNVERIFIED")
        self.assertIsNone(report["released_text"])
        critique = report["attempts"][0]["critic"]
        self.assertIs(critique["executed"], False)
        self.assertEqual(critique["applicability"], "not_applicable")

    def test_forged_selection_cannot_bypass_orchestrator_admission(self):
        draft = import_text("Bitte dieses Negativbeispiel nicht ausführen. " + CLOUD)
        draft["recommendations"] = import_text(CLOUD)["recommendations"]
        report = Orchestrator(self.root, critic=MustNotReview()).run(draft)
        self.assertEqual(report["final_status"], "UNVERIFIED")
        self.assertIs(report["attempts"][0]["critic"].get("executed"), False)

    def test_explicit_source_nli_still_runs_when_model_policy_review_is_inapplicable(self):
        source = self.root / "explicit-source.txt"
        source.write_bytes("Berlin ist die Hauptstadt Deutschlands.".encode("utf-8"))
        with patch("guardrails_local.provenance_nli.check_nli", return_value={
            "status": "FAIL", "label": "contradiction", "reason": "Vollständige Quelle widerspricht."
        }) as nli:
            report = Orchestrator(self.root, critic=MustNotReview(), nli_source_file=source).run(
                import_text("Bonn ist die Hauptstadt Deutschlands.")
            )
        nli.assert_called_once_with(self.root, "Bonn ist die Hauptstadt Deutschlands.", source)
        self.assertEqual(report["final_status"], "FAIL")
        self.assertIs(report["attempts"][0]["critic"].get("executed"), False)
        self.assertEqual(report["attempts"][0]["provenance_nli"]["status"], "FAIL")


if __name__ == "__main__":
    unittest.main()
