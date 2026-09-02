"""C30 EntityExtractor - BR-64~66, FR-17.

Rules run first and, when they find anything, **the LLM is not called** (BR-64).
CAS and UN numbers are regular languages; spending a model call plus its latency
on "7664-93-9" would be paying for a worse answer.

The LLM path exists only for questions where no identifier and no known
substance name appears at all.
"""

from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path

import yaml
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.logging import get_logger
from app.core.types import DocType
from app.db.models import SubstanceSynonym
from app.rag.assembler import PromptAssembler
from app.rag.types import QueryIntent

log = get_logger(__name__)

# Query-side aliases (BR-65a). `substance_synonym` carries only names the
# source publishes (BR-99) - correct for cards, blind for queries: u4 measured
# sub-05 ("메탄올...") resolving to nothing because the master only knows
# 메틸알코올. These map a user's word to the canonical term at query time and
# are stored nowhere; an alias whose canonical is absent from the master
# silently resolves to a term that matches nothing, which is the no-op it
# should be.
_ALIAS_PATH = Path(__file__).resolve().parents[2] / "config" / "query_aliases.yaml"


@lru_cache(maxsize=1)
def _query_aliases() -> dict[str, str]:
    try:
        raw = yaml.safe_load(_ALIAS_PATH.read_text(encoding="utf-8")) or {}
    except FileNotFoundError:
        return {}
    return {str(k): str(v) for k, v in (raw.get("aliases") or {}).items()}


CAS_PATTERN = re.compile(r"\b\d{2,7}-\d{2}-\d\b")
UN_PATTERN = re.compile(r"\bUN\s?(\d{4})\b", re.IGNORECASE)

_ENTITY_SCHEMA = {
    "type": "object",
    "properties": {
        "substance_names": {"type": "array", "items": {"type": "string"}},
        "raw_terms": {"type": "array", "items": {"type": "string"}},
        "doc_type_hint": {"type": ["string", "null"], "enum": ["law", "msds", "incident", None]},
    },
    "required": ["substance_names", "raw_terms"],
    "additionalProperties": False,
}

# Weak signals only. `doc_type_hint` is a weight, never a filter (BR-66), so a
# wrong guess costs ranking rather than recall.
_HINTS: list[tuple[re.Pattern[str], DocType]] = [
    (re.compile(r"법|법령|조문|규정|기준|의무|처벌"), DocType.LAW),
    (re.compile(r"msds|물질안전보건자료|보호구|취급|저장|응급"), DocType.MSDS),
    (re.compile(r"사고|누출|폭발|화재|사례"), DocType.INCIDENT),
]


class EntityExtractor:
    def __init__(
        self,
        session: Session,
        llm=None,
        assembler: PromptAssembler | None = None,
        settings: Settings | None = None,
    ) -> None:
        self._s = session
        self._llm = llm
        self._assembler = assembler or PromptAssembler()
        self._settings = settings or get_settings()

    def extract(self, normalised_query: str) -> QueryIntent:
        cas = CAS_PATTERN.findall(normalised_query)
        un = UN_PATTERN.findall(normalised_query)
        names = self._match_synonyms(normalised_query)

        intent = QueryIntent(
            substance_names=names,
            cas_numbers=cas,
            un_numbers=un,
            doc_type_hint=self._hint(normalised_query),
            raw_terms=[t for t in normalised_query.split() if len(t) > 1],
        )
        if intent.resolved_by_rules or self._llm is None:
            return intent
        if not self._settings.entity_llm_enabled:
            # Skipped by configuration, and said out loud rather than silently:
            # a disabled enrichment that nobody can see is indistinguishable
            # from a broken one. See `entity_llm_enabled` for the precondition.
            log.info(
                "entity_llm_skipped",
                extra={"reason": "entity_llm_enabled=false", "terms": len(intent.raw_terms)},
            )
            return intent
        return self._extract_with_llm(normalised_query, intent)

    def _match_synonyms(self, query: str) -> list[str]:
        """BR-65 - resolve to the canonical name; leave unknown terms alone.

        An unresolved term still goes to keyword search verbatim. Dropping it
        would lose the only thing the user actually named.
        """
        rows = self._s.execute(
            select(SubstanceSynonym.normalized_term, SubstanceSynonym.term)
        ).all()
        matched: list[str] = []
        lowered = query.lower()
        for normalized_term, term in rows:
            if normalized_term and normalized_term.lower() in lowered:
                matched.append(term)
        for alias, canonical in _query_aliases().items():
            if alias.lower() in lowered and canonical not in matched:
                matched.append(canonical)
        return matched

    @staticmethod
    def _hint(query: str) -> DocType | None:
        for pattern, doc_type in _HINTS:
            if pattern.search(query):
                return doc_type
        return None

    def _extract_with_llm(self, query: str, fallback: QueryIntent) -> QueryIntent:
        prompt = self._assembler.for_entity(query)
        try:
            payload, _ = self._llm.generate_structured(
                prompt.user, _ENTITY_SCHEMA, prompt.system
            )
        except Exception as exc:  # noqa: BLE001
            # Entity extraction is an optimisation. Losing it degrades ranking;
            # failing the query over it would be disproportionate.
            log.warning("entity_extraction_failed", extra={"error": str(exc)})
            return fallback

        payload = payload or {}
        hint = payload.get("doc_type_hint")
        try:
            doc_type_hint = DocType(hint) if hint else fallback.doc_type_hint
        except ValueError:
            doc_type_hint = fallback.doc_type_hint
        return QueryIntent(
            substance_names=[str(n) for n in payload.get("substance_names") or []],
            cas_numbers=fallback.cas_numbers,
            un_numbers=fallback.un_numbers,
            doc_type_hint=doc_type_hint,
            raw_terms=[str(t) for t in payload.get("raw_terms") or []] or fallback.raw_terms,
        )
