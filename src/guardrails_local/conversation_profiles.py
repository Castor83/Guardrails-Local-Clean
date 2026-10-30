"""Bounded conversation profiles, using two hash-pinned native local validators.

Evidence is caller-supplied data, never a source of executable instructions.
constraints: min_chars/max_chars/required_sections; sources: url/title/excerpt;
claims: quote/source_url/evidence_quote; recommendations: criteria/options/
decision/rationale. All semantic results remain UNVERIFIED. A formal PASS only
attests the explicitly requested format limits. No model or reask is started.
"""
from __future__ import annotations

import hashlib
import io
import json
import os
from pathlib import Path
import re
import sys
import types
import urllib.parse
import urllib.request
import uuid
import zipfile


PROFILES = frozenset({'conversation', 'explanation', 'research', 'recommendation', 'project', 'source'})
SCOPE = 'Nur ausgewiesene lokale Form- und Belegbindungen; keine allgemeine Wahrheits-, Qualitäts- oder Sicherheitsfreigabe.'
_COMPONENTS = {
    'valid_length': {
        'distribution': 'guardrails-ai-valid-length', 'version': '0.1.0', 'class_name': 'ValidLength',
        'native_validator': 'guardrails/valid_length', 'size_bytes': 4030,
        'wheel_sha256': '5e9a92a0dba699e50213bc4bc670ae2a4f0ee6b5ce2ab92ef649f33db63094df',
        'main_sha256': '83719c0430c0796b30c81d862a0c2f7535f572afce07669d6a5fb4088bb269c4',
        'url': 'https://files.pythonhosted.org/packages/95/e4/16356c06ee0ce81cc980cee4e492cb2aa6f2df0eaca6b82b8d2caa2166e6/guardrails_ai_valid_length-0.1.0-py3-none-any.whl'},
    'valid_url': {
        'distribution': 'guardrails-ai-valid-url', 'version': '0.1.0', 'class_name': 'ValidURL',
        'native_validator': 'guardrails/valid_url', 'size_bytes': 3473,
        'wheel_sha256': '649f499cbbc969f10ffbc74ef2a7a39bc80f0084d92476d9f897aff452421d7e',
        'main_sha256': '116d73087934c6527bf9724d271b43a403282dbeda483231303bd0b05fa42554',
        'url': 'https://files.pythonhosted.org/packages/11/23/c68621d8bf972dd7d94a8f24e00bb1569d1c76f4574afc2470cf0fa03280/guardrails_ai_valid_url-0.1.0-py3-none-any.whl'},
}


