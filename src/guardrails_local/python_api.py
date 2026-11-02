"""Eng begrenzte Python-API-Prüfung; Benutzertext wird ausschließlich geparst."""
import ast
import re


_IMPORT_START = re.compile(
    r'^(?:import guardrails as [A-Za-z_]\w*|from guardrails import Guard(?: as [A-Za-z_]\w*)?)\s*(?:#.*)?$'
)


def _python_fragment(text):
    lines = text.splitlines(keepends=True)
    fences = [i for i, line in enumerate(lines) if line.strip().startswith('```')]
    if fences:
        if (len(fences) != 2 or lines[fences[0]].strip() != '```python'
                or lines[fences[1]].strip() != '```'):
            return None
        start, end = fences
        return ''.join(lines[start + 1:end]), start + 1
    try:
        ast.parse(text)
        return text, 0
    except (SyntaxError, ValueError, RecursionError):
        pass
    for start, line in enumerate(lines):
        if _IMPORT_START.fullmatch(line.rstrip('\r\n')):
            prefix = ''.join(lines[:start])
            if ('"""' in prefix or "'''" in prefix
                    or any(re.match(r'^\s*(?:import|from)\s', part) for part in lines[:start])):
                return None
            return ''.join(lines[start:]), start
    return None


def _binding_root(target):
    while isinstance(target, (ast.Attribute, ast.Subscript)):
        target = target.value
    return target.id if isinstance(target, ast.Name) else None


def _missing_call(value, aliases):
    if not isinstance(value, ast.Call) or not isinstance(value.func, ast.Attribute):
        return False
    if value.func.attr != 'from_string':
        return False
    owner = value.func.value
    if isinstance(owner, ast.Name):
        return aliases.get(owner.id) == 'guard'
    return (isinstance(owner, ast.Attribute) and owner.attr == 'Guard'
            and isinstance(owner.value, ast.Name)
            and aliases.get(owner.value.id) == 'module')


def check_python_apis(text: str, facts: dict) -> list[dict]:
    """Meldet nur belegte fehlende APIs in eindeutig gebundenen Top-Level-Calls.

    Leere Befunde bedeuten keine allgemeine Freigabe des Textes oder Codes.
    """
    software = facts.get('software_evidence', {}) if isinstance(facts, dict) else {}
    if (not isinstance(software, dict) or software.get('guardrails_ai_version') != '0.11.0'
            or software.get('guard_from_string_available') is not False):
        return []
    fragment = _python_fragment(text)
    if fragment is None:
        return []
    source, line_offset = fragment
    try:
        tree = ast.parse(source)
    except (SyntaxError, ValueError, RecursionError):
        return []
    aliases, findings = {}, []
    for statement in tree.body:
        if isinstance(statement, (ast.Import, ast.ImportFrom)):
            if isinstance(statement, ast.ImportFrom) and any(a.name == '*' for a in statement.names):
                break
            for item in statement.names:
                name = item.asname or item.name.split('.')[0]
                aliases.pop(name, None)
                if isinstance(statement, ast.Import) and item.name == 'guardrails' and item.asname:
                    aliases[name] = 'module'
                elif (isinstance(statement, ast.ImportFrom) and statement.module == 'guardrails'
                      and statement.level == 0 and item.name == 'Guard'):
                    aliases[name] = 'guard'
            continue
        if not isinstance(statement, (ast.Expr, ast.Assign, ast.AnnAssign, ast.Delete, ast.AugAssign)):
            break  # Keine Bindungsannahmen nach unbekannten oder verschachtelten Scopes.
        value = getattr(statement, 'value', None)
        missing = _missing_call(value, aliases)
        if missing:
            segment = ast.get_source_segment(source, value) or 'Guard.from_string(...)'
            findings.append(dict(
                requirement_id='EVIDENCE', severity='error',
                description='Aufruf von Guard.from_string ist in der lokal belegten Guardrails-Version nicht vorhanden.',
                evidence=f'Zeile {line_offset + value.lineno}: {segment}\nLokaler Beleg: guardrails-ai 0.11.0; guard_from_string_available=False.',
                correction='Guard.for_string(...) statt Guard.from_string(...) verwenden und die übrigen Validatorabhängigkeiten separat prüfen.',
            ))
        targets = getattr(statement, 'targets', [getattr(statement, 'target', None)])
        for target in targets:
            for part in ast.walk(target) if target is not None else []:
                if isinstance(part, (ast.Attribute, ast.Subscript)):
                    return findings  # Mutationen können auch die Importauflösung verändern.
                if isinstance(part, (ast.Name, ast.Attribute, ast.Subscript)):
                    aliases.pop(_binding_root(part), None)
        if missing or any(isinstance(n, (ast.Call, ast.NamedExpr)) for n in ast.walk(statement)):
            break  # Unbekannte Aufrufe könnten spätere Bindungen verändern.
    return findings
