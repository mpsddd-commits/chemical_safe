"""Regressions for defects found on the first real query against PostgreSQL.

All three had passed unit tests and Docker start-up checks. They needed a real
question against a real corpus, which is the point worth keeping: u1's search
path had never actually been executed.
"""

from __future__ import annotations

import pytest

from app.core.config import Settings
from app.core.types import DocType
from app.indexing.keyword_index import KeywordIndex
from app.rag import refusal
from app.rag.types import Evidence


def _settings(**kw) -> Settings:
    return Settings(postgres_password="x", **kw)


def _evidence(
    chunk_id: int,
    relevance: float | None,
    score: float = 0.03,
    doc_type: DocType = DocType.LAW,
) -> Evidence:
    """Defaults to LAW deliberately.

    These tests pin "relevance decides, not RRF rank" (defect 27), which is
    orthogonal to BR-73a's subject-scope rule. Leaving the default at MSDS
    would make every one of them a test of BR-73a instead - the fixture, not
    the assertion, would be doing the deciding.
    """
    return Evidence(
        chunk_id=chunk_id,
        document_id=1,
        source_url="https://example.test/d",
        document_title="문서",
        section_code=None,
        section_title=None,
        text="본문",
        start_offset=0,
        end_offset=2,
        score=score,
        doc_type=doc_type,
        relevance=relevance,
    )


class TestKoreanTsQuery:
    """Defect: every multi-word question returned 0 keyword hits.

    `plainto_tsquery` joins terms with AND and the `simple` configuration does
    no stemming, so "황산 취급 시 보호구는?" required an exact match on
    "보호구는" — which the index never contains, because the text says "보호구".
    Measured before the fix: 0 hits for the sentence, 5 for the bare word.
    """

    def test_particles_are_trimmed(self):
        terms = KeywordIndex._tsquery_terms("황산 취급 시 보호구는")
        assert "보호구" in terms
        assert "보호구는" not in terms

    def test_terms_are_or_able_not_and_able(self):
        # The caller joins with ' | '; this asserts the pieces exist to do so.
        terms = KeywordIndex._tsquery_terms("화학물질 취급자의 교육 의무는")
        assert len(terms) >= 3

    def test_single_characters_are_dropped(self):
        """'시' and '의' carry no retrieval signal and match everything."""
        assert "시" not in KeywordIndex._tsquery_terms("황산 취급 시 보호구")

    def test_short_words_are_not_over_trimmed(self):
        """Trimming must not eat the word itself."""
        assert KeywordIndex._tsquery_terms("교육 의무") == ["교육", "의무"]

    def test_punctuation_cannot_reach_tsquery(self):
        """`to_tsquery` is strict; stray operators would raise a syntax error."""
        terms = KeywordIndex._tsquery_terms("보호구는? (황산) & 취급!")
        assert all(t.isalnum() for t in terms)

    def test_duplicates_are_collapsed(self):
        assert KeywordIndex._tsquery_terms("황산 황산 황산") == ["황산"]

    @pytest.mark.parametrize("query", ["", "   ", "?", "a", "시 의 을"])
    def test_empty_result_is_safe(self, query):
        """An empty term list must short-circuit — `to_tsquery('')` errors."""
        assert KeywordIndex._tsquery_terms(query) == []


