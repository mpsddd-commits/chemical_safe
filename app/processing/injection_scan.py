"""N3 InjectionScanner - SP-4, SP-5.

Runs at index time and writes a flag into `chunk.meta`. The corpus changes far
less often than queries do, so scanning once costs the query path nothing.

**The flag never excludes anything** (SP-5). That is the design decision worth
defending, because excluding looks safer and is not. MSDS text is full of
imperatives by nature - "즉시 다량의 물로 씻어내십시오", "다음 절차를 따르십시오" -
and a scanner tuned to catch instructions will catch those. Excluding on
suspicion would turn this into a defence that deletes safety information, which
is the failure this system exists to prevent.

So the discrimination that matters is not "is this an instruction" but **"who is
this instruction addressed to"**. First-aid text instructs the reader to act on
a chemical. Injection instructs the *model* to change its behaviour. Only the
second is scored.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

# Attempts to rewrite the model's role or discard its instructions. None of
# these have an innocent reading inside an MSDS or a statute.
_ROLE_HIJACK = re.compile(
    r"(이전|위(의)?|앞(의)?)\s*(지시|명령|규칙|프롬프트)[^.\n]{0,12}(무시|잊)"
    r"|ignore\s+(all\s+)?(previous|prior|above)\s+(instructions?|prompts?)"
    r"|disregard\s+(the\s+)?(previous|above|system)"
    r"|system\s*prompt"
    r"|너는\s*이제"
    r"|you\s+are\s+now\s+a",
    re.IGNORECASE,
)

# Delimiter shapes borrowed from chat templates. Legitimate documents do not
# contain them.
_DELIMITERS = re.compile(
    r"<\s*/?\s*(evidence|question|sentence|document|system|instructions?)\b"
    r"|<\|[a-z_]+\|>"
    r"|\[/?INST\]"
    r"|###\s*(system|instruction)",
    re.IGNORECASE,
)

# Instructions about *output shape*. An MSDS tells you what to do with a
# chemical; it never tells you what format to answer in.
_OUTPUT_DIRECTIVE = re.compile(
    r"(그대로|정확히)\s*(출력|반환|답변)"
    r"|(로만|만)\s*(답|출력)하[라시]"
    r"|output\s+only"
    r"|respond\s+with\s+only"
    r"|reply\s+with\s+exactly",
    re.IGNORECASE,
)

_URL = re.compile(r"https?://", re.IGNORECASE)

# Below this length a couple of links is normal density, not a signal.
_URL_DENSITY_MIN_CHARS = 200
_URL_DENSITY_THRESHOLD = 4


@dataclass
class ScanResult:
    suspected: bool
    reasons: list[str] = field(default_factory=list)


def scan(text: str) -> ScanResult:
    """Heuristic. Any single hit flags; nothing here is a proof."""
    reasons: list[str] = []

    if _ROLE_HIJACK.search(text):
        reasons.append("role_hijack")
    if _DELIMITERS.search(text):
        reasons.append("delimiter_shape")
    if _OUTPUT_DIRECTIVE.search(text):
        reasons.append("output_directive")

    if len(text) >= _URL_DENSITY_MIN_CHARS:
        per_kchar = len(_URL.findall(text)) / (len(text) / 1000)
        if per_kchar >= _URL_DENSITY_THRESHOLD:
            reasons.append("url_density")

    return ScanResult(suspected=bool(reasons), reasons=reasons)
