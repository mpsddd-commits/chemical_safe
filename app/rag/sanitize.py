"""N2 EvidenceSanitizer - SP-3.

Evidence is placed inside an XML-ish structure, so the correct treatment is the
boring one: XML-escape it. After escaping there is no `<` left in the body, so
no tag can be forged at all - not the real per-request tag, not a plausible
looking `</document>`, not `<|im_start|>`.

**This transforms the prompt copy only.** `chunk.text` and
`citation_snapshot.snippet` keep the original bytes. If escaped text ever leaked
into a snippet, the evidence shown to the user would differ from the source and
BR-89/BR-30 would be broken - the user would be reading something we wrote.
"""

from __future__ import annotations

# Order matters: `&` first, or the escapes get escaped.
_ESCAPES = (("&", "&amp;"), ("<", "&lt;"), (">", "&gt;"))


def escape_for_prompt(text: str) -> str:
    """Neutralise markup so evidence cannot close its own block.

    Chemical and legal text does contain `<` (``pH < 2``); it arrives at the
    model as ``pH &lt; 2``, which reads correctly and cannot open a tag.
    """
    out = text
    for raw, escaped in _ESCAPES:
        out = out.replace(raw, escaped)
    return out


def escape_attr(value: str) -> str:
    """Attribute values additionally cannot carry a quote."""
    return escape_for_prompt(value).replace('"', "&quot;")