class TestRefusalUsesRelevanceNotRank:
    """Defect: the threshold read the fused RRF score.

    RRF is a rank statistic. The top result of a query with no relevant
    documents scores exactly what the top result of a good query scores, so no
    threshold on it can separate them — measured, "오늘 점심 메뉴 추천해줘" and
    "황산 취급 시 보호구는?" produced the same fused score.
    """

    def test_off_topic_is_refused(self):
        settings = _settings(refusal_score_threshold=0.50)
        decision = refusal.decide([_evidence(1, relevance=0.42)], settings)
        assert decision.refused

    def test_on_topic_is_answered(self):
        settings = _settings(refusal_score_threshold=0.50)
        decision = refusal.decide([_evidence(1, relevance=0.66)], settings)
        assert not decision.refused

    def test_fused_score_does_not_decide(self):
        """Identical RRF scores, opposite verdicts — the old code could not."""
        settings = _settings(refusal_score_threshold=0.50)
        good = refusal.decide([_evidence(1, relevance=0.70, score=0.0328)], settings)
        bad = refusal.decide([_evidence(2, relevance=0.41, score=0.0328)], settings)
        assert not good.refused
        assert bad.refused

    def test_keyword_only_hit_is_not_treated_as_irrelevant(self):
        """An exact CAS match has no cosine score and is the best signal there is.

        Scoring it 0 would refuse exactly the queries this corpus answers best
        (BR-38).
        """
        settings = _settings(refusal_score_threshold=0.50)
        decision = refusal.decide([_evidence(1, relevance=None)], settings)
        assert not decision.refused

    def test_no_candidates(self):
        decision = refusal.decide([], _settings())
        assert decision.refused
        assert decision.reason.value == "no_candidates"

    def test_refusal_always_offers_links(self):
        """BR-75 — "I don't know" with nowhere to go is worse than a search engine."""
        settings = _settings(refusal_score_threshold=0.50)
        decision = refusal.decide(
            [_evidence(1, relevance=0.42), _evidence(2, relevance=0.40)], settings
        )
        assert decision.refused
        assert decision.links

    def test_links_are_deduplicated_by_document(self):
        """Five chunks of one statute is one place to go, not five."""
        links = refusal.source_links([_evidence(1, 0.4), _evidence(2, 0.4)])
        assert len(links) == 1


class TestExactIdentifierOverridesRelevance:
    """BR-38 — an identifier the user typed is a fact, not a fuzzy signal.

    Measured 2026-08-26: "CAS 75-31-0 물질에 노출되면 어떻게 해야 하나요?" matched
    the right substance record exactly through the keyword route and was refused
    at cosine 0.481 against a 0.50 threshold. The similarity score has no
    standing to overrule an exact match — the same class of mistake as defect 27,
    where the gate read a signal that could not answer the question being asked.
    """

    def _ev(self, *, relevance, keyword_score):
        from app.rag.types import RetrievalCandidate

        candidate = RetrievalCandidate(
            chunk_id=1,
            document_id=1,
            doc_type=DocType.MSDS,
            keyword_score=keyword_score,
            vector_score=relevance,
        )
        item = _evidence(1, relevance=relevance)
        item.exact_identifier = candidate.exact_identifier
        return item

    def test_exact_match_is_answered_below_threshold(self):
        settings = _settings(refusal_score_threshold=0.50)
        decision = refusal.decide(
            [self._ev(relevance=0.481, keyword_score=1.0)], settings
        )
        assert not decision.refused

    def test_a_text_search_hit_does_not_override(self):
        """`ts_rank` sits around 0.03~0.10 here; only 1.0 marks an exact hit."""
        settings = _settings(refusal_score_threshold=0.50)
        decision = refusal.decide(
            [self._ev(relevance=0.42, keyword_score=0.09)], settings
        )
        assert decision.refused

    def test_no_candidates_still_refuses(self):
        assert refusal.decide([], _settings()).refused

    def test_candidate_flag_reads_the_shared_constant(self):
        from app.indexing.keyword_index import EXACT_MATCH_SCORE
        from app.rag.types import RetrievalCandidate

        below = RetrievalCandidate(
            chunk_id=1, document_id=1, doc_type=DocType.MSDS,
            keyword_score=EXACT_MATCH_SCORE - 0.01,
        )
        at = RetrievalCandidate(
            chunk_id=1, document_id=1, doc_type=DocType.MSDS,
            keyword_score=EXACT_MATCH_SCORE,
        )
        assert not below.exact_identifier
        assert at.exact_identifier


