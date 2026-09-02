"""C22 ChunkStage - section-aligned chunking (BR-26~BR-31a).

One section becomes one chunk. MSDS sections and statute articles are already
meaning-bearing units, so imposing a fixed window on top of them would discard
structure that the corpus hands us for free - and would cost the natural
citation unit ("제12조", "8. 노출방지 및 개인보호구").

Splitting happens only when a section exceeds the token ceiling, and it descends
the coarsest boundary that works (BR-27a). There is no overlap: with real
boundaries there is little context to lose, and overlap would inflate the index
and let one passage be cited twice as if it were two sources.
"""

from __future__ import annotations

import re
from dataclasses import replace

from app.core.config import Settings, get_settings
from app.core.types import Chunk, ChunkMeta, Section, StructuredDoc, StructureStatus
from app.processing.tokens import count_tokens

# BR-27a - the boundary ladder.
#
# A blank line alone does not describe this corpus. Measured on the real 1,564
# chunks: the law API returns 부칙 as a single line with no break of any kind
# (14,014 characters, 8,111 tokens, zero newlines), and MSDS section 11 arrives
# as ~80 single-newline rows with no blank line between them. Both fell through
# to "cannot split" and were stored eight times over the ceiling.
#
# Each rung is tried only when the rung above still leaves a span oversized, so
# the common case pays nothing and coarse structure is preferred wherever it
# exists. Splitting finer than necessary is harmless anyway: `_split_oversized`
# packs the spans back up to the ceiling.
_BLANK_LINE = re.compile(r"\n\s*\n")
_LINE_BREAK = re.compile(r"\n")
# Korean statute and MSDS prose both end sentences with a period ("...한다. ").
# A numbered marker ("1. ") matches too, which only makes the spans finer.
_SENTENCE_END = re.compile(r"(?<=[.!?。])\s+")

_BOUNDARY_LADDER = (_BLANK_LINE, _LINE_BREAK, _SENTENCE_END)


def _split_by(
    pattern: re.Pattern[str], text: str, start: int, end: int
) -> list[tuple[int, int]]:
    """Spans of [start, end) between matches of `pattern`, separators excluded.

    Offsets stay absolute into `text` so BR-30 holds by construction: nothing is
    rewritten, only sliced.
    """
    spans: list[tuple[int, int]] = []
    cursor = start
    for match in pattern.finditer(text, start, end):
        if match.start() > cursor:
            spans.append((cursor, match.start()))
        cursor = max(cursor, match.end())
    if cursor < end:
        spans.append((cursor, end))
    return [(s, e) for s, e in spans if text[s:e].strip()]


def _hard_slice(text: str, start: int, end: int, max_tokens: int) -> list[tuple[int, int]]:
    """Last resort - a span carrying no separator at all (BR-27a).

    Cutting mid-sentence is bad. Leaving the span whole is worse: everything past
    `EMBED_MAX_SEQ_LENGTH` is dropped from the vector while the BR-30 offsets go
    on advertising it, so the text becomes citable but unreachable by search.
    That failure is silent, which is what makes it the worse of the two.
    """
    spans: list[tuple[int, int]] = []
    cursor = start
    while cursor < end:
        lo, hi = 1, end - cursor
        while lo < hi:
            mid = (lo + hi + 1) // 2
            if count_tokens(text[cursor : cursor + mid]) <= max_tokens:
                lo = mid
            else:
                hi = mid - 1
        spans.append((cursor, cursor + lo))
        cursor += lo
    return spans


