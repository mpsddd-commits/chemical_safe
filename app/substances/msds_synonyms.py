"""Names an MSDS document prints for its substance - BR-97, BR-99 (revised 2026-09-13).

Backlog D11 measured `substance_synonym` at 49 substances, 98 rows, exactly one
`ko` and one `en` each - not one real synonym - so `H2SO4 저장법` resolved to
nothing although 황산 is held. D11 filled the gap with a separate script, and
that broke BR-97: restoring the corpus by re-indexing from the originals (the
README's promise) would not run the script and the names would silently go -
defect 40's shape. So the extraction lives here and runs **inside the indexing
path**: when an MSDS document is indexed, the names it prints for its one
subject substance are written, owned by that document.

**It invents nothing (BR-99).** Every name is a string the document prints:

  * `msds_title`  - the name in the document title (`X (Y) - 회사`), only when
                    the body prints it too. The title is ours (the manifest);
                    the body is the supplier's.
  * `common_name` - the value of a `관용명 및 이명` / `이명(관용명)` / `동의어`
                    label in **section 3**, only on the row carrying this
                    substance's CAS number. Section 1's free lists are not read:
                    koreachem lists 다이싸이온산 (dithionic acid, a different
                    compound) as a synonym of 황산.
  * `formula`     - the value of a `분자식` / `화학식` label with hyphens
                    removed, only when that exact string also appears verbatim.

and one gate over all three: the name must appear **verbatim in the extracted
text** (`normalize()` output, the text every offset points into). A list that
wraps mid-name ("Cyclohexyl\\nmethacrylate") is split by joining the lines, and
a fragment that only exists because of that join is a string we made - it is
rejected at the value it was cut from, even when the same spelling happens to
be printed somewhere else in the document.

**It is conservative.** The table is matched by substring
(`normalized_term in query`), so a wrong synonym resolves a question to the
wrong substance - one substance's toxicity attached to another (BR-73a). A
candidate is dropped when it is ambiguous (equal to, or contained in, a name of
a different substance, or any name another single-subject MSDS document offers
for a different substance, accepted or not), too short, a generic noun, a
company name, a fragment of an inverted CAS-index name, contained in or
containing the substance's own name (`Butylamine` is printed for
tert-Butylamine and names a different compound), or listed in
`EXCLUDED_TERMS`. Every drop is logged with its reason.

Ambiguity is judged against every single-subject MSDS document in the corpus,
not only the one being indexed, so re-indexing any one document reaches the
same verdict as screening all of them together. A document collected later can
still make an earlier document's name ambiguous; the earlier row stays until
that document is re-indexed, and the query side refuses to resolve a
document-owned name that another substance's name contains in the meantime
(`app/rag/entities.py`).
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field

from sqlalchemy import exists, func, or_
from sqlalchemy.orm import aliased

from app.core.logging import get_logger
from app.core.types import SynonymType
from app.db.models import SubstanceSynonym
from app.processing.stages.normalize import normalize
from app.substances.projection import _normalize_term

log = get_logger(__name__)

# The enum owns the values; `SubstanceLookup` reads every row through it.
MSDS_TITLE = SynonymType.MSDS_TITLE.value
COMMON_NAME = SynonymType.COMMON_NAME.value
FORMULA = SynonymType.FORMULA.value
MSDS_TYPES = (COMMON_NAME, FORMULA, MSDS_TITLE)  # also the keep-one priority

# What an MSDS document owns in `substance_synonym`, and so the only types its
# re-index replaces. Disjoint from the projection's ko/en by a test.
MSDS_SYNONYM_TYPES: frozenset[SynonymType] = frozenset(SynonymType(t) for t in MSDS_TYPES)

# Section 3 is where a name sits in the same row as its CAS number.
COMPOSITION_SECTION = "msds_03"

MIN_LEN = 3  # "한두 글자" - compact length, whitespace removed
MIN_LATIN_LEN = 5  # substring matching makes short Latin tokens hit inside words

GENERIC_NOUNS = frozenset(
    {
        "산", "물", "가스", "용액", "혼합물", "제품", "시약", "물질", "성분",
        "자료없음", "해당없음", "없음",
        "acid", "water", "solution", "mixture", "gas", "product", "reagent",
    }
)

# Strings a document prints that are not names, excluded one by one with the
# reason. A typo in the PDF is not a synonym: nobody searches for it, and the
# table would present a spelling nobody uses as a published name (NFR-8). This
# is a list, not a typo detector - a detector would guess, and a guess that drops
# a real name is as wrong as one that keeps a typo. Keyed by normalized term
# (what `Candidate.normalized` yields), because a misspelling is not a name of
# any substance. Checked first, so a re-index cannot bring the row back.
EXCLUDED_TERMS: Mapping[str, str] = {
    # doc 729 "폼아마이드 (Formamide) - 대정화금", msds_03 관용명·이명.
    "formanfide": "원문 오타 (Formamide 의 오기)",
}

# BR-99 (revised): the gate every accepted name passes.
NOT_PRINTED = "추출문에 그 표기가 그대로 없음 (지어낸 문자열, BR-99)"
JOINED = "줄바꿈을 넘어 이어 붙인 문자열 (원문 값에 그대로 없음, BR-99)"

_COMPANY_MARKERS = re.compile(
    r"㈜|\(주\)|주식회사|co\.|ltd|inc\.|corp|chemicals&metals|page\d", re.IGNORECASE
)
_IDENTIFIER = re.compile(
    r"^(?:\d{2,7}-\d{2}-\d|un\s?\d{4}|rtecs.*|ke-\d+.*|ohs\d+|\d{3}-\d{3}-\d)$",
    re.IGNORECASE,
)
_CAS = re.compile(r"\d{2,7}-\d{2}-\d")
_HANGUL = re.compile(r"[가-힣]")

_LABEL = re.compile(
    r"(관용명\s*및\s*이명(?:\s*\(\s*異名\s*\))?|이명\s*\(\s*관용명\s*\)"
    r"|일반명\s*및\s*이명|관용명|동의어)\s*[:：]?"
)
# A value ends where the next field of the row starts.
_VALUE_STOP = re.compile(r"CAS|화학물질명|물질명|함유량|성분|" + _LABEL.pattern, re.IGNORECASE)
_CAS_LABEL = re.compile(r"CAS", re.IGNORECASE)
_LABEL_WINDOW = 600  # label -> CAS label
_CAS_WINDOW = 120  # CAS label -> CAS number (table headers sit in between)

_FORMULA_LABEL = re.compile(r"(?:분자식|화학식)\s*[:：]?\s*([A-Za-z0-9\-]+)")
_FORMULA_SHAPE = re.compile(r"^(?:[A-Z][a-z]?\d*){2,}$")

_ALLOWED_LOWER_PREFIX = re.compile(r"^(?:sec|tert|iso|cis|trans|[nomp](?:,[nomp])*)-")
_LEADING_LOCANT = re.compile(r"^[0-9][0-9,'’]*-\(?")
# The substituent half of an inverted name: "BIS(2-ETHYLHEXYL)ESTER", "n-butyl".
_SUBSTITUENT_TAIL = re.compile(r"(?:ester|salt)$|^(?:[a-z0-9,'’()\-]*-)?[a-z()0-9]*yl$", re.I)


def compact(term: str) -> str:
    return re.sub(r"\s+", "", term).casefold()


@dataclass(frozen=True)
class MsdsDocument:
    """What extraction reads from one single-subject MSDS document.

    Built from the pipeline context for the document being indexed and from the
    stored rows for every other one, so both are read the same way.
    """

    document_id: int
    title: str | None
    substance_id: int
    cas_number: str | None
    extracted_text: str
    chunks: tuple[tuple[str, str | None], ...]  # (text, section_code), in order


@dataclass
class Candidate:
    substance_id: int
    document_id: int
    term: str
    term_type: str
    evidence: list[str] = field(default_factory=list)
    reason: str | None = None  # None = accepted
    pair: str | None = None  # a Hangul name and its Latin gloss share this

    @property
    def normalized(self) -> str:
        return _normalize_term(self.term)


# --------------------------------------------------------------------------- #
# extraction - text in, raw strings out
# --------------------------------------------------------------------------- #


def title_names(title: str) -> tuple[list[str], str]:
    """`"메탄올 (Methanol) - Methanex 국문판"` -> (["메탄올", "Methanol"], "Methanex 국문판")."""
    head, company = title, ""
    if " - " in title:
        head, company = title.rsplit(" - ", 1)
    head = head.strip()
    if head.endswith(")"):
        depth = 0
        for index in range(len(head) - 1, -1, -1):
            if head[index] == ")":
                depth += 1
            elif head[index] == "(":
                depth -= 1
                if depth == 0:
                    # Only a parenthesis preceded by a space is a gloss;
                    # "비스(2-에틸헥실)" is part of the name.
                    if index > 0 and head[index - 1] == " ":
                        return [head[:index].strip(), head[index + 1 : -1].strip()], company
                    break
    return [head], company.strip()


def _split_gloss(fragment: str) -> list[str]:
    """`2-뷰타논(2-Butanone)` -> both names; a Latin-only parenthesis is a gloss."""
    match = re.match(r"^(.*[가-힣].*?)\s*\(([A-Za-z0-9 ,'’\-\[\]]+)\)$", fragment)
    if match and not _HANGUL.search(match.group(2)):
        return [match.group(1).strip(), match.group(2).strip()]
    return [fragment]


def _is_tail(fragment: str) -> bool:
    """The trailing half of an inverted CAS-index name: `Propane, 2-amino-`."""
    if fragment.endswith("-"):
        return True
    if _SUBSTITUENT_TAIL.search(fragment.replace(" ", "")):
        return True
    rest = _LEADING_LOCANT.sub("", fragment)
    if rest[:1].islower() and not _ALLOWED_LOWER_PREFIX.match(rest):
        return True
    return False


def _balanced(fragment: str) -> bool:
    for opening, closing in ("()", "[]"):
        if fragment.count(opening) != fragment.count(closing):
            return False
    return True


def _split_commas(value: str) -> list[str]:
    """Split on commas, except inside locants: `1,1'-`, `N,N-`."""
    parts: list[str] = []
    start = 0
    for index, char in enumerate(value):
        if char != ",":
            continue
        before = value[index - 1] if index else ""
        after = value[index + 1 : index + 3]
        locant_before = before.isdigit() or (
            before.isalpha() and (index < 2 or not value[index - 2].isalpha())
        )
        locant_after = bool(re.match(r"^[0-9A-Za-z][,'’\-]", after))
        if locant_before and locant_after:
            continue
        parts.append(value[start:index])
        start = index + 1
    parts.append(value[start:])
    return parts


def split_value(value: str, glued_end: bool = False) -> list[tuple[str, str | None]]:
    """A label's value -> [(fragment, reason it is unusable or None)].

    `glued_end` - the next field's label follows with no whitespace
    ("2,2-dimethoxyCAS 번호"), so the last name may have lost its end.

    A fragment that exists only because lines were joined is rejected here
    (`JOINED`): the join is how a wrapped list is read, not a name anyone printed.
    """
    value = value.strip()
    if not value:
        return []
    semicolons = ";" in value
    if semicolons:
        raw = re.sub(r"\s*\n\s*", " ", value).split(";")
    elif "," in value:
        # Daejung lists wrap mid-name ("Silicicacid(H4SiO4),\ntetraethylester").
        raw = _split_commas(re.sub(r"\s*\n\s*", "", value))
    else:
        raw = value.splitlines()
    fragments = [re.sub(r"\s+", " ", part).strip(" .·") for part in raw]
    fragments = [part for part in fragments if part]

    out: list[tuple[str, str | None]] = []
    for position, fragment in enumerate(fragments):
        if glued_end and position == len(fragments) - 1:
            out.append((fragment, "잘린 조각 (다음 칸 이름표와 붙어 끝이 불확실)"))
            continue
        if semicolons and re.search(r"(?<!\d),|,(?!\d)", fragment):
            out.append((fragment, "도치명 (쉼표로 뒤집힌 색인식 이름)"))
            continue
        if _is_tail(fragment):
            out.append((fragment, "잘린 조각 (도치명 뒷부분)"))
            if out and len(out) >= 2 and out[-2][1] is None:
                out[-2] = (out[-2][0], "도치명 머리 (뒤 조각이 붙어야 이름)")
            continue
        if not _balanced(fragment):
            out.append((fragment, "잘린 조각 (괄호 짝 안 맞음)"))
            continue
        for name in _split_gloss(fragment):
            out.append((name, None if name in value else JOINED))
    return out


def gloss_pairs(value: str) -> dict[str, str]:
    """name -> pair key, for the `X(Y)` glosses inside a value."""
    pairs: dict[str, str] = {}
    for line in re.split(r"[;\n]", value):
        names = _split_gloss(re.sub(r"\s+", " ", line).strip(" .·"))
        if len(names) == 2:
            for name in names:
                pairs[name] = names[0]
    return pairs


def labeled_values(text: str, cas_number: str) -> list[tuple[str, str | None, bool]]:
    """Section-3 label values whose row carries `cas_number`.

    Returns (raw value, reason rejected or None, glued_end). The CAS check is
    the whole point: a mixture's section 3 lists every component under the
    same label, and only the row with this substance's CAS is its own.
    """
    out: list[tuple[str, str | None, bool]] = []
    for match in _LABEL.finditer(text):
        after = text[match.end() :]
        stop = _VALUE_STOP.search(after)
        value = after[: stop.start()] if stop else after
        glued = bool(stop and stop.start() > 0 and not after[stop.start() - 1].isspace())
        if not value.strip():
            continue
        cas_label = _CAS_LABEL.search(after, len(value), len(value) + _LABEL_WINDOW)
        number = (
            _CAS.search(after[cas_label.end() : cas_label.end() + _CAS_WINDOW])
            if cas_label
            else None
        )
        if number is None:
            out.append((value.strip(), "뒤따르는 CAS 없음 (행을 특정할 수 없음)", glued))
        elif number.group(0) != cas_number:
            out.append((value.strip(), f"다른 성분의 행 (CAS {number.group(0)})", glued))
        else:
            out.append((value.strip(), None, glued))
    return out


def formula_values(text: str) -> list[str]:
    found = []
    for match in _FORMULA_LABEL.finditer(text):
        formula = match.group(1).replace("-", "")
        if _FORMULA_SHAPE.match(formula) and re.search(r"\d", formula):
            found.append(formula)
    return found


def appears_verbatim(term: str, text: str) -> bool:
    pattern = r"(?<![A-Za-z0-9])" + re.escape(term) + r"(?![A-Za-z0-9])"
    return re.search(pattern, text) is not None


def printed_in(term: str, extracted_text: str) -> bool:
    """BR-99 (revised) as a test: the name, normalized, is in the extracted text.

    Case and spacing included. `extracted_text` is already `normalize()` output,
    so normalizing the term is the only step; lowering either side would accept
    a spelling the document does not print.
    """
    needle = normalize(term)
    return bool(needle) and needle in extracted_text


def extract(document: MsdsDocument) -> tuple[list[Candidate], str | None]:
    """Every candidate the document offers, each accepted or with its reason.

    Returns the candidates and the company named in the title, which screening
    uses to drop company names printed as if they were synonyms.
    """
    sid, did = document.substance_id, document.document_id
    chunks = document.chunks
    candidates: list[Candidate] = []
    company: str | None = None

    if document.title:
        names, company = title_names(document.title)
        for name in names:
            cand = Candidate(
                sid,
                did,
                name,
                MSDS_TITLE,
                [f"doc {did} 제목 '{document.title}'"],
                pair=f"title:{did}" if len(names) == 2 else None,
            )
            norm = _normalize_term(name)
            printed = [i for i, (t, _) in enumerate(chunks) if norm in _normalize_term(t)]
            if printed:
                cand.evidence.append(f"doc {did} chunk #{printed[0]} (본문 표기)")
            else:
                cand.reason = "제목에만 있고 본문에 그 표기가 없음"
            candidates.append(cand)

    cas = document.cas_number
    for index, (text, section) in enumerate(chunks):
        where = f"doc {did} chunk #{index} ({section}"
        if cas and section == COMPOSITION_SECTION:
            for value, row_reason, glued in labeled_values(text, cas):
                if row_reason:
                    shown = re.sub(r"\s+", " ", value)
                    shown = shown if len(shown) <= 60 else shown[:57] + "..."
                    candidates.append(
                        Candidate(sid, did, shown, COMMON_NAME, [f"{where} 관용명·이명)"],
                                  row_reason)
                    )
                    continue
                pairs = gloss_pairs(value)
                for fragment, reason in split_value(value, glued):
                    pair = pairs.get(fragment)
                    key = f"{did}:{index}:{pair}" if pair else None
                    candidates.append(
                        Candidate(sid, did, fragment, COMMON_NAME, [f"{where} 관용명·이명)"],
                                  reason, key)
                    )
        for formula in formula_values(text):
            cand = Candidate(sid, did, formula, FORMULA, [f"{where} 분자식)"])
            verbatim = [i for i, (t, _) in enumerate(chunks) if appears_verbatim(formula, t)]
            if verbatim:
                cand.evidence.append(f"doc {did} chunk #{verbatim[0]} (그대로 표기)")
            else:
                cand.reason = "하이픈을 뺀 형태가 문서에 그대로 나오지 않음 (지어낸 표기)"
            candidates.append(cand)

    for cand in candidates:
        if cand.reason is None and not printed_in(cand.term, document.extracted_text):
            cand.reason = NOT_PRINTED
    return candidates, company


# --------------------------------------------------------------------------- #
# screening - candidates in, each marked accepted or with its reason
# --------------------------------------------------------------------------- #


def screen(
    candidates: list[Candidate],
    base_names: Mapping[int, Iterable[str]],
    companies: Iterable[str] = (),
    labels: Mapping[int, str] | None = None,
) -> list[Candidate]:
    """Mark each candidate. `base_names` is substance id -> its existing ko/en terms.

    Returns one candidate per (document, substance, normalized term): the first
    accepted one by `MSDS_TYPES` priority, with that document's evidence merged,
    so the same name does not go in twice under two types. Two documents that
    print the same name each keep theirs - each is the owner of its row.
    """
    labels = labels or {}
    company_keys = {compact(c) for c in companies if compact(c)}
    base = {sid: {_normalize_term(n) for n in names if n} for sid, names in base_names.items()}

    for cand in candidates:
        if cand.reason:
            continue
        key = compact(cand.term)
        if cand.normalized in EXCLUDED_TERMS:
            cand.reason = EXCLUDED_TERMS[cand.normalized]
        elif cand.normalized in base.get(cand.substance_id, set()):
            cand.reason = "기존 이름과 같음"
        elif _IDENTIFIER.match(cand.term.strip()):
            cand.reason = "식별번호"
        elif len(key) < MIN_LEN:
            cand.reason = f"너무 짧음 ({len(key)}자)"
        elif not _HANGUL.search(key) and len(key) < MIN_LATIN_LEN:
            cand.reason = f"너무 짧음 (라틴 {len(key)}자, 부분 문자열로 오해석)"
        elif key in GENERIC_NOUNS:
            cand.reason = "일반 명사"
        elif _COMPANY_MARKERS.search(key) or any(c in key for c in company_keys):
            cand.reason = "회사명"

    # Merge per (document, substance, normalized), keeping priority order.
    priority = {t: i for i, t in enumerate(MSDS_TYPES)}
    merged: dict[tuple[int, int, str], Candidate] = {}
    for cand in sorted(candidates, key=lambda c: (c.reason is not None, priority[c.term_type])):
        slot = (cand.document_id, cand.substance_id, cand.normalized)
        if slot in merged:
            kept = merged[slot]
            kept.evidence.extend(e for e in cand.evidence if e not in kept.evidence)
            continue
        merged[slot] = cand
    result = list(merged.values())

    for cand in result:
        if cand.reason:
            continue
        own = base.get(cand.substance_id, set())
        norm = cand.normalized
        # Equality was settled in the first pass; containment is left.
        if any(norm in name for name in own):
            cand.reason = "기존 이름의 일부 (더 넓은 이름이라 다른 물질에 걸림)"
        elif any(name in norm for name in own):
            cand.reason = "기존 이름을 포함 (부분 일치로 이미 해석됨)"

    # Ambiguity last: against other substances' existing names and against
    # every other substance's candidate, accepted or not. A term a different
    # substance also claims is not evidence for either.
    claims: dict[str, set[int]] = {}
    for sid, names in base.items():
        for name in names:
            claims.setdefault(name, set()).add(sid)
    for cand in result:
        claims.setdefault(cand.normalized, set()).add(cand.substance_id)
    for cand in result:
        if cand.reason:
            continue
        norm = cand.normalized
        others = sorted(
            (term, sid)
            for term, owners in claims.items()
            if norm in term
            for sid in owners
            if sid != cand.substance_id
        )
        if others:
            term, sid = others[0]
            cand.reason = f"모호해서 제외 ({labels.get(sid, sid)} 의 '{term}' 에 걸림)"

    # A Hangul name and its Latin gloss are one name in two scripts: when one
    # half is ambiguous the other is too, whether or not the substring test
    # can see it ("2-Butanone" hits 3,3-dimethyl-2-butanone; "2-뷰타논" would
    # hit the same compound spelled 뷰타논 rather than the master's 뷰탄온).
    tainted = {
        (c.substance_id, c.pair)
        for c in result
        if c.pair and c.reason and c.reason.startswith("모호")
    }
    for cand in result:
        if cand.reason is None and (cand.substance_id, cand.pair) in tainted:
            cand.reason = "모호해서 제외 (짝 표기가 모호)"
    return result


def names_for(
    document: MsdsDocument,
    others: Iterable[MsdsDocument],
    base_names: Mapping[int, Iterable[str]],
    labels: Mapping[int, str] | None = None,
) -> list[Candidate]:
    """The verdict on every candidate `document` offers, judged against the corpus.

    `others` are the other single-subject MSDS documents. Their candidates take
    part in screening as claims - ambiguity and company names - and are then
    dropped from the result: `document` only ever writes its own rows.
    """
    candidates: list[Candidate] = []
    companies: set[str] = set()
    for doc in (document, *others):
        found, company = extract(doc)
        candidates.extend(found)
        if company:
            companies.add(company)
            companies.add(company.split()[0])
    result = screen(candidates, base_names, companies, labels)
    return [c for c in result if c.document_id == document.document_id]


def synonym_terms(accepted: Iterable[Candidate]) -> list[tuple[str, str, SynonymType]]:
    """Accepted candidates in the repository's `(raw, normalized, type)` shape."""
    return [
        (c.term, c.normalized, SynonymType(c.term_type)) for c in accepted if c.reason is None
    ]