class TestRouteSectionInference:
    """BR-65a - the tie-breaker among a resolved record's seven equal chunks.

    Measured without it: the record surfaced and sub-02/06/08 still scored
    0.000, because the fused top 5 held the wrong sections of the right record.
    """

    @pytest.mark.parametrize(
        ("query", "section"),
        [
            ("황산 증기를 흡입하면 어떤 증상이 나타나나요?", "substance_inhale"),
            ("암모니아가 눈에 들어가면 어떤 손상이 생기나요?", "substance_eye"),
            ("메탄올을 흡입하면 시각에 어떤 영향이 있나요?", "substance_inhale"),
            ("피부에 묻었을 때 어떻게 하나요?", "substance_skin"),
            ("삼켰을 때 치명적인 양은?", "substance_oral"),
        ],
    )
    def test_the_route_word_names_the_section(self, query, section):
        assert KeywordIndex._route_section(query) == section

    def test_no_route_word_means_no_section(self):
        """"염소에 노출되면 나타나는 일반적인 증상" - no route named; the
        fallback priority (symptom first) carries it instead."""
        assert KeywordIndex._route_section("염소는 어떻게 저장해야 하나요?") is None

    def test_inhale_beats_eye_when_both_appear(self):
        """sub-05 names both ("흡입하면 시각에") - patterns are ordered and the
        first match wins. The evidence for that question is the inhale section."""
        assert (
            KeywordIndex._route_section("메탄올을 흡입하면 시각에 어떤 영향이 있나요?")
            == "substance_inhale"
        )


def _cand(chunk_id, doc_type, score):
    from app.rag.types import RetrievalCandidate

    return RetrievalCandidate(
        chunk_id=chunk_id, document_id=chunk_id, doc_type=doc_type, fused_score=score
    )


class TestSubjectPresence:
    """BR-65a part 2 - the named substance must appear in the evidence head.

    Measured (run 239): "암모니아가 눈에 들어가면" put four *other* substances'
    eye sections in the top 4 - route words are generic, both routes light up,
    and the named substance's single-route exact hit loses the RRF race.
    """

    def test_a_missing_subject_is_lifted(self):
        from app.rag.retrieval.fusion import ensure_subject_presence

        head = [_cand(i, DocType.SUBSTANCE, 1.0 - i * 0.1) for i in range(5)]
        pool = head + [_cand(99, DocType.SUBSTANCE, 0.01)]
        result = ensure_subject_presence(head, pool, {99})
        assert any(c.chunk_id == 99 for c in result)
        assert len(result) == 5

    def test_a_present_subject_changes_nothing(self):
        from app.rag.retrieval.fusion import ensure_subject_presence

        head = [_cand(i, DocType.SUBSTANCE, 1.0 - i * 0.1) for i in range(5)]
        assert ensure_subject_presence(head, head, {2}) == head

    def test_no_subject_means_no_change(self):
        """A question naming nothing gets plain fused order - the guarantee
        only exists when the user actually named a substance."""
        from app.rag.retrieval.fusion import ensure_subject_presence

        head = [_cand(i, DocType.LAW, 1.0 - i * 0.1) for i in range(5)]
        assert ensure_subject_presence(head, head, set()) == head

    def test_a_subject_with_no_candidate_is_not_fabricated(self):
        """NFR-8 - the subject id set can only come from real exact hits, but
        the pool cut (fusion_top_k) may still have dropped them."""
        from app.rag.retrieval.fusion import ensure_subject_presence

        head = [_cand(i, DocType.LAW, 1.0 - i * 0.1) for i in range(5)]
        assert ensure_subject_presence(head, head, {777}) == head

    def test_displacement_prefers_the_over_represented_type(self):
        from app.rag.retrieval.fusion import ensure_subject_presence

        head = [
            _cand(1, DocType.SUBSTANCE, 0.9),
            _cand(2, DocType.SUBSTANCE, 0.8),
            _cand(3, DocType.SUBSTANCE, 0.7),
            _cand(4, DocType.MSDS, 0.6),
            _cand(5, DocType.LAW, 0.5),
        ]
        pool = head + [_cand(9, DocType.SUBSTANCE, 0.01)]
        result = ensure_subject_presence(head, pool, {9})
        # The weakest substance chunk (3) went; msds and law survived.
        ids = {c.chunk_id for c in result}
        assert 9 in ids and 3 not in ids
        assert {4, 5} <= ids


