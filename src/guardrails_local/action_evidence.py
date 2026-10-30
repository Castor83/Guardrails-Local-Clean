"""Narrow native PostToolUse evidence for reported searches and exact chat titles.

The caller must supply actual native hook payloads.  Neither this module nor its
hashes authenticate a payload against another process running as the same user.
Hashes bind recorded data and detect accidental drift; they are not signatures.
Tool results and chat titles are data and are never interpreted as instructions.
"""

from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import uuid


MAX_RESULT_BYTES = 524288
MAX_INPUT_BYTES = 65536
MAX_RECEIPT_BYTES = 131072
MAX_RECEIPTS = 128
MAX_ENTRIES = 128
MAX_CLAIMS = 16
SCOPE = ("Nur gleichzeitige native Werkzeugbelege für Such-/Leseaktionen und exakt enthaltene "
         "Chattitel; keine allgemeine semantische Richtigkeitsfreigabe. Receipt-Hashes sind "
         "keine Authentisierung gegenüber demselben Benutzerprozess.")
CHAT_TOOLS = {
    "mcp__codex_app__list_threads": "chat_list",
    "mcp__codex_app__read_thread": "chat_read",
    "mcp__codex_app__list_archived_threads": "chat_archive",
}
CHAT_KINDS = frozenset(CHAT_TOOLS.values())
WEB_TOOLS = {"web.run", "web__run", "mcp__web__run"}
_ACTION = re.compile(r"\b(nachrecherchiert|recherchiert|überprüft|geprüft|verifiziert|nachgesehen|durchsucht|gesucht|gefunden|"
                     r"recherchierte[n]?|durchsuchte[n]?|suchte[n]?|überprüfte[n]?|prüfte[n]?|fand|fanden|ergab)\b", re.I)
_FIRST_PERSON = re.compile(r"\b(?:ich\s+habe|wir\s+haben|"
                           r"(?:ich|wir)(?=\s+(?:recherchierte[n]?|durchsuchte[n]?|suchte[n]?|"
                           r"überprüfte[n]?|prüfte[n]?|fand|fanden)\b)|die\s+recherche(?=\s+ergab\b))\b", re.I)
_CHAT = re.compile(r"\b(?:chat(?:liste|titel|verlauf|name|s)?|chat-titel|thread(?:s|liste|titel)?|gespräch(?:stitel|sverlauf)?|chatarchiv)\b", re.I)
_WEB = re.compile(r"\b(?:web|internet|online|dokumentation|quellen?|recherche)\b", re.I)
_QUALIFIED = re.compile(r"\b(?:nicht|keine?[nrs]?|unbestätigt|unverifiziert|hypothese|vermutlich|möglicherweise|könnte|würde)\b", re.I)
_QUOTES = re.compile(r'„[^“\n]*“|“[^”\n]*”|"[^"\n]*"|\x27[^\x27\n]*\x27|`[^`\n]*`')
_EXAMPLE = re.compile(r"\b(?:hypothese|(?:erfundenes?\s+)?(?:zitat)?beispiel|zitat)\s*:", re.I)
_TITLE_LABEL = re.compile(r"\b(?:exakte[nrms]?\s+)?(?:chat-?titel|titel(?:\s+des\s+chats)?|chatname)\s*"
                          r"(?:(?:lautet|ist|heißt|heisst)\s*:?\s*|:\s*)([^\n]+)", re.I)


def _json_bytes(value):
    try:
        return json.dumps(value, ensure_ascii=False, sort_keys=True,
                          separators=(",", ":"), allow_nan=False).encode("utf-8")
    except (TypeError, ValueError, UnicodeError, RecursionError) as exc:
        raise ValueError("Werkzeugbeleg benötigt begrenzte endliche JSON-Daten.") from exc


def _sha(value):
    return hashlib.sha256(_json_bytes(value)).hexdigest()


