"""Byte sizes as a person reads them - one place for every screen and message.

Before this, three call sites each divided by 1024**2 and picked a format:
`:.0f` for a limit, `:.1f` for a file, `'%.1f'` in a template. Under a limit
below 1MB that printed "파일 크기 0.0MB (한도 0MB)" - a rejection whose reason
says nothing (backlog B8).

Two rules, both about honesty rather than looks:

- **Sizes shown together share one unit**, chosen by the largest, so they can be
  compared at a glance.
- **Rounding never makes two different sizes look equal, and never makes a
  non-empty size look like zero.** A file one byte over a 1MB limit must not read
  "1MB (한도 1MB)" - that reads like the system rejecting a file that fits. More
  decimals are tried first; if even those collide, the exact byte counts are
  shown, because only they tell the truth.
"""

from __future__ import annotations

_KB = 1024
_MB = 1024 * 1024
_GB = 1024 * 1024 * 1024

# Decimals tried before giving up and printing exact bytes.
_MAX_DECIMALS = 3


def _unit_for(largest: int) -> tuple[int, str]:
    if largest >= _GB:
        return _GB, "GB"
    if largest >= _MB:
        return _MB, "MB"
    if largest >= _KB:
        return _KB, "KB"
    return 1, "바이트"


def _render(size: int, divisor: int, decimals: int) -> str:
    text = f"{size / divisor:.{decimals}f}"
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text


def _exact(size: int) -> str:
    return f"{size:,}바이트"


def format_sizes(*sizes: int) -> tuple[str, ...]:
    """Render sizes in one shared unit without rounding lying about them."""
    if not sizes:
        return ()
    if any(s < 0 for s in sizes):
        raise ValueError(f"negative size: {sizes}")
    divisor, unit = _unit_for(max(sizes))
    if divisor == 1:
        return tuple(_exact(s) for s in sizes)

    for decimals in range(1, _MAX_DECIMALS + 1):
        rendered = [_render(s, divisor, decimals) for s in sizes]
        honest = all(
            (rendered[i] == rendered[j]) == (sizes[i] == sizes[j])
            for i in range(len(sizes))
            for j in range(i + 1, len(sizes))
        ) and all(r != "0" or s == 0 for r, s in zip(rendered, sizes, strict=True))
        if honest:
            return tuple(f"{r}{unit}" for r in rendered)
    return tuple(_exact(s) for s in sizes)


def format_size(size: int) -> str:
    """A single size - the same rules with nothing to compare against."""
    return format_sizes(size)[0]