class TestMsdsTopicSections:
    """The MSDS half of the section map (2026-09-02).

    The CAS-meta sweep lifts a vendor MSDS's sixteen chunks along with the
    record's seven. Without a topic map, "황산은 어떻게 저장해야 하나요" broke
    the 23-way tie on row order and lifted 법적규제/참고사항 at the exact-match
    score - msds-02 measured 0.000 with its evidence in the same sweep.
    """

    @pytest.mark.parametrize(
        ("query", "section"),
        [
            ("황산은 어떻게 저장해야 하나요?", "msds_07"),
            ("취급할 때 주의사항은?", "msds_07"),
            ("어떤 보호구를 착용해야 하나요?", "msds_08"),
            ("국내 노출기준 TWA는?", "msds_08"),
            ("화재가 나면 어떻게 대처하나요?", "msds_05"),
            ("폐기할 때는?", "msds_13"),
        ],
    )
    def test_topic_words_name_msds_sections(self, query, section):
        assert section in KeywordIndex._preferred_sections(query)

    def test_a_route_word_still_names_the_substance_section(self):
        preferred = KeywordIndex._preferred_sections("흡입하면 어떻게 되나요?")
        assert "substance_inhale" in preferred

    def test_no_topic_means_no_preference(self):
        assert KeywordIndex._preferred_sections("이 물질은 무엇인가요?") == set()


class TestRefusalSubjectScope:
    """BR-73a - subject-scoped evidence with no identified subject.

    Measured 2026-09-02: "벤젠에 노출되면 어떤 응급조치를" scored 0.631 while
    "황산은 어떻게 저장해야 하나요" - answerable from this corpus - scored
    0.627. No threshold separates them, because the score measures topic and
    both are about first aid / storage of a chemical. The subject is what
    differs, and 카드뮴/벤젠 are in neither the master nor the corpus.
    """

    @staticmethod
    def _evidence(doc_type, relevance=0.63, exact=False):
        from app.rag.types import Evidence

        return Evidence(
            chunk_id=1,
            document_id=1,
            source_url="https://example.test",
            document_title="t",
            section_code=None,
            section_title=None,
            text="x",
            start_offset=0,
            end_offset=1,
            score=0.5,
            doc_type=doc_type,
            relevance=relevance,
            exact_identifier=exact,
        )

    def test_msds_evidence_without_a_subject_is_refused(self):
        from app.core.types import RefusalReason

        decision = refusal.decide([self._evidence(DocType.MSDS)], _settings())
        assert decision.refused
        assert decision.reason is RefusalReason.UNKNOWN_SUBJECT

    def test_substance_evidence_without_a_subject_is_refused(self):
        decision = refusal.decide([self._evidence(DocType.SUBSTANCE)], _settings())
        assert decision.refused

    def test_a_resolved_subject_still_answers(self):
        """BR-38's short-circuit runs first - a typed CAS or a resolved name
        marks the evidence exact, and this rule never sees it."""
        decision = refusal.decide(
            [self._evidence(DocType.MSDS, exact=True)], _settings()
        )
        assert not decision.refused

    def test_law_evidence_answers_without_a_subject(self):
        """A statute question names no substance and needs none."""
        decision = refusal.decide([self._evidence(DocType.LAW, 0.74)], _settings())
        assert not decision.refused

    def test_judged_on_the_top_candidate_not_all(self):
        """BR-69 lifts one chunk per missing type into the head, so an `all()`
        test is defeated by the spread rule itself - measured on ref-05, where
        a 제90조 chunk rode the spread into rank 5."""
        evidence = [
            self._evidence(DocType.MSDS),
            self._evidence(DocType.LAW, 0.4),
        ]
        assert refusal.decide(evidence, _settings()).refused

    def test_a_refusal_still_offers_links(self):
        """BR-75 - never a dead end."""
        decision = refusal.decide([self._evidence(DocType.MSDS)], _settings())
        assert decision.links

    def test_an_upload_is_not_subject_scoped(self):
        """We do not get to declare what a user uploaded, and refusing their
        own document back at them is the wrong side of this trade."""
        decision = refusal.decide(
            [self._evidence(DocType.USER_UPLOAD)], _settings()
        )
        assert not decision.refused