def select_profile(task):
    """Resolve explicit first-line labels or a narrow actual request intention."""
    if not isinstance(task, str) or not task:
        return 'conversation'
    first = task.splitlines()[0]
    explicit = {'Guardrails: Projekt': 'project', 'Guardrails: Modelle': 'recommendation',
        'Profil: Gespräch': 'conversation', 'Profil: Erklärung': 'explanation',
        'Profil: Recherche': 'research', 'Profil: Empfehlung': 'recommendation',
        'Profil: Code': 'project', 'Profil: Quellenprüfung': 'source'}
    if first in explicit:
        return explicit[first]
    request = first.strip().casefold()
    # Quoted material and negated actions never activate a scope. A negative
    # constraint ("ohne Cloud") does not negate the requested action.
    if request.startswith(('>', '"', "'", '`')):
        return 'conversation'
    request = re.sub(r'^bitte\s+', '', request)
    main_clause = re.split(r'[,;.!?]', request, maxsplit=1)[0]
    if (re.match(r'^(?:nicht|kein|keine)\b', main_clause)
            or re.search(r'\bnicht(?:\s+(?:mehr|erneut|nochmal))?$', main_clause)
            or re.search(r'\bnicht\s+(?:sondern|reparieren|implementieren|programmieren|testen)\b', main_clause)):
        return 'conversation'
    polite = re.match(r'^(?:kannst|könntest|würdest) du\b(.+)', request)
    body = re.split(r'[,;.!?]', polite.group(1), maxsplit=1)[0] if polite else request
    patterns = (
        ('source', r'^(?:prüfe|überprüfe|validiere)\b.*\b(?:quelle|quellen|quellenbündel|beleg|belege)\b'),
        ('research', r'^(?:recherchiere|suche|finde|überprüfe aktuell)\b'),
        ('recommendation', r'^(?:vergleiche|empfiehl|empfehle|bewerte|wähle)\b'),
        ('project', r'^(?:implementiere|repariere|programmiere|debugge|behebe|ändere|erstelle den code|teste)\b'),
        ('explanation', r'^(?:erkläre|erläutere|beschreibe|fasse zusammen)\b'),
    )
    if polite:
        if re.search(r'\b(?:prüfen|überprüfen|validieren)\b.*\b(?:quelle|quellen)\b|\b(?:quelle|quellen)\b.*\b(?:prüfen|überprüfen)\b', body):
            return 'source'
        intentions = []
        for profile, verbs in (
                ('research', 'recherchieren|suchen|finden'),
                ('recommendation', 'vergleichen|empfehlen|bewerten'),
                ('project', 'implementieren|reparieren|programmieren|debuggen|beheben|ändern|testen'),
                ('explanation', 'erklären|erläutern|beschreiben|zusammenfassen')):
            match = re.search(r'\b(?:' + verbs + r')\b', body)
            if match:
                intentions.append((match.start(), profile))
        if intentions:
            return min(intentions)[1]
    for profile, pattern in patterns:
        if re.search(pattern, request):
            return profile
    return 'conversation'


def _sha(value):
    return hashlib.sha256(value).hexdigest()


def _area(root):
    root = Path(root).resolve()
    area = root / 'work/profile-components'
    if not area.resolve().is_relative_to(root):
        raise ValueError('Component directory escapes the project.')
    return area


def _safe_file(area, relative):
    path = area / relative
    if path.is_symlink() or not path.resolve().is_relative_to(area.resolve()):
        raise ValueError('Component path escapes the fixed directory.')
    return path


def _write_file(area, relative, payload):
    """Reject symlinks and atomically replace leaves without following hardlinks."""
    destination = _safe_file(area, relative)
    temporary = _safe_file(area, relative + '.' + uuid.uuid4().hex + '.tmp')
    destination.parent.mkdir(parents=True, exist_ok=True)
    try:
        with temporary.open('xb') as stream:
            stream.write(payload)
        os.replace(temporary, destination)
    finally:
        temporary.unlink(missing_ok=True)


def verify_components(root):
    """Verify fixed package identities and executable bytes without importing them."""
    area = _area(root)
    manifest_path = _safe_file(area, 'manifest.json')
    if manifest_path.stat().st_size > 65536:
        raise ValueError('Oversized component manifest.')
    manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    records = manifest.get('components')
    if not isinstance(records, list) or len(records) != len(_COMPONENTS):
        raise ValueError('Incomplete component manifest.')
    checked = []
    for key, expected in _COMPONENTS.items():
        matches = [item for item in records if isinstance(item, dict) and item.get('key') == key]
        if len(matches) != 1 or any(matches[0].get(field) != value for field, value in expected.items()):
            raise ValueError('Component identity differs from pinned artifact.')
        module = _safe_file(area, key + '/main.py')
        if module.stat().st_size > 8192 or _sha(module.read_bytes()) != expected['main_sha256']:
            raise ValueError('Native validator module hash differs from pinned artifact.')
        checked.append(dict(key=key, **expected, path=str(module)))
    return checked


