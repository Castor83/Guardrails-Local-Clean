"""Actual local-file backup contracts; no models, chats, network or real history."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

SCRIPT = Path(__file__).resolve().parents[1] / 'tools/hooks/pre_compaction_snapshot.py'
snapshot = None
if SCRIPT.is_file():
    spec = importlib.util.spec_from_file_location('pre_compaction_snapshot', SCRIPT)
    snapshot = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(snapshot)

SESSION = '11111111-1111-4111-8111-111111111111'


class PreCompactionSnapshotTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(snapshot, 'The local PreCompact backup implementation is missing.')
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.base = Path(self.temporary.name)
        self.codex_home = self.base / 'codex'
        self.transcript = self.codex_home / 'sessions/example.jsonl'
        self.transcript.parent.mkdir(parents=True)
        self.transcript.write_bytes(b'{"role":"user","text":"private test history"}\n')
        self.cwd = self.base / 'workspace'
        self.note = self.cwd / 'work/handoff' / (SESSION + '-working.md')
        self.note.parent.mkdir(parents=True)
        self.note.write_bytes(b'Goal: preserve decisions. Next: actual next step.\n')
        self.event = dict(hook_event_name='PreCompact', trigger='auto', session_id=SESSION,
                          cwd=str(self.cwd), transcript_path=str(self.transcript))

    def run_snapshot(self, **changes):
        return snapshot.capture_snapshot(dict(self.event, **changes), codex_home=self.codex_home)

    def test_saves_actual_complete_files_with_hashes_and_preserves_originals(self):
        original = self.transcript.read_bytes(), self.note.read_bytes()
        result = self.run_snapshot()
        self.assertEqual('PASS', result['status'])
        directory = Path(result['snapshot_path'])
        manifest = json.loads((directory / 'manifest.json').read_text(encoding='utf-8'))
        for key, content, name in [('transcript', original[0], 'transcript.jsonl'),
                                   ('working_state', original[1], 'working.md')]:
            self.assertEqual(content, (directory / name).read_bytes())
            self.assertEqual(hashlib.sha256(content).hexdigest(), manifest[key]['sha256'])
            self.assertEqual(len(content), manifest[key]['bytes'])
        self.assertEqual(original, (self.transcript.read_bytes(), self.note.read_bytes()))

    def test_wrong_event_and_subagent_do_not_create_any_snapshot(self):
        for changes in ({'hook_event_name': 'SessionStart'}, {'subagent_id': 'worker'}):
            self.assertEqual('SKIPPED', self.run_snapshot(**changes)['status'])
        self.assertFalse((self.codex_home / 'handoff-snapshots').exists())

    def test_missing_note_is_explicit_partial_but_history_is_preserved(self):
        self.note.unlink()
        result = self.run_snapshot()
        self.assertEqual('PARTIAL', result['status'])
        manifest = json.loads((Path(result['snapshot_path']) / 'manifest.json').read_text())
        self.assertEqual('MISSING', manifest['working_state']['status'])
        self.assertEqual(self.transcript.read_bytes(),
                         (Path(result['snapshot_path']) / 'transcript.jsonl').read_bytes())

    def test_outside_history_source_is_not_copied(self):
        outside = self.base / 'unrelated-private-file.jsonl'
        outside.write_bytes(b'UNRELATED_SOURCE_MUST_NOT_BE_COPIED')
        result = self.run_snapshot(transcript_path=str(outside))
        self.assertEqual('ERROR', result['status'])
        directory = Path(result['snapshot_path'])
        self.assertFalse((directory / 'transcript.jsonl').exists())
        self.assertNotIn(b'UNRELATED_SOURCE_MUST_NOT_BE_COPIED', (directory / 'manifest.json').read_bytes())
        self.assertEqual(self.note.read_bytes(), (directory / 'working.md').read_bytes())

    def test_size_limit_rejects_history_instead_of_truncating(self):
        with patch.object(snapshot, 'MAX_TRANSCRIPT_BYTES', 8):
            result = self.run_snapshot()
        self.assertEqual('ERROR', result['status'])
        directory = Path(result['snapshot_path'])
        self.assertFalse((directory / 'transcript.jsonl').exists())
        manifest = json.loads((directory / 'manifest.json').read_text())
        self.assertEqual('ERROR', manifest['transcript']['status'])

    def test_redirected_note_directory_cannot_copy_outside_workspace(self):
        outside = self.base / 'other-workspace'
        outside.mkdir()
        outside_note = outside / self.note.name
        outside_note.write_bytes(b'UNRELATED_NOTE_MUST_NOT_BE_COPIED')
        self.note.unlink()
        link = self.note.parent
        link.rmdir()
        if os.name == 'nt':
            subprocess.run(['cmd.exe', '/c', 'mklink', '/J', str(link), str(outside)],
                           capture_output=True, check=True, creationflags=subprocess.CREATE_NO_WINDOW)
            self.addCleanup(link.rmdir)
        else:
            link.symlink_to(outside, target_is_directory=True)
            self.addCleanup(link.unlink)
        result = self.run_snapshot()
        self.assertEqual('PARTIAL', result['status'])
        directory = Path(result['snapshot_path'])
        self.assertFalse((directory / 'working.md').exists())
        self.assertNotIn(b'UNRELATED_NOTE_MUST_NOT_BE_COPIED', (directory / 'manifest.json').read_bytes())
        self.assertEqual(b'UNRELATED_NOTE_MUST_NOT_BE_COPIED', outside_note.read_bytes())

    def test_repeated_events_keep_separate_snapshots(self):
        first = self.run_snapshot()
        self.transcript.write_bytes(b'new available history\n')
        second = self.run_snapshot()
        self.assertNotEqual(first['snapshot_path'], second['snapshot_path'])
        self.assertIn(b'private test history', (Path(first['snapshot_path']) / 'transcript.jsonl').read_bytes())
        self.assertEqual(b'new available history\n', (Path(second['snapshot_path']) / 'transcript.jsonl').read_bytes())

    def test_invalid_session_is_refused_before_creating_storage(self):
        result = self.run_snapshot(session_id='../../outside')
        self.assertEqual('ERROR', result['status'])
        self.assertFalse((self.codex_home / 'handoff-snapshots').exists())

    def test_cli_saves_test_data_without_exposing_contents_in_output(self):
        environment = dict(os.environ, CODEX_HOME=str(self.codex_home))
        result = subprocess.run([sys.executable, '-I', str(SCRIPT)],
                                input=json.dumps(self.event), text=True, capture_output=True,
                                env=environment, timeout=10)
        self.assertEqual(0, result.returncode)
        self.assertEqual({}, json.loads(result.stdout))
        self.assertEqual('', result.stderr)
        directories = list((self.codex_home / 'handoff-snapshots' / SESSION).iterdir())
        self.assertEqual(1, len(directories))
        self.assertEqual(self.transcript.read_bytes(), (directories[0] / 'transcript.jsonl').read_bytes())