class TestRefusalTextsAgree:
    def test_every_reason_has_text_in_both_renderers(self):
        """The SSR map and the streaming client's map render the same refusal.
        A reason in one but not the other degrades silently to the generic
        fallback - the failure this test exists to make loud."""
        import re
        from pathlib import Path

        from app.core.types import RefusalReason

        root = Path(__file__).resolve().parents[2]
        # Read as text rather than importing: `pages.py` pulls in Jinja2 and
        # FastAPI, and the unit run must stay import-light (NFR-28).
        py = (root / "app" / "web" / "routers" / "pages.py").read_text(encoding="utf-8")
        py_block = py.split("REFUSAL_TEXT = {", 1)[1].split("\n}", 1)[0]
        in_py = set(re.findall(r'"(\w+)":', py_block))

        js = (root / "app" / "web" / "static" / "query.js").read_text(encoding="utf-8")
        block = js.split("REFUSAL_TEXT = {", 1)[1].split("};", 1)[0]
        in_js = set(re.findall(r"^\s*(\w+):", block, re.MULTILINE))

        for reason in RefusalReason:
            assert reason.value in in_py, f"pages.py 에 {reason.value} 문구 없음"
            assert reason.value in in_js, f"query.js 에 {reason.value} 문구 없음"


class TestUnknownSubjectRefusalText:
    """Backlog D10. `UNKNOWN_SUBJECT` covers two situations the code cannot
    tell apart - the question named no substance, or it named one the corpus
    does not hold - so the text may only say what is true in both. The old
    wording did neither: it asserted we could not tell which substance was
    asked about (false when the user wrote 카드뮴 plainly) and promised an
    answer if they named it (false, because naming it changes nothing when the
    material is absent). Both send the user to rewrite a question instead of
    reading an MSDS."""

    @staticmethod
    def _texts():
        import re
        from pathlib import Path

        root = Path(__file__).resolve().parents[2]
        # Text, not imports - same reason as TestRefusalTextsAgree above.
        py = (root / "app" / "web" / "routers" / "pages.py").read_text(encoding="utf-8")
        js = (root / "app" / "web" / "static" / "query.js").read_text(encoding="utf-8")

        py_entry = py.split('"unknown_subject": (', 1)[1].split("),", 1)[0]
        js_entry = js.split("\n    unknown_subject:", 1)[1].split("\n  };", 1)[0]
        # Both renderers write the sentence as adjacent string literals, so the
        # literals joined in order are the sentence the user reads.
        return (
            "".join(re.findall(r'"([^"]*)"', py_entry)),
            "".join(re.findall(r'"([^"]*)"', js_entry)),
        )

    def test_the_two_renderers_show_the_same_sentence(self):
        """SSR and streaming render the same refusal. Agreeing on the key is
        not enough - a divergent sentence shows a different refusal depending
        on which path served the request."""
        py_text, js_text = self._texts()
        assert py_text == js_text

    def test_it_makes_no_claim_about_what_the_user_asked(self):
        """The system is not in a position to judge what the user wrote: an
        unresolved name never reaches `substance_names`, so a question naming
        카드뮴 is indistinguishable from one naming nothing."""
        for name, text in zip(("pages.py", "query.js"), self._texts(), strict=True):
            for claim in ("확인하지 못했", "파악하지 못했", "질문인지", "알아듣"):
                assert claim not in text, f"{name} 가 사용자 질문을 단정함: {claim}"

    def test_it_promises_no_answer_it_cannot_give(self):
        """Naming the substance does not produce an answer when the corpus has
        no material for it - 카드뮴 with CAS 7440-43-9 returns this same
        refusal."""
        for name, text in zip(("pages.py", "query.js"), self._texts(), strict=True):
            for promise in ("주시면", "하시면 답", "답변합니다", "답변해 드립"):
                assert promise not in text, f"{name} 가 지킬 수 없는 약속을 함: {promise}"

    def test_it_makes_no_claim_about_what_the_corpus_holds(self):
        """The reason fires when a name fails to RESOLVE, which is not the same
        as the material being absent. Measured 2026-09-10 with
        `EntityExtractor.extract`, entity LLM off: H2SO4 저장법 and 유산은
        어떻게 저장하나요 both yield names=[] and land here, while 황산 is held
        - two MSDS documents plus a substance record. So a sentence saying the
        corpus does not have it is false for every question that names a held
        substance by an unlisted synonym, and synonyms average two per
        substance. The text may say it did not find, never that we do not
        have."""
        for name, text in zip(("pages.py", "query.js"), self._texts(), strict=True):
            for claim in ("없습니다", "보유", "가지고 있지", "갖고 있지", "미보유"):
                assert claim not in text, f"{name} 가 보유 여부를 단정함: {claim}"

    def test_it_points_at_the_substance_list(self):
        """The useful next action is checking what the corpus holds, which the
        substance list answers exactly. Rewriting the question does not."""
        for name, text in zip(("pages.py", "query.js"), self._texts(), strict=True):
            assert "물질" in text and "목록" in text, f"{name} 가 물질 목록을 가리키지 않음"


