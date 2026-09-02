"""BR-08 - which substances the initial collection picks.

The rule says the first pass should take ① substances that have appeared in an
accident record, then ② regulated substances. Until now neither was
implemented: `list_targets` simply stopped after `INITIAL_SUBSTANCE_TARGET`
rows, so the master held the first 40 records the API happened to return
(아이소프로필아민, 테트라메틸실리케이트, ...) and **none** of the eight substances
the MSDS corpus actually documents. Every card came back six items out of seven
empty, because the substance master and the document corpus had zero overlap.

Criterion ② has no data behind it. The `/kischemlist` response carries
`dataNo/casNo/chemKo/chemEn` plus the four first-aid routes and no regulation
flag of any kind, so there is nothing to sort on. Rather than invent one, this
module widens ① to the substances the corpus already talks about - accident
records *and* the MSDS documents already collected - which is the same
criterion in kind (the substance is one this system holds documents about) and
serves the same purpose: a card that has something on it.

Matching is **exact on the normalised name**, and that is a deliberate
restriction. Substring matching was measured first and is unusable here:
"톨루엔" is a substring of 68 master entries (2-브로모톨루엔, 2,4-다이클로로톨루엔,
...) and "황산" of 56 (황산구리, 황산니켈, ...), so a 40-record budget would
fill with derivatives and never reach the substance the user asked about.
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Iterable, Sequence

# The source renders every Korean name as "·톨루엔". The bullet is list markup
# from the original rendering, not part of the name (see the same problem in
# `substances/projection.py`). Only bullets are stripped - a hyphen or an
# asterisk can be part of a chemical name.
_LIST_MARKERS = "·•‧・∙"

# 사고 원문 writes "4,4‛-디이소시안산 디페닐메탄", the master writes
# "4,4’-디이소시안산 디페닐메탄". Same prime, different code point, and folding
# them is the whole difference between a hit and a miss on that record.
_APOSTROPHES = "‘’‛′`＇"

# "톨루엔 30~35 %", "암모니아(100%)", "아크릴산(1~3%)".
_CONCENTRATION = re.compile(r"\d+(?:[.,]\d+)?\s*(?:~\s*\d+(?:[.,]\d+)?)?\s*%")
_PARENTHESISED = re.compile(r"[(（]([^()（）]*)[)）]")
# `,` is NOT a separator outside a concentration group: it is part of the name
# in "N,N-디메틸포름아미드" and "4,4'-디이소시안산 디페닐메탄", and splitting on it
# turned the second into "4‛-디이소시안산 디페닐메탄", which matches nothing.
_OUTSIDE_SPLIT = re.compile(r"[:：/]|\s및\s")
_MIXTURE_SPLIT = re.compile(r"[,、]")
_LABEL = re.compile(r"^\s*substances\s*:\s*", re.IGNORECASE)
# MSDS titles carry a vendor: "황산 (SULFURIC ACID) - 남해화학".
_VENDOR_TAIL = re.compile(r"\s[-–—]\s")

MIN_TERM_LENGTH = 2


def normalise(value: str | None) -> str:
    """Fold a name to the form both sides of the comparison are matched on."""
    text = unicodedata.normalize("NFKC", str(value or "")).strip()
    text = text.lstrip(_LIST_MARKERS + " ")
    text = "".join("'" if char in _APOSTROPHES else char for char in text)
    # Whitespace is removed rather than collapsed: the master writes
    # "메틸 에틸 케톤" and the accident record "메틸에틸케톤".
    return re.sub(r"\s+", "", text).casefold()


def candidate_terms(values: Iterable[str]) -> list[str]:
    """Pull chemical names out of free-form corpus text.

    Deliberately generous - the exact-match step is what rejects noise, so a
    wrong candidate costs nothing while a missed one costs a card. Both input
    shapes go through the same path: an accident record's
    "substances: 암모니아(100%)" and an MSDS title's "황산 (SULFURIC ACID) - 남해화학".
    """
    terms: list[str] = []
    for raw in values:
        value = _VENDOR_TAIL.split(_LABEL.sub("", str(raw or "")).strip())[0]
        terms.extend(_terms_in(value))
    # Deduplicate, keep order - order is only cosmetic here but makes the log
    # line reproducible.
    seen: set[str] = set()
    return [t for t in terms if not (t in seen or seen.add(t))]


def _terms_in(value: str) -> list[str]:
    found: list[str] = []
    for group in _PARENTHESISED.findall(value):
        cleaned = _CONCENTRATION.sub("", group).strip()
        if _CONCENTRATION.search(group):
            # A mixture: "톨루엔 30~35 %, 메틸에틸케톤 35~40 %, ...". Both the
            # parts and the whole are offered, because a single-component group
            # may itself contain a comma ("N,N-디메틸포름아미드 100%").
            found.extend(part.strip() for part in _MIXTURE_SPLIT.split(cleaned))
        found.append(cleaned)
    outside = _PARENTHESISED.sub(" ", value)
    for part in _OUTSIDE_SPLIT.split(outside):
        part = _CONCENTRATION.sub("", part).strip()
        if not part:
            continue
        found.append(part)
        # A product name often leads with the substance:
        # "선형저밀도폴리에틸렌 R905U". The head is offered as well.
        head = part.split()[0]
        if head != part:
            found.append(head)
    return [t for t in found if len(t) >= MIN_TERM_LENGTH]


def partition[T](
    entries: Sequence[tuple[T, Sequence[str]]],
    terms: Iterable[str],
    target: int,
) -> tuple[list[T], int]:
    """Order `entries` so corpus substances come first, then cut to `target`.

    Stable within each group: the remainder keeps the source's own order, which
    is what the previous behaviour was in its entirety. Returns the selection
    and how many of it matched, so the caller can log the difference rather
    than assert it.
    """
    wanted = {normalise(term) for term in terms}
    wanted.discard("")
    matched: list[T] = []
    rest: list[T] = []
    for item, names in entries:
        hit = any(normalise(name) in wanted for name in names)
        (matched if hit else rest).append(item)
    return (matched + rest)[:target], len(matched)
