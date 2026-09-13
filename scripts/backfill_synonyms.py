"""Fill `substance_synonym` with names our own MSDS documents publish (backlog D11).

Measured 2026-09-10: 49 substances, 98 rows, exactly one `ko` and one `en` each.
Not one real synonym. 황산 is held (two MSDS plus a record) and `H2SO4 저장법`
still resolves to nothing, because `entities._match_synonyms` can only match a
string the table holds.

**It invents nothing.** Every term this script writes is a string that appears
in a document linked to that substance (`document_substance.relation =
'subject'`). General knowledge is not evidence: "메탄올 = 메틸알코올" goes in
because Methanex's MSDS prints it, not because it is true.

Three sources, one `term_type` each, so "where did this synonym come from" has
an answer after the fact:

  * `msds_title`  - the name in the MSDS document title (`X (Y) - 회사`), and
                    only when that name also appears in the document body. The
                    title is written in `config/msds_manifest.json`; the body is
                    what the supplier published.
  * `common_name` - the value of a `관용명 및 이명` / `이명(관용명)` / `동의어`
                    label in **section 3** (구성성분의 명칭 및 함유량), and only
                    when the CAS number that follows the label is this
                    substance's. Section 3 ties a name to a CAS row; section 1's
                    free "동의어/상품명" list does not, and koreachem's lists
                    다이싸이온산 (dithionic acid, a different compound) as a
                    synonym of 황산. So section 1 lists are not read.
  * `formula`     - the value of a `분자식` / `화학식` label, hyphens removed,
                    and only when that exact string also appears verbatim in the
                    same document. A string we produced by removing hyphens is
                    not published; the verbatim occurrence is.

**It is conservative.** The table is matched by substring
(`normalized_term in query`), so a wrong synonym resolves a question to the
wrong substance - one substance's toxicity attached to another (BR-73a). A
candidate is dropped when it is ambiguous (equal to, or contained in, a term of
a different substance), too short, a generic noun, a company name, a fragment of
an inverted CAS-index name, or contained in / containing the substance's own
existing name (the shorter name is a broader one - `Butylamine` is printed as a
synonym of tert-Butylamine and names a different compound; the longer one adds
nothing a substring match does not already find), or named in `EXCLUDED_TERMS`
(a misprint in the source). Every drop is printed with its reason.

**It is idempotent.** Rows go in with `ON CONFLICT ON CONSTRAINT uq_synonym_term
DO NOTHING`, and a term the substance already carries is reported, not written.

`normalized_term` is built by `projection._normalize_term`, the function the
collection path uses for the existing rows - one owner for the rule, or a row
this script writes would not match the way the others do.

Dry run is the default. Run it from the host (the container has no `scripts/`):

    set -a; . ./.env; set +a
    PYTHONIOENCODING=utf-8 POSTGRES_HOST=127.0.0.1 POSTGRES_PORT=5433 \
        python scripts/backfill_synonyms.py            # print candidates only
    ...                                  python scripts/backfill_synonyms.py --apply
"""

from __future__ import annotations

import argparse
import re
import sys
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.types import SynonymType  # noqa: E402
from app.substances.projection import _normalize_term  # noqa: E402

# The enum owns the values; `SubstanceLookup` reads every row through it.
MSDS_TITLE = SynonymType.MSDS_TITLE.value
COMMON_NAME = SynonymType.COMMON_NAME.value
FORMULA = SynonymType.FORMULA.value
BACKFILL_TYPES = (COMMON_NAME, FORMULA, MSDS_TITLE)  # also the keep-one priority

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
# any substance. Checked first, so a rerun cannot bring the row back.
EXCLUDED_TERMS: Mapping[str, str] = {
    # doc 729 "폼아마이드 (Formamide) - 대정화금", msds_03 관용명·이명.
    "formanfide": "원문 오타 (Formamide 의 오기)",
}

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


@dataclass
class Candidate:
    substance_id: int
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
        out.extend((name, None) for name in _split_gloss(fragment))
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

    Returns one candidate per (substance, normalized term): the first accepted
    one by `BACKFILL_TYPES` priority, with every source's evidence merged, so
    the same name does not go in twice under two types.
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

    # Merge per (substance, normalized), keeping priority order.
    priority = {t: i for i, t in enumerate(BACKFILL_TYPES)}
    merged: dict[tuple[int, str], Candidate] = {}
    for cand in sorted(candidates, key=lambda c: (c.reason is not None, priority[c.term_type])):
        slot = (cand.substance_id, cand.normalized)
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


# --------------------------------------------------------------------------- #
# database
# --------------------------------------------------------------------------- #


