"""Token counting for chunk sizing (BR-27, BR-31).

Chunk bounds only need a *stable* size signal, not exact model tokenisation, so
the default is a heuristic with no dependencies. Korean text averages roughly
1.3 characters per token for common subword vocabularies; ASCII runs closer to
4. Counting both parts separately is noticeably better than one flat divisor.

If exact counts ever matter, replace `count_tokens` with the embedding model's
own tokenizer - it is deliberately a single function.
"""

from __future__ import annotations

_KO_CHARS_PER_TOKEN = 1.3
_OTHER_CHARS_PER_TOKEN = 4.0


def _is_hangul(ch: str) -> bool:
    code = ord(ch)
    return (
        0xAC00 <= code <= 0xD7A3  # syllables
        or 0x1100 <= code <= 0x11FF  # jamo
        or 0x3130 <= code <= 0x318F  # compatibility jamo
    )


def count_tokens(text: str) -> int:
    if not text:
        return 0
    hangul = sum(1 for ch in text if _is_hangul(ch))
    other = len(text) - hangul
    estimate = hangul / _KO_CHARS_PER_TOKEN + other / _OTHER_CHARS_PER_TOKEN
    return max(1, int(round(estimate)))
