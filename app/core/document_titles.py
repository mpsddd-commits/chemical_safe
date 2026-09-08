"""What a document is called — and why the generator cannot work without it.

`indexing_service` stores these strings as `document.title`. `assembler.for_answer`
puts that value in the `title=` attribute of every evidence block, and the citation
panel shows it to the user. It is the **only** cue the generator has for *whose*
evidence it is holding.

That matters because a substance record's chunks never contain the substance's
name. The 암모니아 eye chunk reads

    eyeball: ·눈에 소량은 영구적은 손상을 일으킬 것임

and nothing more — the name lives only in the substance master. The retrieval
layer was taught this on 2026-09-01 (BR-65a: name -> CAS -> exact match); the
generation layer was not. So five untitled `substance_eye` chunks arrived at the
generator indistinguishable from each other, and asked about 암모니아 it refused
rather than guess which of the five was 암모니아 (2026-09-08, C13). It was right
to refuse. The prompt had lied by omission.

The formats live here rather than inside each adapter because the backfill of the
70 documents collected before this existed has to produce exactly the strings the
next collection will produce. One format, one owner.
"""

from __future__ import annotations

from typing import Any

__all__ = ["clean", "incident_title", "law_title", "substance_title"]


def clean(value: Any) -> str | None:
    """A trimmed string, or None for anything that would render as empty."""
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def substance_title(
    name_ko: Any = None, name_en: Any = None, cas_number: Any = None
) -> str | None:
    """`암모니아 (Ammonia) · CAS 7664-41-7`, shrinking to whatever is present.

    A missing part is dropped, never rendered: an empty pair of brackets or a
    literal `None` in the prompt is worse than a shorter title.
    """
    ko = clean(name_ko)
    en = clean(name_en)
    cas = clean(cas_number)

    head = ko or en
    if head and en and en != head:
        head = f"{head} ({en})"

    parts = [part for part in (head, f"CAS {cas}" if cas else None) if part]
    return " · ".join(parts) or None


def incident_title(
    place: Any = None,
    incident_type: Any = None,
    occurred_at: Any = None,
    area: Any = None,
) -> str | None:
    """`광운대학교 폭발 (2025-12-26)`.

    `area` (`전라북도 군산시`) stands in when the record names no `place`. With
    neither, the type and date alone still say which accident this is; with not
    even a type, a bare date in brackets says nothing, so there is no title.
    """
    where = clean(place) or clean(area)
    kind = clean(incident_type)
    when = clean(occurred_at)

    head = " ".join(part for part in (where, kind) if part)
    if not head:
        return None
    return f"{head} ({when})" if when else head


def law_title(law_name_korean: Any) -> str | None:
    """The statute's own name — `화학물질관리법 시행령`.

    Deliberately not `document.law_name`. That column holds the *search term*
    from `sources.yaml` `targets`, so the Act, its Enforcement Decree and its
    Enforcement Rule all carry `화학물질관리법` and naming a document by it would
    make the three indistinguishable — the exact failure this module exists to
    prevent. The searched-for term staying in `law_name` is the design; the
    document's own name belongs here.
    """
    return clean(law_name_korean)
