"""C44 GoldenSetLoader - FR-36, BR-111~BR-114.

The loader validates **everything before anything runs**. A full evaluation
takes days on the free tier; a typo discovered on day seven is a week thrown
away, and validation costs nothing but SQL.

Two kinds of check happen here and they are different in kind:

  * **Schema** - shape, required fields, no duplicate ids, a refusal question
    carrying evidence (which would mean the author disagreed with themselves).
  * **Corpus** - every `EvidenceRef` actually resolves to a document, and to a
    section when one is named. This is the check that catches a renamed section
    code after a parsing-rule change, and it is why the loader takes a session.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import yaml
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import ConfigurationError
from app.db.models import Document, DocumentSection, Source
from app.evaluation.types import EvidenceRef, Expects, GoldenQuestion, GoldenSet

_ALLOWED_CATEGORIES = {"law", "substance", "msds", "incident", "refusal"}


class GoldenSetError(ConfigurationError):
    """Raised before a single question is scored."""


class GoldenSetLoader:
    def __init__(self, session: Session | None = None) -> None:
        # Optional so the schema half can be unit-tested without a database
        # (NFR-28). `load` without a session skips the corpus check and says so.
        self._s = session

    def load(self, path: str | Path) -> GoldenSet:
        path = Path(path)
        if not path.exists():
            raise GoldenSetError(f"golden set not found: {path}")

        raw = path.read_text(encoding="utf-8")
        data = yaml.safe_load(raw) or {}
        questions = self._parse(data)
        if self._s is not None:
            self._verify_against_corpus(questions)
        return GoldenSet(
            path=str(path),
            sha256=hashlib.sha256(raw.encode("utf-8")).hexdigest(),
            questions=tuple(questions),
        )

    @staticmethod
    def fingerprint(path: str | Path) -> str:
        return hashlib.sha256(Path(path).read_bytes()).hexdigest()

    # ---- schema ----
    def _parse(self, data: dict) -> list[GoldenQuestion]:
        items = data.get("questions")
        if not isinstance(items, list) or not items:
            raise GoldenSetError("golden set declares no questions")

        seen: set[str] = set()
        parsed: list[GoldenQuestion] = []
        for index, item in enumerate(items):
            if not isinstance(item, dict):
                raise GoldenSetError(f"question #{index} is not a mapping")
            qid = str(item.get("id") or "").strip()
            if not qid:
                raise GoldenSetError(f"question #{index} has no id")
            if qid in seen:
                raise GoldenSetError(f"duplicate question id: {qid}")
            seen.add(qid)

            question = str(item.get("question") or "").strip()
            if not question:
                raise GoldenSetError(f"{qid}: question text is empty")

            category = str(item.get("category") or "").strip()
            if category not in _ALLOWED_CATEGORIES:
                raise GoldenSetError(f"{qid}: unknown category {category!r}")

            try:
                expects = Expects(str(item.get("expects")))
            except ValueError as exc:
                raise GoldenSetError(
                    f"{qid}: expects must be 'answer' or 'refusal'"
                ) from exc

            evidence = self._parse_evidence(qid, item.get("evidence") or [])
            points = tuple(
                str(p).strip() for p in (item.get("answer_points") or []) if str(p).strip()
            )

            if expects is Expects.ANSWER:
                if not evidence:
                    raise GoldenSetError(f"{qid}: an answer question needs evidence")
                if not points:
                    # Without these the judge has nothing to compare against and
                    # the accuracy metric silently becomes "did it say anything".
                    raise GoldenSetError(f"{qid}: an answer question needs answer_points")
            elif evidence:
                # A refusal question with evidence means the author expected an
                # answer somewhere in their head. Better to stop than to guess.
                raise GoldenSetError(f"{qid}: a refusal question must have no evidence")

            parsed.append(
                GoldenQuestion(
                    id=qid,
                    category=category,
                    question=question,
                    expects=expects,
                    answer_points=points,
                    evidence=evidence,
                    rationale=(str(item["rationale"]).strip() if item.get("rationale") else None),
                )
            )
        return parsed

    @staticmethod
    def _parse_evidence(qid: str, raw: object) -> tuple[EvidenceRef, ...]:
        if not isinstance(raw, list):
            raise GoldenSetError(f"{qid}: evidence must be a list")
        refs: list[EvidenceRef] = []
        for entry in raw:
            if not isinstance(entry, dict):
                raise GoldenSetError(f"{qid}: evidence entry is not a mapping")
            source = str(entry.get("source") or "").strip()
            external_id = str(entry.get("external_id") or "").strip()
            if not source or not external_id:
                raise GoldenSetError(f"{qid}: evidence needs source and external_id")
            section = entry.get("section")
            refs.append(
                EvidenceRef(
                    source=source,
                    external_id=external_id,
                    section=str(section).strip() if section else None,
                )
            )
        return tuple(refs)

    # ---- corpus ----
    def _verify_against_corpus(self, questions: list[GoldenQuestion]) -> None:
        assert self._s is not None
        problems: list[str] = []
        for question in questions:
            for ref in question.evidence:
                source_pk = self._s.scalar(
                    select(Source.id).where(Source.source_id == ref.source)
                )
                if source_pk is None:
                    problems.append(f"{question.id}: no such source {ref.source!r}")
                    continue
                document_id = self._s.scalar(
                    select(Document.id).where(
                        Document.source_id == source_pk,
                        Document.external_id == ref.external_id,
                    )
                )
                if document_id is None:
                    problems.append(
                        f"{question.id}: {ref.source}:{ref.external_id} is not in the corpus"
                    )
                    continue
                if ref.section is None:
                    continue
                section_id = self._s.scalar(
                    select(DocumentSection.id).where(
                        DocumentSection.document_id == document_id,
                        DocumentSection.section_code == ref.section,
                    )
                )
                if section_id is None:
                    problems.append(
                        f"{question.id}: {ref.source}:{ref.external_id} has no section "
                        f"{ref.section!r}"
                    )
        if problems:
            # All of them, not the first. Fixing a golden set one error per run
            # is exactly the loop this check exists to avoid.
            raise GoldenSetError(
                f"{len(problems)} golden set reference(s) do not resolve:\n  "
                + "\n  ".join(problems)
            )
