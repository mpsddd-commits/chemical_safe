"""C26 KeywordIndex (FR-12, BR-38).

Exact identifier matching is the reason this exists. A CAS number like
"7664-93-9" is meaningless to a vector model and gets shredded by most text
search configurations, yet it is the most precise thing a user can type. So
identifiers are matched against indexed JSON expressions, and only free text
goes through full-text search.
"""

from __future__ import annotations

import re

from sqlalchemy import Float, func, literal, or_, select
from sqlalchemy import text as sql_text
from sqlalchemy.dialects.postgresql import REGCONFIG
from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.core.types import Candidate, Scope
from app.db.models import ChunkRow
from app.indexing.vector_index import MetaFilter, apply_meta_filter, apply_scope

log = get_logger(__name__)

CAS_PATTERN = re.compile(r"\b\d{2,7}-\d{2}-\d\b")
UN_PATTERN = re.compile(r"\bUN\s?(\d{4})\b", re.IGNORECASE)

# 'simple' rather than a language configuration: Korean is not stemmed by any
# stock PostgreSQL config, and 'simple' at least leaves identifiers intact.
FTS_CONFIG = "simple"

# The score `lookup_exact` assigns. A CAS or UN number is a fact the user typed,
# not a fuzzy signal, so downstream needs to be able to tell such a hit apart
# from a text-search hit (BR-38).
EXACT_MATCH_SCORE = 1.0

# BR-65a - which record section a query's wording points at. A substance
# record has seven chunks and a name resolves to all of them equally; the
# question usually names the exposure route ("흡입하면", "눈에 들어가면"),
# and that word is the only thing that can break the tie. Measured before
# this existed: the record surfaced but the *wrong sections* took the fused
# top 5, and sub-02/06/08 stayed at recall 0.000 with the evidence in hand.
_ROUTE_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"흡입|들이마시|증기|가스를 마시"), "substance_inhale"),
    (re.compile(r"눈|안구|시각|시야"), "substance_eye"),
    (re.compile(r"피부|접촉 시"), "substance_skin"),
    (re.compile(r"삼키|삼켰|섭취|먹었|먹으면|마셨"), "substance_oral"),
]

# The MSDS half of the same idea (2026-09-02). The CAS-meta lookup sweeps a
# vendor MSDS's sixteen chunks along with the record's seven - both carry the
# substance's CAS - and a question about storage or protective gear points at
# an MSDS section no substance record has. Without this map, "황산은 어떻게
# 저장해야 하나요" lifted 법적규제/참고사항 chunks at 1.0: nothing matched, the
# tie among 23 equal chunks broke on row order, and msds-02 measured 0.000
# with its evidence (msds_07) sitting unlifted in the same CAS sweep.
_MSDS_TOPIC_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"저장|보관|취급"), "msds_07"),
    (re.compile(r"보호구|노출방지|노출기준"), "msds_08"),
    (re.compile(r"응급조치|응급"), "msds_04"),
    (re.compile(r"화재|폭발|소화"), "msds_05"),
    (re.compile(r"누출"), "msds_06"),
    (re.compile(r"폐기"), "msds_13"),
    (re.compile(r"운송"), "msds_14"),
    (re.compile(r"물리화학|끓는점|녹는점|인화점"), "msds_09"),
]

# Ordering within a resolved record when the route section is decided (or
# absent): general symptoms outrank identity, identity outranks the rest.
# `substance_symptom` is the section that answers "노출되면 어떻게 되나요".
_SECTION_FALLBACK_PRIORITY = ("substance_symptom", "substance_identity")

# How many chunks of a name-resolved record may enter the candidate list.
# All seven at a flat score crowded out MSDS evidence - msds-01 went from
# recall 1.000 to 0.000 the day the flood shipped. Three leaves room for the
# text hits the question also deserves. Typed CAS (BR-38) is not capped:
# an identifier the user typed is an explicit request for the record.
_RESOLVED_NAME_LIMIT = 3

# Section-title tier (2026-09-02). Between the identifier band (1.0) and the
# body ts_rank band (~0.03-0.10): a title naming the query's compound noun is
# stronger evidence than term frequency in a body, weaker than an identifier
# the user typed. Five body-prefix variants were measured first and every one
# was zero-sum (runs 277-282); the title LIKE is precise where they were broad.
_TITLE_MATCH_SCORE = 0.3
_TITLE_TERM_MIN_CHARS = 5
_TITLE_TIER_LIMIT = 5

# The configuration argument is `regconfig`, not text. Binding it as VARCHAR -
# which is what a bare `literal()` does - produces
# `function to_tsvector(character varying, text) does not exist`, and every
# keyword search fails. u1 shipped it that way: its tests mock the session and
# Build & Test exercised indexing rather than searching, so nothing ever ran
# this statement against PostgreSQL. Found in u2 on the first real query.
_CONFIG = literal(FTS_CONFIG, type_=REGCONFIG)