def _atomic_spans(
    text: str, start: int, end: int, max_tokens: int, rung: int = 0
) -> list[tuple[int, int]]:
    """Descend `_BOUNDARY_LADDER` until every span fits under the ceiling."""
    if count_tokens(text[start:end]) <= max_tokens:
        return [(start, end)]
    if rung >= len(_BOUNDARY_LADDER):
        return _hard_slice(text, start, end, max_tokens)
    parts = _split_by(_BOUNDARY_LADDER[rung], text, start, end)
    if len(parts) < 2:
        # This rung found no boundary here; it changes nothing, so drop to the
        # next one rather than emitting the span unchanged.
        return _atomic_spans(text, start, end, max_tokens, rung + 1)
    out: list[tuple[int, int]] = []
    for part_start, part_end in parts:
        out.extend(_atomic_spans(text, part_start, part_end, max_tokens, rung + 1))
    return out


def _split_oversized(
    text: str, section: Section, max_tokens: int
) -> list[tuple[int, int]]:
    """BR-27 - split an oversized section, then pack back up to the ceiling.

    Packing measures the **merged slice**, never the sum of the parts. Those are
    not the same number, and the one that matters is the merged slice: a chunk's
    stored `token_count` is computed on `text[start:end]`, which includes the
    separators the spans excluded and rounds once instead of once per part.
    Summing 39 sentence spans understated the merged slice by 6 tokens in a
    measured case - enough to carry 15 real chunks past a ceiling this function
    believed it was enforcing.
    """
    spans = _atomic_spans(text, section.start_offset, section.end_offset, max_tokens)
    out: list[tuple[int, int]] = []
    cur_start: int | None = None
    cur_end = 0

    for span_start, span_end in spans:
        if cur_start is None:
            cur_start, cur_end = span_start, span_end
            continue
        if count_tokens(text[cur_start:span_end]) > max_tokens:
            out.append((cur_start, cur_end))
            cur_start, cur_end = span_start, span_end
        else:
            cur_end = span_end

    if cur_start is not None:
        out.append((cur_start, cur_end))
    return out


def _merge_undersized(
    pieces: list[tuple[int, int, int | None]], text: str, min_tokens: int, max_tokens: int
) -> list[tuple[int, int, int | None]]:
    """BR-31 - fold a too-small fragment into its neighbour.

    **Merging never crosses a section boundary.** BR-31 exists to clean up the
    trailing scraps produced when an oversized section is split (BR-27), not to
    glue two sections together. Merging across the boundary would produce a chunk
    labelled `msds_11` whose body also contains section 12 - and u2 would cite it
    that way. A genuinely short section stays its own chunk, undersized or not.

    Within one section, merging backwards is right: a stray fragment belongs to
    the text it followed.

    A document whose sections are *all* too small to be citation units is a
    different problem, and BR-31a handles it at the document level rather than
    by relaxing this rule piece by piece.

    Merging also stops at the ceiling. BR-27a makes `MAX_CHUNK_TOKENS` an
    invariant, and folding a 12-token scrap into a chunk already sitting at 1,000
    would quietly break it - measured, that is exactly what happened to 15 chunks
    (overflow 1-18 tokens, all below `MIN_CHUNK_TOKENS`). BR-31 already permits
    an undersized fragment to stand alone when it has nowhere to go, so the
    tie-break costs nothing: a slightly short chunk is a retrieval nuisance, an
    over-ceiling chunk is a correctness problem.
    """
    if not pieces:
        return []

    merged: list[tuple[int, int, int | None]] = []
    for start, end, section_ordinal in pieces:
        tokens = count_tokens(text[start:end])
        can_merge = (
            bool(merged)
            and tokens < min_tokens
            # same section only - None (unstructured) merges freely with None
            and merged[-1][2] == section_ordinal
            and count_tokens(text[merged[-1][0] : end]) <= max_tokens
        )
        if not can_merge:
            merged.append((start, end, section_ordinal))
            continue
        prev_start, _prev_end, prev_section = merged[-1]
        merged[-1] = (prev_start, end, prev_section)

    # A leading fragment has no predecessor; fold it forward, again only inside
    # its own section and only while the ceiling holds.
    if len(merged) > 1:
        first_start, first_end, first_section = merged[0]
        if (
            count_tokens(text[first_start:first_end]) < min_tokens
            and merged[1][2] == first_section
            and count_tokens(text[first_start : merged[1][1]]) <= max_tokens
        ):
            merged[0] = (first_start, merged[1][1], first_section)
            del merged[1]
    return merged


