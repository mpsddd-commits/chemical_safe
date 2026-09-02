"""C20 NormalizeStage (BR-14).

The output of this stage *is* `extracted_text.text`, and every offset stored
anywhere in the system points into it (FQ-5=A). Once a document has been
indexed, changing these rules invalidates its offsets - so re-normalising means
re-chunking, which is exactly what `reindex_document` does.
"""

from __future__ import annotations

import re
import unicodedata

# Control characters except tab and newline.
_CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
# A hyphen at end of line that splits a word across the break.
_HYPHEN_BREAK = re.compile(r"(\w)-[ \t]*\n[ \t]*(\w)")
_SPACES = re.compile(r"[ \t ]+")
_BLANK_LINES = re.compile(r"\n{3,}")
_TRAILING_WS = re.compile(r"[ \t]+\n")


def normalize(text: str) -> str:
    if not text:
        return ""
    # 4) unicode NFC first, so later regexes see composed characters
    out = unicodedata.normalize("NFC", text)
    # 1) strip control characters
    out = _CONTROL.sub("", out)
    out = out.replace("\r\n", "\n").replace("\r", "\n")
    # 3) rejoin hyphenated line breaks
    out = _HYPHEN_BREAK.sub(r"\1\2", out)
    # 2) collapse runs of spaces
    out = _SPACES.sub(" ", out)
    out = _TRAILING_WS.sub("\n", out)
    # keep paragraph breaks meaningful but bounded
    out = _BLANK_LINES.sub("\n\n", out)
    return out.strip()


def tabulate(rows: list[list[str]]) -> str:
    """5) render an extracted table as one line per row (BR-14)."""
    return "\n".join(" ".join(cell.strip() for cell in row if cell) for row in rows)
