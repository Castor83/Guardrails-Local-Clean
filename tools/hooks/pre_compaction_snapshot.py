"""Local PreCompact file snapshots. No network, models, chats or trust changes.

Installed as a standalone script under CODEX_HOME/hooks. Sources are opaque
files: the transcript format is not treated as a stable parsing interface.
"""
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import uuid

MAX_TRANSCRIPT_BYTES = 128 * 1024 * 1024
MAX_WORKING_BYTES = 4 * 1024 * 1024
MAX_EVENT_BYTES = 65536


def _local(path):
    """Refuse explicit UNC paths; this is not an OS network sandbox."""
    value = str(path)
    if value.startswith('\\\\?\\'):
        return bool(re.match(r'^[A-Za-z]:[\\/]', value[4:]))
    return not value.startswith(('\\\\', '//'))


def _copy_prefix(source, destination, allowed_roots, limit):
    if not source.is_absolute() or not _local(source):
        raise ValueError('Source must be an absolute local path.')
    resolved = source.resolve(strict=True)
    if not _local(resolved) or not any(resolved.is_relative_to(root) for root in allowed_roots):
        raise ValueError('Resolved source is outside its allowed area.')
    if not resolved.is_file():
        raise ValueError('Source is not a regular file.')
    digest = hashlib.sha256()
    with resolved.open('rb') as original:
        size = os.fstat(original.fileno()).st_size
        if size > limit:
            raise ValueError('Source exceeds the byte limit; no truncated backup.')
        with destination.open('xb') as copied:
            remaining = size
            while remaining:
                chunk = original.read(min(1024 * 1024, remaining))
                if not chunk:
                    raise OSError('Source became shorter during backup.')
                copied.write(chunk)
                digest.update(chunk)
                remaining -= len(chunk)
            copied.flush()
            os.fsync(copied.fileno())
        size_after = os.fstat(original.fileno()).st_size
        if size_after < size:
            raise OSError('Source became shorter during backup.')
    return dict(status='COPIED', source=str(resolved), file=destination.name,
                bytes=size, sha256=digest.hexdigest(), source_bytes_after_read=size_after,
                scope='Exact prefix available at file open; later appends are not part of this snapshot.')


def capture_snapshot(event, *, codex_home=None):
    """Return a durable manifest for a main-session PreCompact event."""
    if not isinstance(event, dict):
        return dict(status='ERROR', error='Invalid event object.')
    if (event.get('hook_event_name') != 'PreCompact'
            or event.get('trigger') not in {'auto', 'manual'} or event.get('subagent_id')):
        return dict(status='SKIPPED')
    directory = None
    try:
        session = event.get('session_id')
        if not isinstance(session, str) or str(uuid.UUID(session)) != session:
            raise ValueError('Canonical session ID required.')
        cwd_value = event.get('cwd')
        if not isinstance(cwd_value, str) or not Path(cwd_value).is_absolute() or not _local(cwd_value):
            raise ValueError('Absolute local working directory required.')
        cwd = Path(cwd_value).resolve(strict=True)
        if not _local(cwd) or not cwd.is_dir():
            raise ValueError('Working directory is not a directory.')
        home = Path(codex_home if codex_home is not None else
                    os.environ.get('CODEX_HOME', str(Path.home() / '.codex')))
        if not home.is_absolute() or not _local(home):
            raise ValueError('Absolute local CODEX_HOME required.')
        home = home.resolve(strict=True)
        if not _local(home):
            raise ValueError('Resolved CODEX_HOME must be local.')
        storage = home / 'handoff-snapshots'
        parent = storage / session
        if not parent.resolve().is_relative_to(home):
            raise ValueError('Resolved backup area escapes CODEX_HOME.')
        parent.mkdir(parents=True, exist_ok=True)
        name = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ') + '-' + uuid.uuid4().hex[:8]
        directory = parent / name
        directory.mkdir(exist_ok=False)
        manifest = dict(schema_version=1, session_id=session, cwd=str(cwd), trigger=event['trigger'],
                        started_at_utc=datetime.now(timezone.utc).isoformat(),
                        status='ERROR', snapshot_path=str(directory),
                        model_called=False, network_requested=False, chat_created=False)
        transcript_value = event.get('transcript_path')
        try:
            if not isinstance(transcript_value, str) or not transcript_value:
                raise ValueError('Host did not provide a local transcript path.')
            allowed = [(home / part).resolve() for part in ('sessions', 'archived_sessions')]
            # A redirected sessions directory must not escape CODEX_HOME.
            if any(not path.is_relative_to(home) for path in allowed):
                raise ValueError('History directory escapes CODEX_HOME.')
            manifest['transcript'] = _copy_prefix(Path(transcript_value), directory / 'transcript.jsonl',
                                                   allowed, MAX_TRANSCRIPT_BYTES)
        except (OSError, ValueError) as exc:
            manifest['transcript'] = dict(status='ERROR', error=str(exc))
        note = cwd / 'work/handoff' / (session + '-working.md')
        try:
            manifest['working_state'] = _copy_prefix(note, directory / 'working.md', [cwd], MAX_WORKING_BYTES)
        except FileNotFoundError:
            manifest['working_state'] = dict(status='MISSING', source=str(note))
        except (OSError, ValueError) as exc:
            manifest['working_state'] = dict(status='ERROR', error=str(exc))
        manifest['status'] = ('ERROR' if manifest['transcript']['status'] != 'COPIED' else
                              'PASS' if manifest['working_state']['status'] == 'COPIED' else 'PARTIAL')
        manifest['completed_at_utc'] = datetime.now(timezone.utc).isoformat()
        with (directory / 'manifest.json').open('x', encoding='utf-8', newline='\n') as handle:
            json.dump(manifest, handle, ensure_ascii=False, indent=2, allow_nan=False)
            handle.write('\n')
            handle.flush()
            os.fsync(handle.fileno())
        return manifest
    except (OSError, ValueError, TypeError) as exc:
        return dict(status='ERROR', error=str(exc), snapshot_path=str(directory) if directory else None)


def main():
    try:
        raw = sys.stdin.buffer.read(MAX_EVENT_BYTES + 1)
        if len(raw) > MAX_EVENT_BYTES:
            raise ValueError('Oversized hook event.')
        result = capture_snapshot(json.loads(raw.decode('utf-8')))
        if result['status'] in {'PASS', 'SKIPPED'}:
            output = {}
        else:
            output = dict(systemMessage='Lokale Vorsicherung vor Komprimierung: ' + result['status'] +
                          '. Sicherung und Manifest prüfen: ' + str(result.get('snapshot_path') or 'kein Sicherungsordner'))
    except (ValueError, UnicodeError):
        output = dict(systemMessage='Lokale Vorsicherung konnte das PreCompact-Ereignis nicht lesen.')
    print(json.dumps(output, ensure_ascii=True))


if __name__ == '__main__':
    main()
