"""S4 SubstanceService - workflows W13 and W14 (FR-23~26).

**No LLM.** The card is a structured lookup, which is why NFR-3's one-second
budget is comfortable (u2 measured the pure-DB path at 26ms) and why the free
tier's daily quota does not touch this unit at all.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.substances.card import SubstanceCardBuilder
from app.substances.lookup import KeySupport, SubstanceLookup
from app.substances.types import SubstanceCard, SubstanceRef


class SubstanceService:
    def __init__(self, session: Session) -> None:
        self._lookup = SubstanceLookup(session)
        self._builder = SubstanceCardBuilder(session)

    def search(self, query: str) -> tuple[list[SubstanceRef], KeySupport]:
        """W13 - returns (candidates, which key types the data can answer).

        The key support travels with every result rather than living only in
        the template, so a screen cannot quietly omit that UN numbers have no
        data behind them, or that aliases exist for some substances only
        (BR-109, BR-110). Same device as u2's `unpriced_calls`.
        """
        return self._lookup.search(query), self._lookup.key_support()

    def key_support(self) -> KeySupport:
        """The same notice for a page that has not searched yet."""
        return self._lookup.key_support()

    def card(self, substance_id: int) -> SubstanceCard | None:
        """W14 - seven items, always, in order (BR-102)."""
        ref = self._lookup.get(substance_id)
        if ref is None:
            return None
        return self._builder.build(ref)