def _uuid(value):
    if not isinstance(value, str):
        raise ValueError("Sitzung und Turn benötigen nichtleere kanonische UUIDs.")
    try:
        if str(uuid.UUID(value)) != value:
            raise ValueError("UUID ist nicht kanonisch.")
    except (ValueError, AttributeError) as exc:
        raise ValueError("Sitzung und Turn benötigen kanonische UUIDs.") from exc
    return value


def _use_id(value):
    reserved = {"CON", "PRN", "AUX", "NUL", *("COM" + str(i) for i in range(1, 10)),
                *("LPT" + str(i) for i in range(1, 10))}
    if (not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,127}", value)
            or value.upper() in reserved):
        raise ValueError("Ungültige oder nicht dateisichere Werkzeugaufruf-ID.")
    return value


def _kind(tool_name, tool_input):
    if tool_name in CHAT_TOOLS:
        return CHAT_TOOLS[tool_name]
    if tool_name in WEB_TOOLS:
        return "web_search" if isinstance(tool_input, dict) and tool_input.get("search_query") else "web_open"
    if tool_name in {"tool_search", "functions.tool_search", "mcp__functions__tool_search"}:
        return "tool_discovery"
    return "other"


def _directory(root, session_id, turn_id):
    root = Path(root).resolve()
    path = root / "work/codex/sessions" / _uuid(session_id) / "receipts" / _uuid(turn_id)
    if not path.resolve().is_relative_to(root):
        raise ValueError("Werkzeugbeleg verlässt das autorisierte Arbeitsrepository.")
    return path


def _error_payload(value):
    return (isinstance(value, dict) and (
        value.get("isError") is True or value.get("success") is False
        or isinstance(value.get("status"), str) and value["status"] in {"ERROR", "error", "FAILED", "failed"}
        or bool(value.get("error"))))


def _mcp_payloads(response):
    if not isinstance(response, dict):
        return []
    structured = response.get("structuredContent")
    if isinstance(structured, (dict, list)):
        return [structured]
    content = response.get("content", [])
    payloads = []
    if isinstance(content, list):
        for block in content[:32]:
            if not isinstance(block, dict) or block.get("type") != "text" or not isinstance(block.get("text"), str):
                continue
            try:
                value = json.loads(block["text"])
            except (ValueError, TypeError, RecursionError):
                continue
            if isinstance(value, (dict, list)):
                payloads.append(value)
    return payloads


def _chat_entries(payloads, kind):
    entries, seen = [], set()
    budget = [4096]
    truncated = [False]
    recognized = [False]
    def entry(value):
        if not isinstance(value, dict):
            return
        title = value.get("title")
        identity = next((value.get(name) for name in ("threadId", "thread_id", "id")
                         if isinstance(value.get(name), str) and value[name]), None)
        if not isinstance(title, str) or not title.strip() or not identity:
            return
        if len(title) > 512 or len(identity) > 200:
            truncated[0] = True
            return
        item = {"title": title, "id": identity}
        if isinstance(value.get("url"), str) and len(value["url"]) <= 2048:
            item["url"] = value["url"]
        key = _json_bytes(item)
        if key not in seen:
            if len(entries) < MAX_ENTRIES:
                entries.append(item)
                seen.add(key)
            else:
                truncated[0] = True

    def walk(value, depth=0):
        budget[0] -= 1
        if depth > 8 or budget[0] < 0:
            truncated[0] = True
            return
        if not isinstance(value, dict):
            return
        # Only documented thread containers and result wrappers carry titles.
        # Project/metadata/turn/message titles and summaries are never promoted.
        if kind == "chat_read" and depth == 0 and any(name in value for name in ("threadId", "thread_id")):
            recognized[0] = True
            entry(value)
        if kind == "chat_read" and isinstance(value.get("thread"), dict):
            recognized[0] = True
            entry(value["thread"])
        for name in ("threads", "pinnedThreads", "archivedThreads"):
            children = value.get(name)
            if isinstance(children, list):
                recognized[0] = True
                if len(children) > 256:
                    truncated[0] = True
                for child in children[:256]:
                    entry(child)
        for name in ("data", "result"):
            if isinstance(value.get(name), dict):
                walk(value[name], depth + 1)

    for payload in payloads:
        walk(payload)
    return entries, truncated[0], recognized[0]