def setup_components(root, *, download=False):
    """Materialize only the two reviewed modules/metadata; never pip or postinstall."""
    import importlib.metadata
    from packaging.requirements import Requirement
    from packaging.version import Version

    installed = {name: importlib.metadata.version(name) for name in ('guardrails-ai', 'rstr', 'pydantic')}
    area = _area(root)
    area.mkdir(parents=True, exist_ok=True)
    records = []
    for key, expected in _COMPONENTS.items():
        filename = urllib.parse.unquote(urllib.parse.urlsplit(expected['url']).path.rsplit('/', 1)[1])
        wheel = _safe_file(area, 'wheels/' + filename)
        if wheel.is_file():
            payload = wheel.read_bytes()
        elif download:
            opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
            with opener.open(expected['url'], timeout=30) as response:
                if urllib.parse.urlsplit(response.geturl()).hostname != 'files.pythonhosted.org':
                    raise ValueError('Unexpected wheel redirect.')
                payload = response.read(expected['size_bytes'] + 1)
            if len(payload) != expected['size_bytes'] or _sha(payload) != expected['wheel_sha256']:
                raise ValueError('Official wheel size or SHA256 differs from pinned artifact.')
            wheel.parent.mkdir(parents=True, exist_ok=True)
            _write_file(area, 'wheels/' + filename, payload)
        else:
            raise ValueError('Reviewed wheel is missing; explicit download setup is required.')
        if len(payload) != expected['size_bytes'] or _sha(payload) != expected['wheel_sha256']:
            raise ValueError('Wheel size or SHA256 differs from pinned artifact.')
        with zipfile.ZipFile(io.BytesIO(payload)) as archive:
            members = archive.namelist()
            prefix = f'guardrails_ai/{key}/'
            if (len(members) > 16 or len(set(members)) != len(members)
                    or any('..' in Path(n).parts or n.startswith(('/', '\\')) for n in members)
                    or {n for n in members if n.endswith('.py')} != {prefix + 'main.py', prefix + '__init__.py'}
                    or any(n.endswith(('.pth', 'entry_points.txt')) for n in members)
                    or archive.testzip() is not None):
                raise ValueError('Unexpected executable wheel members.')
            source = archive.read(prefix + 'main.py')
            if _sha(source) != expected['main_sha256']:
                raise ValueError('Reviewed module SHA256 differs.')
            metadata_name = next(n for n in members if n.endswith('.dist-info/METADATA'))
            from email.parser import BytesParser
            metadata = BytesParser().parsebytes(archive.read(metadata_name))
            if metadata['Name'] != expected['distribution'] or metadata['Version'] != expected['version']:
                raise ValueError('Wheel metadata differs from fixed package identity.')
            for raw in metadata.get_all('Requires-Dist', []):
                requirement = Requirement(raw)
                if requirement.marker is None or requirement.marker.evaluate():
                    if Version(importlib.metadata.version(requirement.name)) not in requirement.specifier:
                        raise ValueError('Existing controller dependencies do not satisfy native component.')
            directory = _safe_file(area, key)
            directory.mkdir(parents=True, exist_ok=True)
            _write_file(area, key + '/main.py', source)
            _write_file(area, key + '/METADATA', archive.read(metadata_name))
            license_name = next(n for n in members if n.endswith('/licenses/LICENSE'))
            _write_file(area, key + '/LICENSE', archive.read(license_name))
        records.append(dict(key=key, **expected))
    manifest = dict(version=1, components=records, controller_packages=installed,
                    package_installed=False, postinstall_executed=False, model_downloaded=False)
    _write_file(area, 'manifest.json', json.dumps(manifest, indent=2).encode('utf-8'))
    return dict(status='READY', components=verify_components(root), controller_packages=installed,
                package_installed=False, postinstall_executed=False, model_downloaded=False)


def _native(root, key, value, **kwargs):
    # Verification repeats even when Python has cached the imported class.
    record = next(item for item in verify_components(root) if item['key'] == key)
    from . import validator as _local_guardrails  # disables telemetry before Guardrails import
    from guardrails.validator_base import PassResult
    module_name = '_guardrails_profile_' + key + '_' + record['main_sha256']
    module = sys.modules.get(module_name)
    if module is None:
        # Compile exactly the verified source bytes, never a sibling pyc cache.
        source = Path(record['path']).read_bytes()
        if _sha(source) != record['main_sha256']:
            raise ValueError('Native module changed before execution.')
        module = types.ModuleType(module_name)
        module.__file__ = record['path']
        sys.modules[module_name] = module
        try:
            exec(compile(source, record['path'], 'exec'), module.__dict__)
        except Exception:
            sys.modules.pop(module_name, None)
            raise
    validator = getattr(module, record['class_name'])(on_fail='noop', **kwargs)
    passed = isinstance(validator.validate(value, {}), PassResult)
    return passed, dict(distribution=record['distribution'], version=record['version'],
        native_validator=record['native_validator'], wheel_sha256=record['wheel_sha256'],
        module_sha256=record['main_sha256'], passed=passed)


