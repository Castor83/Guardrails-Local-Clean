"""Strukturierte Eingaben und eng begrenzte, konservative Texterkennung."""
import json
import re
from pathlib import Path
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field


MODEL = 'huihui_ai/gpt-oss-abliterated:20b-mxfp4'
CORE_METHODS = {
    'LOCAL_ONLY': 'local_execution', 'NO_PAID_API': 'no_paid_api',
    'ABLITERATED': 'catalog_provenance', 'HARDWARE': 'documented_resources',
    'EVIDENCE': 'evidence_binding', 'PROJECT_POLICY': 'project_rules',
    'SEMANTIC_REVIEW': 'critic', 'INDEPENDENCE': 'model_family',
}


class Recommendation(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    model: str = Field(min_length=1, max_length=300)
    execution: Literal['local', 'cloud_api', 'unknown'] = 'unknown'
    context_tokens: int | None = Field(default=None, ge=1, le=1048576)
    estimated_vram_gb: float | int | None = Field(default=None, ge=0, le=10000)
    evidence_quote: str = Field(min_length=1, max_length=32000)


class Draft(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    text: str = Field(min_length=1, max_length=32000)
    source: str = Field(default='manual', max_length=200)
    task: str = Field(default='Modell- und API-Empfehlung prüfen', max_length=6000)
    developer_family: str | None = Field(default=None, max_length=100)
    recommendations: list[Recommendation] = Field(default_factory=list, max_length=30)
    extraction_status: str = 'unknown'
    fixture_generated: bool = False


def load_requirements(root: Path) -> list:
    value = json.loads((Path(root) / 'config/requirements.json').read_text(encoding='utf-8-sig'))
    return value['requirements']


def load_catalog(root: Path) -> dict:
    return json.loads((Path(root) / 'config/catalog.json').read_text(encoding='utf-8-sig'))


def analyze_text(text: str) -> dict:
    """Preserve recognized selections, without certifying unparsed surrounding prose."""
    recs, unknown, rename = [], [], False
    blank = lambda match: re.sub(r'[^\r\n]', ' ', match.group(0))
    masked = re.sub(r'```[\s\S]*?(?:```|$)', blank, text)
    masked = re.sub(r'(?m)^\s*>[^\n]*', blank, masked)
    masked = re.sub(r'„[^“]*(?:“|$)|“[^”]*(?:”|$)|"[^"]*(?:"|$)|`[^`]*(?:`|$)', blank, masked)
    masked = re.sub(r"(?<!\w)'[^']*(?:'|$)", blank, masked)
    if masked != text:
        unknown.append(text)
    role = re.compile(r'\b(?:negativbeispiel|negatives?\s+beispiel|beispiel|zitat)\b|'
                      r'\b(?:nicht\s+ausführen|(?:befolge|verwende|nutze)\s+niemals)\b|'
                      r'\b(?:folgende|diese)\s+(?:empfehlung|anweisung|aussage)\s+(?:ist|sei|wäre)\s+'
                      r'(?:falsch|verboten|unzulässig)\b|\bkeine?\s+(?:empfehlung|auswahl)\b', re.I)
    blocks = []
    for block in re.split(r'\r?\n[ \t]*\r?\n', masked):
        if role.search(block):
            unknown.append(block)
            blocks.append('')
        else:
            blocks.append(block)
    masked = '\n\n'.join(blocks)
    sentences = [s.strip() for s in re.split(r'(?<=[.!?])\s+|[\r\n]+', masked) if s.strip()]
    for sentence in sentences:
        if re.fullmatch(r'Verwende keine OpenAI-API\.?', sentence, re.I) or re.fullmatch(
                r'Stattdessen soll Ollama lokal eingesetzt werden\.?', sentence, re.I):
            continue
        if re.fullmatch(r'Verwende ein reguläres Modell und benenne es in model-abliterated um\.?', sentence, re.I):
            rename = True
            continue
        local = re.fullmatch(r'(?:Verwende|Nutze) (\S+) lokal über Ollama(?: mit Kontext (\d+))?\.?', sentence, re.I)
        if local:
            recs.append(dict(model=local[1].rstrip('.'), execution='local',
                             context_tokens=int(local[2]) if local[2] else None,
                             estimated_vram_gb=None, evidence_quote=sentence))
            continue
        cloud = re.fullmatch(r'(?:Installiere|Verwende|Nutze|Empfehle)\s+GPT-4o\s+über (?:die )?OpenAI-API\.?', sentence, re.I)
        if cloud:
            recs.append(dict(model='gpt-4o', execution='cloud_api', context_tokens=None,
                             estimated_vram_gb=None, evidence_quote=sentence))
            # Nur genau dieser Satz ist vollständig deterministisch erfasst.
            if not re.fullmatch(r'(?:Installiere|Verwende|Nutze|Empfehle) GPT-4o über (?:die )?OpenAI-API\.?', sentence, re.I):
                unknown.append(sentence)
            continue
        if re.fullmatch(r'Die Ausführung erfolgt vollständig lokal und kostenlos\.?', sentence, re.I):
            # Wird unten an die vorangehende Cloud-Empfehlung gebunden.
            if not any(r['model'] == 'gpt-4o' for r in recs):
                unknown.append(sentence)
            continue
        unknown.append(sentence)
    # A recognized violation survives unrelated prose. Explicit preceding
    # example/warning roles and quotations still suppress selections; the
    # remaining unknown text prevents a general PASS in downstream validators.
    return dict(recommendations=recs, unknown=unknown, rename=rename)


def import_text(text: str, source='manual', task='Modell- und API-Empfehlung prüfen') -> dict:
    parsed = analyze_text(text)
    return dict(text=text, source=source, task=task, recommendations=parsed['recommendations'],
                extraction_status='partial' if parsed['unknown'] else 'complete')