def _read_receipt(path, session_id, turn_id):
    if path.is_symlink() or not path.is_file() or path.stat().st_size > MAX_RECEIPT_BYTES:
        raise ValueError("Werkzeugbeleg fehlt oder überschreitet die feste Grenze.")
    value = json.loads(path.read_bytes().decode("utf-8"))
    if not isinstance(value, dict):
        raise ValueError("Ungültiger Werkzeugbeleg.")
    digest = value.get("receipt_sha256")
    body = {key: item for key, item in value.items() if key != "receipt_sha256"}
    if (digest != _sha(body) or value.get("source") != "native_post_tool_use"
            or value.get("session_id") != session_id or value.get("turn_id") != turn_id
            or _use_id(value.get("tool_use_id")) != path.stem
            or value.get("kind") != _kind(value.get("tool_name"), value.get("kind_input", {}))):
        raise ValueError("Werkzeugbeleg stimmt nicht mit seinem Inhalt oder Turn überein.")
    return value


def _require_evidence_permission(root, session_id):
    from .codex_hook import _config
    config = _config(Path(root), session_id, required=True)
    if session_id not in config.get('action_evidence_session_ids', []):
        raise ValueError('Keine aktuelle ausdrückliche Belegfreigabe für diese Sitzung.')


def record_tool_result(root, session_id, turn_id, tool_name, tool_use_id, tool_input, tool_response):
    """Record one native event. The root hook owns provenance of these arguments."""
    session_id, turn_id, tool_use_id = _uuid(session_id), _uuid(turn_id), _use_id(tool_use_id)
    _require_evidence_permission(root, session_id)
    if not isinstance(tool_name, str) or not re.fullmatch(r"[A-Za-z0-9_.:-]{1,180}", tool_name):
        raise ValueError("Ungültiger nativer Werkzeugname.")
    input_bytes, result_bytes = _json_bytes(tool_input), _json_bytes(tool_response)
    if len(input_bytes) > MAX_INPUT_BYTES or len(result_bytes) > MAX_RESULT_BYTES:
        raise ValueError("Werkzeugeingabe oder Ergebnis überschreitet die Receipt-Grenze.")
    kind = _kind(tool_name, tool_input)
    payloads = _mcp_payloads(tool_response) if kind in CHAT_KINDS else []
    entries, truncated, recognized = _chat_entries(payloads, kind) if kind in CHAT_KINDS else ([], False, False)
    error = bool(_error_payload(tool_response) or any(_error_payload(payload) for payload in payloads))
    valid_result = (isinstance(tool_response, dict) and (
        isinstance(tool_response.get("content"), list)
        or isinstance(tool_response.get("structuredContent"), (dict, list))))
    if kind in CHAT_KINDS:
        valid_result = valid_result and recognized
    identity = dict(session_id=session_id, turn_id=turn_id, tool_name=tool_name,
                    tool_use_id=tool_use_id, input_sha256=hashlib.sha256(input_bytes).hexdigest(),
                    result_sha256=hashlib.sha256(result_bytes).hexdigest())
    directory = _directory(root, session_id, turn_id)
    path = directory / (tool_use_id + ".json")

    def duplicate():
        existing = _read_receipt(path, session_id, turn_id)
        if any(existing.get(key) != value for key, value in identity.items()):
            raise ValueError("Werkzeugaufruf-ID wurde mit abweichendem Inhalt erneut verwendet.")
        return dict(status="DUPLICATE", receipt_path=str(path), tool_use_id=tool_use_id)

    if path.exists():
        return duplicate()
    directory.mkdir(parents=True, exist_ok=True)
    if not directory.resolve().is_relative_to(Path(root).resolve()):
        raise ValueError("Receipt-Verzeichnis verlässt das Arbeitsrepository.")
    if len(list(directory.glob("*.json"))) >= MAX_RECEIPTS:
        raise ValueError("Zu viele Werkzeugbelege in einem Turn.")
    receipt = dict(version=1, source="native_post_tool_use", **identity, kind=kind,
                   kind_input={"search_query": True} if kind == "web_search" else {},
                   error=error, success=not error and valid_result, entries=entries,
                   extraction_truncated=truncated, structured_result=bool(payloads),
                   chat_payload_recognized=recognized,
                   created_at=datetime.now(timezone.utc).isoformat())
    receipt["receipt_sha256"] = _sha(receipt)
    data = _json_bytes(receipt)
    if len(data) > MAX_RECEIPT_BYTES:
        raise ValueError("Der begrenzte Werkzeugbeleg ist zu groß.")
    temporary = directory / ("." + uuid.uuid4().hex + ".tmp")
    try:
        with temporary.open("xb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        try:
            # Exclusive atomic publication: a competing event cannot replace an
            # existing ID. Unsupported filesystems fail closed, without fallback.
            os.link(temporary, path)
        except FileExistsError:
            return duplicate()
    finally:
        temporary.unlink(missing_ok=True)
    return dict(status="RECORDED", receipt_path=str(path), tool_use_id=tool_use_id,
                kind=kind, error=error)


def _mask_examples(text):
    def blank(match):
        return re.sub(r"[^\n]", " ", match.group(0))
    text = re.sub(r"```[\s\S]*?```", blank, text)
    text = re.sub(r"(?m)^\s*>[^\n]*", blank, text)
    return text


def _narrative(text):
    # Preserve quotes in the original context for exact-title extraction, but
    # do not mistake words inside a title or quotation for the speaker's claim.
    blank = lambda match: " " * len(match.group(0))
    return re.sub(r"\*\*[^\n]*?\*\*", blank, _QUOTES.sub(blank, text))


def _title_at_start(value):
    value = value.strip()
    for pattern in (r"\*\*(.+?)\*\*", r"„([^“]+)“", r"“([^”]+)”", r'"([^"\n]+)"',
                    r"'([^'\n]+)'", r"`([^`\n]+)`"):
        match = re.match(pattern, value)
        if match:
            title = match.group(1)
            return title if len(title) <= 512 else None
    return None


def _titles(context, result_claim):
    titles, complete = [], True

    def add(value, allow_plain=False):
        nonlocal complete
        title = _title_at_start(value)
        if title is None and allow_plain:
            raw = value.strip().rstrip(" .;")
            if raw and len(raw) <= 512 and not re.search(r"[\n:*]", raw):
                title = raw
        if title and title not in titles:
            titles.append(title)
        elif title is None:
            complete = False

    def finish():
        # A second inline name must not disappear behind a successful first
        # match, including within one bullet. Unsupported combinations remain
        # unverified rather than assuming every quoted/bold name was checked.
        formatted = list(re.finditer(r"\*\*[^\n]*?\*\*", context)) + list(_QUOTES.finditer(context))
        all_formatted = all(_title_at_start(match.group(0)) in titles for match in formatted)
        return titles[:MAX_CLAIMS], complete and bool(titles) and len(titles) <= MAX_CLAIMS and all_formatted

    bullets = re.findall(r"(?m)^\s*(?:[-*]|\d+[.)])\s+(.+)$", context)
    if bullets:
        for value in bullets:
            add(value)
        return finish()
    for labelled in _TITLE_LABEL.finditer(context):
        add(labelled.group(1), allow_plain=True)
    if not titles and result_claim:
        named = re.search(r"\bchat\s+(?:mit\s+dem\s+titel\s+)?(.+?)\s+"
                          r"(?:gefunden|verifiziert|überprüft|geprüft)\b", context, re.I)
        if named and not re.match(r"(?:in|auf|unter|aus|bei|dort)\b", named.group(1), re.I):
            add(named.group(1), allow_plain=True)
        if not titles:
            for match in re.finditer(r"\b(?:gefunden|verifiziert|überprüft|geprüft)\s*:\s*([^\n]+)", context, re.I):
                add(match.group(1))
        if not titles:
            for line in context.splitlines():
                if _title_at_start(line):
                    add(line)
    return finish()


def _claims(text):
    paragraphs = re.split(r"\n\s*\n", _mask_examples(text))
    claims = []
    for number, paragraph in enumerate(paragraphs):
        narrative = _narrative(paragraph)
        if _EXAMPLE.search(narrative):
            continue
        matches = list(_FIRST_PERSON.finditer(narrative))
        candidates = [(match.start(), match.end(), matches[index + 1].start() if index + 1 < len(matches)
                       else len(paragraph)) for index, match in enumerate(matches)]
        title_assertion = _TITLE_LABEL.search(narrative)
        if not candidates and (_CHAT.search(narrative) and re.search(r"\bgefunden\s*:", narrative, re.I)
                               or title_assertion):
            candidates = [(0, 0, len(paragraph))]
        for start, body_start, end in candidates:
            chunk = paragraph[start:end].strip()
            body = narrative[body_start:end]
            verbs = [match.group(1).lower()
                     for clause in re.split(r"[,;.!?\n]|\b(?:und|aber|sondern)\b", body, flags=re.I)
                     if not _QUALIFIED.search(clause) for match in _ACTION.finditer(clause)]
            if not verbs and not title_assertion:
                continue
            if title_assertion and not verbs and _QUALIFIED.search(body):
                continue
            context = chunk
            if _CHAT.search(chunk) and number + 1 < len(paragraphs) and len(paragraphs[number + 1]) <= 700:
                context += "\n" + paragraphs[number + 1]
            result_claim = bool(title_assertion or any(verb in {
                "gefunden", "verifiziert", "geprüft", "überprüft", "prüfte", "prüften",
                "überprüfte", "überprüften", "fand", "fanden", "ergab"} for verb in verbs))
            titles, title_complete = _titles(context, result_claim)
            kind = "chat" if _CHAT.search(context) else "web" if (
                _WEB.search(context) or any("recherchiert" in verb for verb in verbs)) else "unknown"
            claims.append(dict(kind=kind, verbs=verbs, text=context[:2000],
                               title=titles[0] if titles else None, titles=titles,
                               title_complete=title_complete, result_claim=result_claim or bool(titles)))
            if len(claims) > MAX_CLAIMS:
                return claims[:MAX_CLAIMS], True
    return claims, False


def _turn_receipts(root, session_id, turn_id):
    directory = _directory(root, session_id, turn_id)
    if not directory.is_dir():
        return [], []
    paths = sorted(directory.glob("*.json"))
    if len(paths) > MAX_RECEIPTS:
        return [], ["Zu viele Werkzeugbelege für eine begrenzte Prüfung."]
    receipts, errors = [], []
    for path in paths:
        try:
            receipts.append(_read_receipt(path, session_id, turn_id))
        except (OSError, ValueError, TypeError, UnicodeError, RecursionError) as exc:
            errors.append(str(exc)[:300])
    return receipts, errors


def check_action_claims(root, session_id, turn_id, text):
    """Check only observed actions/title fields; a successful check is not semantic verification."""
    base = dict(findings=[], claims=[], checked=False, scope=SCOPE, semantic_verified=False)
    try:
        if not isinstance(text, str) or len(text.encode("utf-8")) > 65536:
            raise ValueError("Aktionsbehauptungen benötigen den vollständigen begrenzten Antworttext.")
        claims, overflow = _claims(text)
        if not claims:
            return dict(base, status="SKIPPED")
        if overflow:
            return dict(base, status="UNVERIFIED", claims=claims,
                        findings=[dict(requirement_id="ACTION_EVIDENCE", severity="warning",
                                       description="Zu viele Aktionsbehauptungen; keine vollständige Prüfung.")])
        session_id, turn_id = _uuid(session_id), _uuid(turn_id)
        _require_evidence_permission(root, session_id)
        receipts, receipt_errors = _turn_receipts(root, session_id, turn_id)
        checked_claims, findings = [], []
        for claim in claims:
            status, ids = "UNVERIFIED", []
            reason = "Diese Prüfart ist nicht durch die begrenzte Werkzeugbelegprüfung abgedeckt."
            if claim["kind"] == "chat":
                usable = [receipt for receipt in receipts if receipt["kind"] in CHAT_KINDS
                          and receipt.get("success") is True and receipt.get("error") is False
                          and receipt.get("chat_payload_recognized") is True]
                if re.search(r"\b(?:chatliste|chatarchiv)\b", claim["text"], re.I):
                    # Reading one already known chat does not prove a claimed
                    # list search or a title allegedly found in that list.
                    usable = [receipt for receipt in usable if receipt["kind"] in {"chat_list", "chat_archive"}]
                matches = usable
                if claim["titles"]:
                    missing = [title for title in claim["titles"] if not any(
                        entry.get("title") == title for receipt in usable for entry in receipt.get("entries", []))]
                    matches = [] if missing else [receipt for receipt in usable if any(
                        entry.get("title") in claim["titles"] for entry in receipt.get("entries", []))]
                elif claim["result_claim"]:
                    matches = [receipt for receipt in usable if receipt.get("entries")]
                if matches and claim["result_claim"] and not claim["title_complete"]:
                    status = "UNVERIFIED"
                    reason = "Die behaupteten Fundtitel sind nicht vollständig eindeutig erfasst; keine pauschale Erfolgsfreigabe."
                elif matches:
                    status = "PASS"
                    ids = [receipt["tool_use_id"] for receipt in matches]
                    reason = "Behauptete Aktion beziehungsweise exakter Titel ist im selben nativen Turn belegt."
                elif any(receipt.get("extraction_truncated") for receipt in usable):
                    status = "UNVERIFIED"
                    reason = "Der strukturierte Ergebnisumfang überschreitet die vollständige Receipt-Prüfung."
                else:
                    status = "FAIL"
                    reason = "Behaupteter Chat-Sucherfolg oder exakter Titel hat keinen passenden erfolgreichen nativen Beleg im selben Turn."
            elif claim["kind"] == "web" and not claim["result_claim"]:
                matches = [receipt for receipt in receipts if receipt["kind"] == "web_search"
                           and receipt.get("success") is True and receipt.get("error") is False]
                if matches:
                    status, ids = "PASS", [receipt["tool_use_id"] for receipt in matches]
                    reason = "Nur die protokollierte Suchaktion ist belegt; ihr Rechercheergebnis bleibt semantisch ungeprüft."
                else:
                    reason = "Für diese Recherche liegt kein sichtbarer nativer Suchbeleg vor; nicht alle Webwerkzeuge liefern PostToolUse-Ereignisse."
            checked_claims.append(dict(claim, status=status, receipt_ids=ids, reason=reason))
            if status != "PASS":
                findings.append(dict(requirement_id="ACTION_EVIDENCE", severity="error" if status == "FAIL" else "warning",
                                     description=reason, evidence=claim["text"],
                                     correction="Nur tatsächlich belegte Aktionen und Titel als bestätigt ausgeben; ungeprüfte Angaben kennzeichnen."))
        statuses = {claim["status"] for claim in checked_claims}
        status = "FAIL" if "FAIL" in statuses else "UNVERIFIED" if "UNVERIFIED" in statuses else "PASS"
        return dict(base, status=status, claims=checked_claims, findings=findings,
                    checked=any(claim["status"] != "UNVERIFIED" for claim in checked_claims),
                    receipt_errors=receipt_errors)
    except (OSError, ValueError, TypeError, UnicodeError, RecursionError) as exc:
        return dict(base, status="UNVERIFIED", findings=[dict(requirement_id="ACTION_EVIDENCE", severity="warning",
                                                             description=str(exc)[:1000])])