def collect(session) -> tuple[list[Candidate], dict[int, list[str]], dict[int, str], set[str]]:
    from sqlalchemy import text as sql

    substances = session.execute(
        sql("SELECT id, name_ko, name_en, cas_number FROM substance ORDER BY id")
    ).all()
    labels = {sid: (ko or en or str(sid)) for sid, ko, en, _ in substances}
    cas_of = {sid: cas for sid, _, _, cas in substances}
    base: dict[int, list[str]] = {sid: [] for sid, *_ in substances}
    for sid, term in session.execute(
        sql("SELECT substance_id, term FROM substance_synonym WHERE term_type IN ('ko', 'en')")
    ).all():
        base[sid].append(term)

    # One subject, and the document is an MSDS: a mixture MSDS that merely
    # mentions a substance is not that substance's document.
    docs = session.execute(
        sql(
            """
            SELECT d.id, d.title, min(ds.substance_id)
              FROM document d
              JOIN document_substance ds ON ds.document_id = d.id AND ds.relation = 'subject'
             WHERE d.doc_type = 'msds'
             GROUP BY d.id, d.title
            HAVING count(DISTINCT ds.substance_id) = 1
             ORDER BY d.id
            """
        )
    ).all()

    candidates: list[Candidate] = []
    companies: set[str] = set()
    for document_id, title, sid in docs:
        chunks = session.execute(
            sql(
                """
                SELECT c.id, c.text, s.section_code
                  FROM chunk c LEFT JOIN document_section s ON s.id = c.section_id
                 WHERE c.document_id = :d ORDER BY c.ordinal
                """
            ),
            {"d": document_id},
        ).all()

        if title:
            names, company = title_names(title)
            if company:
                companies.add(company)
                companies.add(company.split()[0])
            for name in names:
                cand = Candidate(
                    sid,
                    name,
                    MSDS_TITLE,
                    [f"doc {document_id} 제목 '{title}'"],
                    pair=f"title:{document_id}" if len(names) == 2 else None,
                )
                # Verbatim, spacing included: the title is ours (the manifest),
                # the body is the supplier's. "메틸에틸케톤" counts only because
                # section 14 prints it; "메틸 에틸 케톤" elsewhere would not.
                norm = _normalize_term(name)
                printed = [cid for cid, t, _ in chunks if norm in _normalize_term(t)]
                if printed:
                    cand.evidence.append(f"doc {document_id} chunk {printed[0]} (본문 표기)")
                else:
                    cand.reason = "제목에만 있고 본문에 그 표기가 없음"
                candidates.append(cand)

        cas = cas_of.get(sid)
        for chunk_id, text, section in chunks:
            if cas and section == COMPOSITION_SECTION:
                for value, row_reason, glued in labeled_values(text, cas):
                    where = f"doc {document_id} chunk {chunk_id} ({section} 관용명·이명)"
                    if row_reason:
                        shown = re.sub(r"\s+", " ", value)
                        shown = shown if len(shown) <= 60 else shown[:57] + "..."
                        candidates.append(Candidate(sid, shown, COMMON_NAME, [where], row_reason))
                        continue
                    pairs = gloss_pairs(value)
                    for fragment, reason in split_value(value, glued):
                        pair = pairs.get(fragment)
                        key = f"{chunk_id}:{pair}" if pair else None
                        candidates.append(
                            Candidate(sid, fragment, COMMON_NAME, [where], reason, key)
                        )
            for formula in formula_values(text):
                where = f"doc {document_id} chunk {chunk_id} ({section} 분자식)"
                cand = Candidate(sid, formula, FORMULA, [where])
                verbatim = [cid for cid, t, _ in chunks if appears_verbatim(formula, t)]
                if verbatim:
                    cand.evidence.append(f"doc {document_id} chunk {verbatim[0]} (그대로 표기)")
                else:
                    cand.reason = "하이픈을 뺀 형태가 문서에 그대로 나오지 않음 (지어낸 표기)"
                candidates.append(cand)
    return candidates, base, labels, companies


def plan_inserts(
    result: Iterable[Candidate], existing: set[tuple[int, str]]
) -> list[Candidate]:
    """Accepted candidates the table does not already hold, by (substance, normalized).

    Keyed without `term_type`, deliberately wider than `uq_synonym_term`: the
    same name under a second type would be a second row matching the same way.
    """
    return [
        c for c in result
        if c.reason is None and (c.substance_id, c.normalized) not in existing
    ]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true", help="print candidates (default)")
    mode.add_argument("--apply", action="store_true", help="insert the accepted candidates")
    args = parser.parse_args(argv)

    from sqlalchemy import text as sql

    from app.core.config import get_settings
    from app.db.engine import init_engine, session_scope

    init_engine(get_settings())
    with session_scope() as session:
        raw, base, labels, companies = collect(session)
        result = screen(raw, base, companies, labels)
        existing = {
            (sid, norm)
            for sid, norm in session.execute(
                sql("SELECT substance_id, normalized_term FROM substance_synonym")
            ).all()
        }

        to_insert = {id(c) for c in plan_inserts(result, existing)}
        accepted = sum(1 for c in result if c.reason is None)
        present = accepted - len(to_insert)
        inserted = 0
        by_substance: dict[int, list[Candidate]] = {}
        for cand in result:
            by_substance.setdefault(cand.substance_id, []).append(cand)

        print("물질 | 후보 | term_type | 근거 | 판정")
        for sid in sorted(by_substance, key=lambda s: labels.get(s, "")):
            for cand in sorted(by_substance[sid], key=lambda c: (c.reason is not None, c.term)):
                verdict = cand.reason or "채택"
                if cand.reason is None and id(cand) not in to_insert:
                    verdict = "채택 (이미 있음)"
                elif cand.reason is None and args.apply:
                    row = session.execute(
                        sql(
                            """
                            INSERT INTO substance_synonym
                                   (substance_id, term, normalized_term, term_type)
                            VALUES (:sid, :term, :norm, :type)
                            ON CONFLICT ON CONSTRAINT uq_synonym_term DO NOTHING
                            RETURNING id
                            """
                        ),
                        {"sid": sid, "term": cand.term, "norm": cand.normalized,
                         "type": cand.term_type},
                    ).first()
                    inserted += 1 if row else 0
                    verdict = "채택 (넣음)" if row else "채택 (이미 있음)"
                print(
                    f"{labels.get(sid, sid)} | {cand.term} | {cand.term_type} | "
                    f"{'; '.join(cand.evidence)} | {verdict}"
                )

    excluded = len(result) - accepted
    verb = "넣음" if args.apply else "넣을 대상(dry-run)"
    print(
        f"\n후보 {len(result)}건 · 채택 {accepted}건 · 제외 {excluded}건 · "
        f"이미 있음 {present}건 · {verb} {inserted if args.apply else len(to_insert)}건"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