class TestRefusalHeadlinesAgree:
    """The refusal headline is the first thing read, so it must not contradict
    the reason printed under it. Fixed headline text told every refusal it was
    a missing-evidence refusal, including `verification_unavailable`, which is
    the one refusal that is explicitly not the user's question's fault."""

    @staticmethod
    def _maps():
        import re
        from pathlib import Path

        root = Path(__file__).resolve().parents[2]
        # Text, not imports - same reason as TestRefusalTextsAgree above.
        py = (root / "app" / "web" / "routers" / "pages.py").read_text(encoding="utf-8")
        js = (root / "app" / "web" / "static" / "query.js").read_text(encoding="utf-8")

        py_default = re.search(r'DEFAULT_REFUSAL_HEADLINE = "([^"]+)"', py).group(1)
        js_default = re.search(r'DEFAULT_REFUSAL_HEADLINE = "([^"]+)"', js).group(1)

        py_block = py.split("\nREFUSAL_HEADLINE = {", 1)[1].split("\n}", 1)[0]
        js_block = js.split("REFUSAL_HEADLINE = {", 1)[1].split("};", 1)[0]
        py_map = dict(re.findall(r'"(\w+)": "([^"]*)"', py_block))
        js_map = dict(re.findall(r'(\w+): "([^"]*)"', js_block))
        return py_default, js_default, py_map, js_map

    def test_the_two_renderers_show_the_same_headlines(self):
        py_default, js_default, py_map, js_map = self._maps()
        assert py_default == js_default
        assert py_map == js_map

    def test_verification_unavailable_does_not_say_evidence_was_missing(self):
        """C15's refusal means nothing was judged. A headline claiming we found
        no evidence sends the user to rewrite a question that was fine."""
        _, _, py_map, js_map = self._maps()
        for name, headline in (("pages.py", py_map), ("query.js", js_map)):
            assert "verification_unavailable" in headline, f"{name} 에 헤드라인 없음"
            assert "근거를 찾지 못했" not in headline["verification_unavailable"], (
                f"{name} 의 verification_unavailable 헤드라인이 사유를 반박함"
            )

    def test_every_other_reason_keeps_the_original_headline(self):
        """Most refusals really are "we looked and found nothing", and that
        headline is right for them. Only the reason that needs a different one
        gets one."""
        from app.core.types import RefusalReason

        py_default, _, py_map, js_map = self._maps()
        assert "근거를 찾지 못했습니다" in py_default
        for reason in RefusalReason:
            if reason is RefusalReason.VERIFICATION_UNAVAILABLE:
                continue
            assert reason.value not in py_map, f"pages.py 가 {reason.value} 헤드라인을 바꿈"
            assert reason.value not in js_map, f"query.js 가 {reason.value} 헤드라인을 바꿈"

    def test_the_template_holds_no_headline_text_of_its_own(self):
        """A copy in the template would be a second owner of the sentence and
        would go on showing through whatever pages.py chose."""
        import re
        from pathlib import Path

        root = Path(__file__).resolve().parents[2]
        html = (root / "app" / "web" / "templates" / "query.html").read_text(
            encoding="utf-8"
        )
        body = re.sub(r"\{#.*?#\}", "", html, flags=re.DOTALL)
        assert "근거를 찾지 못했습니다" not in body
        assert "{{ refusal_headline }}" in body
