"""Shared structuring for flat "label: value" records (BR-25).

Accident records and substance records arrive as flat key/value data that
`extract` has already rendered one field per line. Both turn each known field
into one section, and both need a section to run from its label to the *next*
label rather than to the end of the line: a field whose value carries its own
line breaks (an accident summary, a paragraph of exposure symptoms) would
otherwise be truncated at the first newline, and text that falls outside every
section is never chunked (BR-26) — silent data loss.

An absent field produces no section at all rather than an empty one, so a chunk
never claims to describe damage that was never reported (NFR-8).
"""

from __future__ import annotations

import re

from app.core.types import Section, StructureStatus

# (section code, display title, label aliases)
FieldTable = list[tuple[str, str, tuple[str, ...]]]


def find_sections(text: str, fields: FieldTable) -> tuple[list[Section], StructureStatus]:
    found: list[tuple[int, int, str, str]] = []
    for code, title, labels in fields:
        pattern = re.compile(
            r"^[ \t]*(?:" + "|".join(re.escape(label) for label in labels) + r")\s*[:：]",
            re.MULTILINE | re.IGNORECASE,
        )
        match = pattern.search(text)
        if match is None:
            continue
        found.append((match.start(), match.end(), code, title))

    if not found:
        return [], StructureStatus.UNSTRUCTURED

    # Document order, so a chunk's ordinal matches where it actually appears.
    found.sort(key=lambda item: item[0])

    sections: list[Section] = []
    for index, (start, label_end, code, title) in enumerate(found):
        last = index + 1 == len(found)
        end = len(text.rstrip()) if last else found[index + 1][0]
        if end <= label_end:
            continue
        sections.append(
            Section(
                ordinal=len(sections),
                section_code=code,
                section_title=title,
                start_offset=start,
                end_offset=end,
            )
        )

    if not sections:
        return [], StructureStatus.UNSTRUCTURED
    return sections, StructureStatus.STRUCTURED