def _nonempty(value, maximum=65536):
    return isinstance(value, str) and bool(value.strip()) and len(value) <= maximum


def check_profile(root, profile, text, *, evidence=None):
    """Check applicable mechanical requirements; never infer semantic correctness."""
    report = dict(status='SKIPPED', profile=profile, findings=[], scope=SCOPE,
                  components=[], checked=False, semantic_verified=False)

    def finding(rule, description, status='UNVERIFIED'):
        report['findings'].append(dict(rule=rule, description=description, status=status))

    def finish(default='UNVERIFIED'):
        states = [item['status'] for item in report['findings']]
        report['status'] = next((s for s in ('ERROR', 'FAIL', 'UNVERIFIED') if s in states), default)
        return report

    def native(key, value, **kwargs):
        passed, component = _native(root, key, value, **kwargs)
        if component not in report['components']:
            report['components'].append(component)
        report['checked'] = True
        return passed

    try:
        if profile not in PROFILES or not isinstance(text, str):
            finding('input', 'Profil oder vollständige nichtleere Antwort fehlt.', 'ERROR')
            return finish()
        report['answer_sha256'] = _sha(text.encode('utf-8'))
        if not text.strip():
            finding('empty_answer', 'Die vollständige Antwort ist leer.', 'FAIL')
            return finish()
        if evidence is None:
            evidence = {}
        if not isinstance(evidence, dict) or len(json.dumps(evidence, ensure_ascii=False, allow_nan=False)) > 262144:
            raise ValueError('Evidence must be a bounded JSON object.')
        constraints = evidence.get('constraints', {})
        if not isinstance(constraints, dict) or set(constraints) - {'min_chars', 'max_chars', 'required_sections'}:
            raise ValueError('Unsupported explicit format constraints.')
        if profile == 'project':
            report['delegated_to'] = 'workflow'
            return report
        if profile == 'conversation' and not constraints:
            return report
        minimum, maximum = constraints.get('min_chars', 1), constraints.get('max_chars', 32000)
        if (type(minimum) is not int or type(maximum) is not int
                or not 0 <= minimum <= maximum <= 262144):
            raise ValueError('Explicit length bounds must be bounded integers.')
        if len(text) > 262144:
            finding('length', 'Die vollständige Antwort überschreitet die Eingabegrenze; keine Kürzung.', 'FAIL')
            return finish()
        if not native('valid_length', text, min=minimum, max=maximum):
            finding('length', 'Die Antwort verletzt die ausgewiesene Zeichengrenze; unverändert verworfen.', 'FAIL')
        sections = constraints.get('required_sections', [])
        if not isinstance(sections, list) or len(sections) > 32 or any(not _nonempty(s, 200) for s in sections):
            raise ValueError('Required sections must be a bounded string list.')
        if any(section not in text for section in sections):
            finding('required_sections', 'Ein ausdrücklich verlangter Abschnitt fehlt.', 'FAIL')
        if profile == 'conversation':
            return finish('PASS')
        if profile == 'source':
            report['delegated_to'] = 'explicit_nli_source_check'
            finding('source', 'Explizite vollständige Quelle und reservierte native NLI-Ausführung sind erforderlich; hier keine Inferenz.')
            return finish()
        if profile == 'research':
            sources, claims = evidence.get('sources'), evidence.get('claims')
            if not isinstance(sources, list) or not 1 <= len(sources) <= 16:
                finding('sources', 'Strukturierte tatsächlich beschaffte Quellenbelege fehlen; ein URL-Text genügt nicht.')
                return finish()
            valid_sources = {}
            for source in sources:
                if not isinstance(source, dict) or not _nonempty(source.get('url'), 4096):
                    finding('sources', 'Quellenmetadaten sind unvollständig.')
                    continue
                url = source['url']
                valid = native('valid_url', url)
                parsed = urllib.parse.urlsplit(url)
                if (not valid or parsed.scheme not in {'https', 'http'} or not parsed.hostname
                        or parsed.username is not None or parsed.password is not None
                        or any(character.isspace() or ord(character) < 32 for character in url)):
                    finding('source_url', 'Quellenlink verletzt die lokale HTTP-/HTTPS-Adressregel.', 'FAIL')
                    continue
                if not _nonempty(source.get('title'), 1024) or not _nonempty(source.get('excerpt')):
                    finding('sources', 'Titel und tatsächlich beschaffter vollständiger Belegauszug fehlen.')
                    continue
                if url in valid_sources:
                    finding('sources', 'Mehrdeutige doppelte Quellenadresse.', 'FAIL')
                    continue
                valid_sources[url] = source['excerpt']
            bound = bool(valid_sources) and isinstance(claims, list) and 1 <= len(claims) <= 64
            if not bound:
                finding('claim_binding', 'Antwortaussagen sind nicht wortgetreu an vorhandene Quellenbelege gebunden.')
            else:
                for claim in claims:
                    if (not isinstance(claim, dict) or not _nonempty(claim.get('quote'))
                            or not _nonempty(claim.get('evidence_quote'))
                            or not isinstance(claim.get('source_url'), str)
                            or claim['quote'] not in text
                            or claim['evidence_quote'] not in valid_sources.get(claim['source_url'], '')):
                        bound = False
                        finding('claim_binding', 'Ein angegebener Wortlaut steht nicht in Antwort oder Quellenbeleg.', 'FAIL')
            report['source_bindings_checked'] = bound
            finding('semantic_scope', 'Wortlaut- und Quellenstruktur belegen weder Abrufherkunft noch inhaltliche Folgerung oder vollständige Tatsachendeckung.')
        elif profile == 'recommendation':
            recommendation = evidence.get('recommendations')
            if not isinstance(recommendation, dict):
                finding('recommendation', 'Explizite Kriterien, Optionen, Entscheidung und Begründung fehlen.')
                return finish()
            criteria, options = recommendation.get('criteria'), recommendation.get('options')
            decision, rationale = recommendation.get('decision'), recommendation.get('rationale')
            if (not isinstance(criteria, list) or not 1 <= len(criteria) <= 32
                    or any(not _nonempty(c, 1000) for c in criteria)
                    or not isinstance(options, list) or len(options) > 32
                    or any(not _nonempty(option, 1000) for option in options)
                    or not _nonempty(decision, 1000) or not _nonempty(rationale)):
                finding('recommendation', 'Strukturierte Empfehlungsbelege sind unvollständig.')
                return finish()
            if not native('valid_length', options, min=1, max=3):
                finding('recommendation_count', 'Es sind eine bis höchstens drei Optionen zulässig.', 'FAIL')
            bound = decision in options and decision in text and rationale in text
            report['recommendation_structure_checked'] = bound
            if not bound:
                finding('recommendation_binding', 'Entscheidung oder Begründung fehlen im vollständigen Antworttext.', 'FAIL')
            finding('semantic_scope', 'Kriterien- und Entscheidungsstruktur belegen keine Eignung, Aktualität oder Wahrheit der Empfehlung.')
        else:
            finding('semantic_scope', 'Erklärungsform geprüft; fachliche Richtigkeit wurde durch keine gebundenen Quellenprüfung belegt.')
        return finish()
    except Exception as exc:
        finding('profile_error', 'Lokale Profilprüfung fehlgeschlagen: ' + type(exc).__name__, 'ERROR')
        return finish()