def _sections_are_too_small_to_cite(
    doc: StructuredDoc, text: str, min_tokens: int, max_tokens: int
) -> bool:
    """BR-31a - decide whether this document's sections can be citation units.

    An accident record has seven fields of 6-28 tokens describing one event, and
    one-section-one-chunk turned a 206-character record into seven chunks that
    retrieval could do nothing with. A substance record also has seven fields,
    but each is a 50-140 token paragraph about a distinct route of exposure and
    stands perfectly well alone.

    So the question is not the document type, it is whether the sections are
    individually substantial. The median is used rather than the mean or a
    strict all-of: one field that happens to land on the threshold should not
    change the verdict for the document, which is exactly what happened when
    this was tried piece by piece (`incident_area` at exactly 20 tokens split
    the record into four).

    When they are too small the whole document becomes one chunk carrying no
    section code - it spans all of them, so claiming one would be false.
    """
    if len(doc.sections) < 2:
        return False
    if count_tokens(text) > max_tokens:
        return False
    sizes = sorted(
        count_tokens(text[s.start_offset : s.end_offset]) for s in doc.sections
    )
    median = sizes[len(sizes) // 2]
    return median < min_tokens


def chunk_document(
    text: str,
    doc: StructuredDoc,
    base_meta: ChunkMeta,
    settings: Settings | None = None,
    section_clause_numbers: dict[int, list[str]] | None = None,
) -> list[Chunk]:
    settings = settings or get_settings()
    max_tokens = settings.max_chunk_tokens
    min_tokens = settings.min_chunk_tokens

    pieces: list[tuple[int, int, int | None]] = []

    if doc.structure_status is StructureStatus.STRUCTURED and doc.sections:
        for section in doc.sections:
            section_text = text[section.start_offset : section.end_offset]
            if count_tokens(section_text) <= max_tokens:
                # BR-26 - the common case: one section, one chunk.
                pieces.append((section.start_offset, section.end_offset, section.ordinal))
            else:
                for span_start, span_end in _split_oversized(text, section, max_tokens):
                    pieces.append((span_start, span_end, section.ordinal))
    else:
        # BR-28 - paragraph fallback for unstructured documents.
        synthetic = Section(
            ordinal=0, section_code=None, section_title=None,
            start_offset=0, end_offset=len(text),
        )
        for span_start, span_end in _split_oversized(text, synthetic, max_tokens):
            pieces.append((span_start, span_end, None))

    if _sections_are_too_small_to_cite(doc, text, min_tokens, max_tokens):
        first = min(s.start_offset for s in doc.sections)
        last = max(s.end_offset for s in doc.sections)
        pieces = [(first, last, None)]
    else:
        pieces = _merge_undersized(pieces, text, min_tokens, max_tokens)

    section_by_ordinal = {s.ordinal: s for s in doc.sections}
    clause_map = section_clause_numbers or {}
    chunks: list[Chunk] = []

    for ordinal, (start, end, section_ordinal) in enumerate(pieces):
        body = text[start:end]
        if not body.strip():
            continue
        section = section_by_ordinal.get(section_ordinal) if section_ordinal is not None else None
        meta = replace(
            base_meta,
            section_code=section.section_code if section else None,
            section_title=section.section_title if section else None,
            structure_status=doc.structure_status.value,
            clause_numbers=clause_map.get(section_ordinal, []) if section_ordinal is not None
            else [],
        )
        chunks.append(
            Chunk(
                ordinal=ordinal,
                text=body,
                token_count=count_tokens(body),
                # BR-30 - offsets index into extracted_text.text, and the chunk
                # body must be exactly that slice.
                start_offset=start,
                end_offset=end,
                section_ordinal=section_ordinal,
                meta=meta,
            )
        )
    return chunks
