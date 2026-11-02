"""Native result receipts support narrow action/title claims, never self-testimony."""

import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
try:
    from guardrails_local import action_evidence
except ImportError:
    action_evidence = None

SESSION = "11111111-1111-4111-8111-111111111111"
TURN = "22222222-2222-4222-8222-222222222222"
OTHER_TURN = "33333333-3333-4333-8333-333333333333"
THREAD = "44444444-4444-4444-8444-444444444444"
TOOL = "mcp__codex_app__list_threads"
TITLE = "DeepEval und Promptfoo integrieren"
CLAIM = 'Ich habe in der Chatliste gesucht und den exakten Chattitel verifiziert: „' + TITLE + '“.'


def mcp_threads(title=TITLE, *, error=False):
    data = {"threads": [{"threadId": THREAD, "title": title,
                         "url": "codex://threads/" + THREAD,
                         "summary": "Nur Hintergrund, kein weiterer Chattitel."}]}
    return {"content": [{"type": "text", "text": json.dumps(data, ensure_ascii=False)}],
            "isError": error}


class ActionEvidenceTests(unittest.TestCase):
    def test_direct_record_requires_current_session_permission_before_paths(self):
        config_path = self.root / 'work/codex/config.json'
        config_path.parent.mkdir(parents=True, exist_ok=True)
        config_path.write_text(json.dumps(dict(enabled=True, critic_enabled=False,
            session_ids=[SESSION], action_evidence_session_ids=[])), encoding='utf-8')
        from unittest.mock import patch
        with patch.object(action_evidence, '_directory') as directory:
            with self.assertRaises(ValueError):
                self.record()
        directory.assert_not_called()

    def test_checked_documentation_is_not_proved_by_weather_search(self):
        self.record(tool_name='web.run', tool_input={'search_query': [{'q': 'Wetter Berlin'}]})
        for verb in ('geprüft', 'überprüft'):
            with self.subTest(verb=verb):
                result = self.check(f'Ich habe die offizielle OpenAI-Dokumentation {verb}.')
                self.assertEqual('UNVERIFIED', result['status'])
                self.assertFalse(result['semantic_verified'])
                self.assertTrue(result['claims'][0]['result_claim'])

    def test_direct_german_research_claims_require_receipts(self):
        for text, expected in (
                ('Ich recherchierte im Web und fand die Dokumentation.', 'UNVERIFIED'),
                ('Wir haben die Chatliste durchsucht und den Chat gefunden.', 'FAIL'),
                ('Die Recherche ergab die passende Dokumentation.', 'UNVERIFIED')):
            with self.subTest(text=text):
                result = self.check(text)
                self.assertEqual(expected, result['status'])
                self.assertTrue(result['claims'])
                self.assertFalse(result['semantic_verified'])

    def test_quotes_negations_and_hypotheses_remain_nonclaims(self):
        for text in ('„Ich recherchierte im Web und fand die Dokumentation.“',
                     'Zitat: Wir haben die Chatliste durchsucht.',
                     'Wir haben die Chatliste nicht durchsucht.',
                     'Die Recherche ergab keine bestätigten Ergebnisse.',
                     'Hypothese: Die Recherche ergab den passenden Chat.',
                     'Ich werde im Web recherchieren und dann berichten.'):
            with self.subTest(text=text):
                self.assertEqual('SKIPPED', self.check(text)['status'])

    def setUp(self):
        self.assertIsNotNone(action_evidence, "The native action-evidence receipt module is missing.")
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        config = self.root / 'work/codex/config.json'
        config.parent.mkdir(parents=True)
        config.write_text(json.dumps(dict(enabled=True, critic_enabled=False, session_ids=[SESSION],
            action_evidence_session_ids=[SESSION])), encoding='utf-8')

    def record(self, response=None, **changes):
        arguments = dict(root=self.root, session_id=SESSION, turn_id=TURN,
                         tool_name=TOOL, tool_use_id="call_list_01", tool_input={"limit": 10},
                         tool_response=mcp_threads() if response is None else response)
        arguments.update(changes)
        return action_evidence.record_tool_result(**arguments)

    def check(self, text=CLAIM, turn_id=TURN):
        return action_evidence.check_action_claims(self.root, SESSION, turn_id, text)

    def test_real_record_read_binds_exact_structured_title_in_same_turn(self):
        response = mcp_threads()
        recorded = self.record(response)
        path = self.root / "work/codex/sessions" / SESSION / "receipts" / TURN / "call_list_01.json"
        self.assertEqual(recorded["status"], "RECORDED")
        self.assertEqual(Path(recorded["receipt_path"]), path)
        receipt = json.loads(path.read_bytes().decode("utf-8"))
        expected_sha = hashlib.sha256(json.dumps(response, ensure_ascii=False, sort_keys=True,
                                                separators=(",", ":"), allow_nan=False).encode("utf-8")).hexdigest()
        self.assertEqual(receipt["result_sha256"], expected_sha)
        self.assertEqual(receipt["tool_use_id"], "call_list_01")
        self.assertEqual(receipt["kind"], "chat_list")
        self.assertIs(receipt["error"], False)
        self.assertEqual(receipt["entries"][0]["title"], TITLE)
        self.assertEqual(receipt["entries"][0]["id"], THREAD)
        result = self.check()
        self.assertEqual(result["status"], "PASS")
        self.assertIs(result["checked"], True)
        self.assertIs(result["semantic_verified"], False)
        self.assertIn("call_list_01", result["claims"][0]["receipt_ids"])

    def test_structured_content_and_read_thread_are_valid_native_sources(self):
        self.record({"structuredContent": {"thread": {"id": THREAD, "title": TITLE}},
                     "content": [], "isError": False},
                    tool_name="mcp__codex_app__read_thread")
        self.assertEqual(self.check('Ich habe den exakten Chattitel verifiziert: „' + TITLE + '“.')["status"], "PASS")

    def test_reading_a_known_chat_does_not_prove_searching_the_chat_list(self):
        self.record(tool_name="mcp__codex_app__read_thread")
        self.assertEqual(self.check()["status"], "FAIL")

    def test_archived_threads_can_support_their_actual_title(self):
        self.record(tool_name="mcp__codex_app__list_archived_threads")
        self.assertEqual(self.check()["status"], "PASS")

    def test_missing_same_turn_receipt_fails_asserted_chat_success(self):
        result = self.check()
        self.assertEqual(result["status"], "FAIL")
        self.assertTrue(result["findings"])
        self.assertIs(result["semantic_verified"], False)

    def test_another_turn_receipt_never_proves_current_success(self):
        self.record(turn_id=OTHER_TURN)
        self.assertEqual(self.check()["status"], "FAIL")

    def test_list_call_alone_does_not_prove_a_different_exact_title(self):
        self.record(mcp_threads("Ein anderer tatsächlicher Chat"))
        self.assertEqual(self.check()["status"], "FAIL")

    def test_summary_text_is_not_promoted_to_a_chat_title(self):
        payload = {"threads": [{"id": THREAD, "title": "Anderer Titel", "summary": TITLE}]}
        self.record({"content": [{"type": "text", "text": json.dumps(payload)}]})
        self.assertEqual(self.check()["status"], "FAIL")

    def test_tool_error_and_empty_results_cannot_prove_found_title(self):
        for response in (mcp_threads(error=True),
                         {"structuredContent": {"threads": []}, "isError": False}):
            with self.subTest(response=response):
                self.record(response, tool_use_id="call_" + str(len(list(self.root.rglob("*.json")))))
        self.assertEqual(self.check()["status"], "FAIL")

    def test_successful_empty_list_proves_search_action_but_not_found_result(self):
        self.record({"structuredContent": {"threads": []}, "isError": False})
        self.assertEqual(self.check("Ich habe in der Chatliste gesucht.")["status"], "PASS")
        self.assertEqual(self.check("Ich habe den Chat in der Chatliste gefunden.")["status"], "FAIL")

    def test_unstructured_or_unrecognized_chat_payload_cannot_prove_search_action(self):
        for index, response in enumerate((
            {"content": [{"type": "text", "text": "nicht verfügbar"}], "isError": False},
            {"structuredContent": {"metadata": {"title": "nicht verfügbar"}}, "isError": False},
        )):
            with self.subTest(response=response):
                self.record(response, tool_use_id="call_unavailable_" + str(index))
                self.assertEqual(self.check("Ich habe die Chatliste durchsucht.")["status"], "FAIL")
        self.record({"structuredContent": {"threads": []}, "isError": False}, tool_use_id="call_empty")
        self.assertEqual(self.check("Ich habe die Chatliste durchsucht.")["status"], "PASS")

    def test_bash_or_exec_printing_mcp_json_is_not_native_chat_evidence(self):
        for number, name in enumerate(("Bash", "exec_command", "mcp__functions__exec")):
            self.record(tool_name=name, tool_use_id="call_fake_" + str(number),
                        tool_input={"command": "print('mcp__codex_app__list_threads')"})
        self.assertEqual(self.check()["status"], "FAIL")

    def test_web_and_tool_discovery_receipts_do_not_prove_a_chat_title(self):
        self.record(tool_name="web.run", tool_use_id="call_web", tool_input={"search_query": [{"q": TITLE}]})
        self.record(tool_name="tool_search", tool_use_id="call_tools", tool_input={"query": TITLE})
        self.assertEqual(self.check()["status"], "FAIL")

    def test_unknown_checks_and_unobserved_hosted_web_search_remain_unverified(self):
        for text in ("Ich habe die Installation geprüft.",
                     "Ich habe im Web gezielt nachrecherchiert."):
            with self.subTest(text=text):
                result = self.check(text)
                self.assertEqual(result["status"], "UNVERIFIED")
                self.assertIs(result["semantic_verified"], False)

    def test_no_claim_negation_hypothesis_and_quoted_examples_are_not_accusations(self):
        for text in (
            "Der Auftrag bleibt offen.",
            "Ich habe noch nicht in der Chatliste gesucht.",
            "Ich habe keinen passenden Chat gefunden.",
            "Hypothese: Ich habe den Chat in der Chatliste gefunden.",
            'Erfundenes Zitatbeispiel: „Ich habe den Chattitel verifiziert: X.“',
            '> Ich habe in der Chatliste gesucht und den Chattitel verifiziert: „X“.',
            '```text\nIch habe in der Chatliste gesucht und X gefunden.\n```',
        ):
            with self.subTest(text=text):
                result = self.check(text)
                self.assertEqual(result["status"], "SKIPPED")
                self.assertEqual(result["claims"], [])

    def test_coupled_title_in_next_paragraph_must_match_native_title(self):
        self.record()
        text = "Ich habe gezielt nachrecherchiert und den exakten Chattitel verifiziert.\n\n**" + TITLE + "**"
        self.assertEqual(self.check(text)["status"], "PASS")
        self.assertEqual(self.check(text.replace(TITLE, "Erfundener Chattitel"))["status"], "FAIL")

    def test_elliptical_chat_list_success_is_also_bound(self):
        self.assertEqual(self.check('In der Chatliste gefunden: „' + TITLE + '“.')["status"], "FAIL")
        self.record()
        self.assertEqual(self.check('In der Chatliste gefunden: „' + TITLE + '“.')["status"], "PASS")

    def test_explicit_title_assertions_and_found_chat_shorthand_require_evidence(self):
        for text in ('Der Chattitel lautet: **Erfunden**.',
                     'Gefunden: **Erfunden** (Chat)',
                     'Ich habe die Chatliste durchsucht.'):
            with self.subTest(text=text):
                self.assertEqual(self.check(text)["status"], "FAIL")
        self.record()
        self.assertEqual(self.check('Der Chattitel lautet: **' + TITLE + '**.')["status"], "PASS")
        self.assertEqual(self.check('Gefunden: **' + TITLE + '** (Chat)')["status"], "PASS")
        self.assertEqual(self.check('Ich habe die Chatliste durchsucht.')["status"], "PASS")

    def test_unrelated_negation_does_not_hide_positive_chat_check(self):
        text = 'Ich habe keine Cloud benutzt und die Chatliste geprüft.'
        self.assertEqual(self.check(text)["status"], "FAIL")
        self.record()
        self.assertEqual(self.check(text)["status"], "UNVERIFIED")
        self.assertEqual(self.check('Ich habe die Chatliste nicht geprüft.')["status"], "SKIPPED")

    def test_project_metadata_title_is_not_promoted_to_thread_title(self):
        payload = {"project": {"id": "project-1", "title": TITLE},
                   "metadata": {"title": TITLE},
                   "threads": [{"id": THREAD, "title": "Ein tatsächlicher anderer Chat"}]}
        recorded = self.record({"structuredContent": payload, "isError": False})
        receipt = json.loads(Path(recorded["receipt_path"]).read_bytes().decode("utf-8"))
        self.assertEqual([entry["title"] for entry in receipt["entries"]], ["Ein tatsächlicher anderer Chat"])
        self.assertEqual(self.check()["status"], "FAIL")

    def test_action_words_inside_an_actual_title_keep_the_exact_title_constraint(self):
        title = "Ich habe den Chat gefunden"
        self.record()
        text = 'Ich habe den exakten Chattitel verifiziert: „' + title + '“.'
        self.assertEqual(self.check(text)["status"], "FAIL")
        self.record(mcp_threads(title), tool_use_id="call_title_02")
        self.assertEqual(self.check(text)["status"], "PASS")

    def test_plain_named_chat_must_match_the_actual_title(self):
        self.record()
        self.assertEqual(self.check('Ich habe den Chat Erfunden gefunden.')["status"], "FAIL")
        self.assertEqual(self.check('Ich habe den Chat ' + TITLE + ' gefunden.')["status"], "PASS")

    def test_every_explicit_found_title_in_a_list_needs_its_own_match(self):
        self.record(mcp_threads("Echt"))
        text = 'Ich habe diese Chats gefunden:\n- **Echt**\n- **Erfunden**'
        self.assertEqual(self.check(text)["status"], "FAIL")
        self.record(mcp_threads("Erfunden"), tool_use_id="call_title_02")
        self.assertEqual(self.check(text)["status"], "PASS")

    def test_compound_bullet_cannot_hide_a_second_title_behind_the_first(self):
        self.record(mcp_threads("Echt"))
        text = 'Ich habe diese Chats gefunden:\n- **Echt** und **Erfunden**'
        self.assertEqual(self.check(text)["status"], "UNVERIFIED")

    def test_incompletely_parsed_found_title_cannot_get_blanket_success(self):
        self.record()
        for text in ('Ich habe diese Chats gefunden:\n- **' + TITLE + '**\n- weiterer Chat siehe oben',
                     'Ich habe diese Chats gefunden: **' + TITLE + '** und **Erfunden**.',
                     'Ich habe den gesuchten Chat gefunden.'):
            with self.subTest(text=text):
                self.assertEqual(self.check(text)["status"], "UNVERIFIED")

    def test_hypothetical_title_and_quoted_assertion_are_not_success_claims(self):
        for text in ('Der Chattitel lautet vermutlich: **Erfunden**.',
                     'Hypothese: Der Chattitel lautet: **Erfunden**.',
                     '„Ich habe die Chatliste durchsucht.“'):
            with self.subTest(text=text):
                self.assertEqual(self.check(text)["status"], "SKIPPED")

    def test_identical_receipt_is_idempotent_and_conflicting_id_cannot_overwrite(self):
        first = self.record()
        path = Path(first["receipt_path"])
        before = path.read_bytes()
        self.assertEqual(self.record()["status"], "DUPLICATE")
        self.assertEqual(path.read_bytes(), before)
        with self.assertRaises(ValueError):
            self.record(mcp_threads("Ein anderer Titel unter derselben Aufruf-ID"))
        self.assertEqual(path.read_bytes(), before)

    def test_invalid_identifiers_and_oversized_results_cannot_write_receipts(self):
        before = {path.relative_to(self.root).as_posix(): path.read_bytes()
                  for path in self.root.rglob('*.json')}
        for changes in ({"session_id": "../escape"}, {"turn_id": None},
                        {"tool_use_id": "../escape"}, {"tool_use_id": "CON"},
                        {"tool_response": {"huge": "x" * 600000}}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                self.record(**changes)
        self.assertEqual({path.relative_to(self.root).as_posix(): path.read_bytes()
                          for path in self.root.rglob('*.json')}, before)

    def test_accidentally_modified_receipt_is_not_accepted_as_title_evidence(self):
        recorded = self.record()
        path = Path(recorded["receipt_path"])
        value = json.loads(path.read_bytes().decode("utf-8"))
        value["entries"][0]["title"] = "Manipulierter Titel"
        path.write_bytes(json.dumps(value).encode("utf-8"))
        self.assertNotEqual(self.check()["status"], "PASS")


if __name__ == "__main__":
    unittest.main()
