"""Evidence binding through the actual bounded HTTP critic; no Ollama model."""

import copy
import unittest

from test_critic import envelope, fake_ollama, settings
from guardrails_local.critic import OllamaCritic, _bind_evidence
from guardrails_local.domain import import_text


REQUIREMENTS = [
    {"requirement_id": requirement_id, "description": "Belegten Verstoß prüfen"}
    for requirement_id in ("LOCAL_ONLY", "NO_PAID_API", "ABLITERATED", "HARDWARE", "EVIDENCE")
]
FACTS = {
    "models": {
        "gpt-4o": {
            "execution": "cloud_api", "api_cost_required": True,
            "abliterated_verified": False,
        }
    }
}
CLOUD_QUOTE = "Verwende GPT-4o über die OpenAI-API."


def finding(requirement_id="LOCAL_ONLY", evidence=CLOUD_QUOTE):
    return {
        "requirement_id": requirement_id, "severity": "critical",
        "description": "Behaupteter Verstoß", "evidence": evidence,
        "correction": "Nur einen belegten Verstoß korrigieren",
    }


class CriticEvidenceBindingTests(unittest.TestCase):
    def test_explicit_negative_role_cannot_bind_a_model_violation(self):
        for text in ('Warnung: Die folgende Empfehlung ist falsch.\n' + CLOUD_QUOTE,
                     CLOUD_QUOTE + '\nDas ist ein Negativbeispiel, keine Empfehlung.'):
            result = self.bind_without_inference(import_text(text), dict(status='fail', findings=[finding()]))
            self.assertEqual('unverified', result['status'])
            self.assert_binding(result, [False])

    def test_partial_choice_preserves_exact_critic_quote_binding(self):
        draft = import_text(CLOUD_QUOTE + ' Diese Wahl ist am besten.')
        result = self.bind_without_inference(draft, dict(status='fail', findings=[finding()]))
        self.assertEqual('fail', result['status'])
        self.assert_binding(result, [True])

    def bind_without_inference(self, draft, raw_response):
        # These out-of-domain responses must never be generated automatically.
        # Exercise the final evidence barrier directly with hostile raw input.
        original = copy.deepcopy((draft, raw_response))
        status, findings, binding = _bind_evidence(raw_response, draft)
        self.assertEqual(original, (draft, raw_response))
        return dict(status=status, findings=findings, evidence_binding=binding,
                    response=raw_response)

    def review(self, draft, raw_response):
        original = copy.deepcopy((draft, REQUIREMENTS, FACTS, raw_response))
        with fake_ollama({"/api/chat": envelope(raw_response)}) as (url, calls):
            result = OllamaCritic(settings(url)).review(draft, REQUIREMENTS, FACTS)
        self.assertEqual(original, (draft, REQUIREMENTS, FACTS, raw_response))
        self.assertEqual(["/api/tags", "/api/ps", "/api/chat"], [call["path"] for call in calls])
        request = calls[-1]["body"]
        self.assertEqual({"num_ctx": 4096, "num_predict": 1200, "temperature": 0}, request["options"])
        self.assertEqual(0, request["keep_alive"])
        self.assertIs(False, result["verified"])
        self.assertEqual(raw_response, result["response"])
        return result

    def assert_binding(self, result, expected):
        binding = result["evidence_binding"]
        self.assertIn("mechan", binding["scope"].lower())
        self.assertEqual(len(expected), len(binding["checks"]))
        for index, (check, bound) in enumerate(zip(binding["checks"], expected)):
            self.assertEqual(index, check["finding_index"])
            self.assertIs(bound, check["bound"])
            self.assertIsInstance(check["reason"], str)
            self.assertTrue(check["reason"].strip())

    def test_catalogue_only_allegations_are_unverified_and_raw_fail_is_preserved(self):
        draft = import_text("DeepEval organisiert Testfälle. Lokaler Betrieb mit Ollama ist möglich.")
        raw = {"status": "fail", "findings": [
            finding(evidence='Im Fakten-Block steht gpt-4o mit execution="cloud_api".'),
            finding("NO_PAID_API", "Im Fakten-Block ist gpt-4o als kostenpflichtig gelistet."),
        ]}
        result = self.bind_without_inference(draft, raw)
        self.assertEqual("unverified", result["status"])
        self.assertEqual("fail", result["response"]["status"])
        self.assert_binding(result, [False, False])

    def test_quote_in_original_task_only_does_not_bind_a_finding(self):
        draft = import_text("Es wurde kein Modell ausgewählt.", task=CLOUD_QUOTE)
        result = self.bind_without_inference(draft, {"status": "fail", "findings": [finding("EVIDENCE")]})
        self.assertEqual("unverified", result["status"])
        self.assert_binding(result, [False])

    def test_negative_example_is_not_a_selected_model_for_any_model_policy(self):
        draft = import_text("Nicht ausführen. Negatives Beispiel: " + CLOUD_QUOTE)
        self.assertEqual([], draft["recommendations"])
        for forged_selection in (False, True):
            candidate = copy.deepcopy(draft)
            if forged_selection:
                candidate["recommendations"] = import_text(CLOUD_QUOTE)["recommendations"]
            for requirement_id in ("LOCAL_ONLY", "NO_PAID_API", "ABLITERATED", "HARDWARE"):
                with self.subTest(requirement_id=requirement_id, forged_selection=forged_selection):
                    result = self.bind_without_inference(candidate, {"status": "fail", "findings": [finding(requirement_id)]})
                    self.assertEqual("unverified", result["status"])
                    self.assert_binding(result, [False])

    def test_real_parsed_cloud_recommendation_remains_fail(self):
        draft = import_text(CLOUD_QUOTE)
        self.assertEqual("gpt-4o", draft["recommendations"][0]["model"])
        self.assertEqual(CLOUD_QUOTE, draft["recommendations"][0]["evidence_quote"])
        raw = {"status": "fail", "findings": [finding(), finding("NO_PAID_API")]}
        result = self.review(draft, raw)
        self.assertEqual("fail", result["status"])
        self.assert_binding(result, [True, True])

    def test_model_name_substring_does_not_replace_complete_recommendation_quote(self):
        result = self.review(import_text(CLOUD_QUOTE), {
            "status": "fail", "findings": [finding(evidence="GPT-4o")],
        })
        self.assertEqual("unverified", result["status"])
        self.assert_binding(result, [False])

    def test_mixed_bound_and_unbound_findings_keep_fail(self):
        result = self.review(import_text(CLOUD_QUOTE), {"status": "fail", "findings": [
            finding(), finding("NO_PAID_API", "Katalogeintrag bedeutet kostenpflichtige Nutzung."),
        ]})
        self.assertEqual("fail", result["status"])
        self.assert_binding(result, [True, False])

    def test_bound_finding_never_upgrades_raw_unverified_to_fail_or_pass(self):
        result = self.review(import_text(CLOUD_QUOTE), {
            "status": "unverified", "findings": [finding()],
        })
        self.assertEqual("unverified", result["status"])
        self.assert_binding(result, [True])

    def test_empty_passing_response_stays_pass_without_claiming_verification(self):
        result = self.review(import_text(CLOUD_QUOTE), {"status": "pass", "findings": []})
        self.assertEqual("pass", result["status"])
        self.assert_binding(result, [])


if __name__ == "__main__":
    unittest.main()