class KeywordIndex:
    def __init__(self, session: Session) -> None:
        self._s = session

    def lookup_exact(self, term: str, field: str, scope: Scope, limit: int = 50) -> list[Candidate]:
        """BR-38 - identifier lookup that never goes through tokenisation."""
        if field not in {"cas_number", "un_number"}:
            raise ValueError(f"unsupported exact field: {field!r}")
        stmt = select(ChunkRow.id).where(ChunkRow.meta[field].astext == term)
        stmt = apply_scope(stmt, scope)
        rows = self._s.execute(stmt.limit(limit)).all()
        return [
            Candidate(chunk_id=row[0], score=EXACT_MATCH_SCORE, route="keyword")
            for row in rows
        ]

    def search(
        self,
        query: str,
        top_k: int,
        filters: MetaFilter,
        scope: Scope,
        resolved_cas: tuple[str, ...] = (),
    ) -> list[Candidate]:
        """`resolved_cas` - CAS numbers resolved from substance names (BR-65a).

        A substance record's chunks never contain the substance's name: the
        황산 inhale chunk reads "·심각한 기도 자극..." and the name lives only
        in the master. So a name query cannot reach those chunks through text
        or vector search - measured on u4's golden set as CAS queries 3/3
        against name queries 0/5. The caller resolves the name to its CAS and
        this method feeds it through the same exact-match path the typed CAS
        already takes.
        """
        identifiers = self._extract_identifiers(query)
        results: dict[int, float] = {}

        # Exact identifier hits rank above anything the text search returns.
        # `EXACT_MATCH_SCORE` is the marker downstream reads: `ts_rank` values
        # sit around 0.03~0.10 on this corpus, so 1.0 is unambiguous.
        for field, value in identifiers:
            for candidate in self.lookup_exact(value, field, scope, limit=top_k):
                results[candidate.chunk_id] = EXACT_MATCH_SCORE
        if resolved_cas:
            route_section = self._route_section(query)
            for value in resolved_cas:
                for chunk_id in self._resolved_record_chunks(
                    value, route_section, scope, query
                ):
                    results.setdefault(chunk_id, EXACT_MATCH_SCORE)

        cleaned = self._strip_identifiers(query)
        terms = self._tsquery_terms(cleaned)

        # Section-title matches sit between identifiers and body-text hits.
        # A statute question usually paraphrases the article TITLE
        # ("공정안전보고서를 제출해야 하는 업종" -> 제43조 "공정안전보고서의
        # 제출 대상"), and LIKE on the title dodges Korean's missing stemmer
        # entirely - the particle problem lives in tsvector lexemes, not in a
        # substring match. Prefix-matching the body (`:*`) was tried first, in
        # five measured variants; every one traded existing recall for new
        # (ts_rank reordering is zero-sum), and the two target questions'
        # evidence never reached the top 5. Titles are the precise instrument:
        # a 5+ character compound noun rarely appears in more than a handful
        # of them.
        for chunk_id, score in self._title_matches(terms, scope):
            results.setdefault(chunk_id, score)

        if terms:
            tsvector = func.to_tsvector(_CONFIG, ChunkRow.text)
            tsquery = func.to_tsquery(_CONFIG, " | ".join(terms))
            rank = func.ts_rank(tsvector, tsquery).cast(Float)
            stmt = select(ChunkRow.id, rank.label("rank")).where(tsvector.op("@@")(tsquery))
            stmt = apply_scope(stmt, scope)
            stmt = apply_meta_filter(stmt, filters)
            stmt = stmt.order_by(rank.desc()).limit(top_k)
            for chunk_id, score in self._s.execute(stmt).all():
                results.setdefault(chunk_id, float(score))

        ordered = sorted(results.items(), key=lambda kv: kv[1], reverse=True)[:top_k]
        return [Candidate(chunk_id=cid, score=score, route="keyword") for cid, score in ordered]

    def _title_matches(
        self, terms: list[str], scope: Scope
    ) -> list[tuple[int, float]]:
        """Chunks whose section title contains a specific query term.

        Only terms of `_TITLE_TERM_MIN_CHARS`+ characters participate: short
        stems ("관리", "제출") appear in dozens of titles and a broad boost is
        the ts_rank reshuffle all over again. Scored `_TITLE_MATCH_SCORE` plus
        the count of matching terms as a tie-break, capped so a common compound
        noun ("유해화학물질" titles ~20 articles of the 화관법) cannot flood
        the head the way the seven equal substance chunks once did (BR-65a).
        """
        long_terms = [t for t in terms if len(t) >= _TITLE_TERM_MIN_CHARS]
        if not long_terms:
            return []
        title = ChunkRow.meta["section_title"].astext
        stmt = select(ChunkRow.id, title).where(
            or_(*[title.like(f"%{t}%") for t in long_terms])
        )
        stmt = apply_scope(stmt, scope)
        rows = self._s.execute(stmt.limit(200)).all()
        scored = [
            (chunk_id, sum(1 for t in long_terms if t in section_title))
            for chunk_id, section_title in rows
            if section_title
        ]
        scored.sort(key=lambda pair: (-pair[1], pair[0]))
        return [
            (chunk_id, _TITLE_MATCH_SCORE + hits * 0.01)
            for chunk_id, hits in scored[:_TITLE_TIER_LIMIT]
        ]

    # ---- helpers ----
    @staticmethod
    def _route_section(query: str) -> str | None:
        for pattern, section in _ROUTE_PATTERNS:
            if pattern.search(query):
                return section
        return None

    @staticmethod
    def _preferred_sections(query: str) -> set[str]:
        """Every section the query's wording points at, substance and MSDS."""
        preferred = {
            section for pattern, section in _ROUTE_PATTERNS if pattern.search(query)
        }
        preferred.update(
            section for pattern, section in _MSDS_TOPIC_PATTERNS if pattern.search(query)
        )
        return preferred

    def _resolved_record_chunks(
        self, cas: str, route_section: str | None, scope: Scope, query: str = ""
    ) -> list[int]:
        """The best few chunks of a name-resolved record, matched section first.

        Order is the whole output: every returned chunk gets the same
        `EXACT_MATCH_SCORE`, `sorted` is stable, and fusion ranks by list
        position - so putting `substance_inhale` first here is what makes an
        inhalation question surface the inhalation section rather than
        whichever of seven equal chunks the dict happened to hold first.

        Chunks that match nothing - no query topic and no fallback - are not
        lifted at all. Lifting them anyway broke the tie among 23 equal-CAS
        chunks on row order and put 법적규제/참고사항 at 1.0 for a storage
        question (measured, msds-02): an arbitrary lift is not a smaller
        version of a right lift, it is noise wearing the exact-match score.
        """
        stmt = select(ChunkRow.id, ChunkRow.meta["section_code"].astext).where(
            ChunkRow.meta["cas_number"].astext == cas
        )
        stmt = apply_scope(stmt, scope)
        rows = self._s.execute(stmt.limit(50)).all()

        preferred = self._preferred_sections(query)
        if route_section:
            preferred.add(route_section)
        droppable = 1 + len(_SECTION_FALLBACK_PRIORITY)

        def priority(section: str | None) -> int:
            if section in preferred:
                return 0
            if section in _SECTION_FALLBACK_PRIORITY:
                return 1 + _SECTION_FALLBACK_PRIORITY.index(section)
            return droppable

        ranked = sorted(
            (row for row in rows if priority(row[1]) < droppable),
            key=lambda row: priority(row[1]),
        )
        return [row[0] for row in ranked[:_RESOLVED_NAME_LIMIT]]

    @staticmethod
    def _extract_identifiers(query: str) -> list[tuple[str, str]]:
        found: list[tuple[str, str]] = []
        for match in CAS_PATTERN.finditer(query):
            found.append(("cas_number", match.group(0)))
        for match in UN_PATTERN.finditer(query):
            found.append(("un_number", match.group(1)))
        return found

    @staticmethod
    def _tsquery_terms(cleaned: str) -> list[str]:
        """Build OR terms, and strip Korean particles from the tail.

        `plainto_tsquery` joins with AND, which makes a natural-language question
        unanswerable here: "황산 취급 시 보호구는?" becomes
        `황산 & 취급 & 시 & 보호구는`, and the `simple` configuration does no
        stemming, so "보호구는" never matches the indexed "보호구". Measured on
        the real corpus, that query returned **0 keyword hits** while the single
        word "보호구" returned 5 - every multi-word question fell back to
        vector-only search without anything reporting a failure.

        OR keeps partial matches, and `ts_rank` still ranks documents matching
        more terms higher. Trailing particles are trimmed because Korean has no
        stemmer in stock PostgreSQL; this is a blunt instrument, and it is what
        makes "보호구는" find "보호구".
        """
        # A conservative list: only endings that cannot begin a content word.
        particles = ("으로는", "에서는", "이라는", "에게는", "까지", "부터", "에서",
                     "으로", "에게", "이나", "라는", "는", "은", "이", "가", "을",
                     "를", "의", "에", "도", "로", "과", "와")
        terms: list[str] = []
        for raw in re.split(r"[^0-9A-Za-z가-힣]+", cleaned):
            token = raw.strip()
            if len(token) < 2:
                continue
            for particle in particles:
                if len(token) > len(particle) + 1 and token.endswith(particle):
                    token = token[: -len(particle)]
                    break
            if len(token) >= 2:
                terms.append(token)
        # Deduplicate while keeping order; `to_tsquery` rejects an empty string.
        seen: set[str] = set()
        return [t for t in terms if not (t in seen or seen.add(t))]

    @staticmethod
    def _strip_identifiers(query: str) -> str:
        stripped = CAS_PATTERN.sub(" ", query)
        stripped = UN_PATTERN.sub(" ", stripped)
        return re.sub(r"\s+", " ", stripped).strip()

    def refresh_statistics(self) -> None:
        """ANALYZE after a bulk load so the planner sees the new distribution."""
        self._s.execute(sql_text("ANALYZE chunk"))