def register(
    repo,
    document_id: int,
    document: MsdsDocument | None,
    others: Iterable[MsdsDocument],
    base_names: Mapping[int, Iterable[str]],
    labels: Mapping[int, str] | None = None,
) -> int:
    """BR-97/99 - replace the rows `document_id` owns with what it prints now.

    `document` is None when the document is not a single-subject MSDS (any
    more): its rows are cleared, because nothing it prints is evidence for a
    substance it is not the datasheet of. Returns the number of rows written.
    """
    if document is None:
        repo.replace_document_synonyms(document_id, [], owned_types=MSDS_SYNONYM_TYPES)
        return 0

    verdicts = names_for(document, others, base_names, labels)
    terms = synonym_terms(verdicts)
    substance = repo.get_by_id(document.substance_id)
    written = repo.replace_document_synonyms(
        document_id, [(substance, terms)] if substance else [], owned_types=MSDS_SYNONYM_TYPES
    )
    log.info(
        "msds_synonyms_registered",
        extra={
            "document_id": document_id,
            "substance_id": document.substance_id,
            "accepted": [t for t, _n, _k in terms],
            "rejected": {c.term: c.reason for c in verdicts if c.reason},
        },
    )
    return written


# --------------------------------------------------------------------------- #
# reading - the same ambiguity rule, where a name becomes a substance
# --------------------------------------------------------------------------- #


def resolvable_synonym():
    """SQL filter: rows a question may resolve through (BR-73a).

    Every `ko`/`en` row, and a document-owned row only while no row of a
    **different** substance contains it (equal included). Screening applies the
    same test when the row is written, but only against what the corpus holds
    at that moment: a substance record or MSDS collected later can make an
    earlier document's name ambiguous, and that row stays until its document is
    re-indexed. Resolving through it in the meantime would pull the other
    substance's record chunks in at exact-match rank and past the
    `unknown_subject` refusal - one substance's data answering for another.

    The `ko`/`en` rows are left as they are: they are the substance's own
    names, and how they overlap (`ethyl silicate` inside `tetramethyl
    silicate`) predates document-owned names and is not changed here.
    """
    other = aliased(SubstanceSynonym)
    return or_(
        SubstanceSynonym.source_document_id.is_(None),
        ~exists().where(
            other.substance_id != SubstanceSynonym.substance_id,
            func.strpos(other.normalized_term, SubstanceSynonym.normalized_term) > 0,
        ),
    )
