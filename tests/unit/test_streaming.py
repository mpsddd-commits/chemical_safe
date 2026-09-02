"""Incremental sentence extraction from a structured-output stream (FQ2-13).

Deltas arrive at arbitrary byte boundaries, so the property that matters is:
**the result is independent of how the stream was chopped up.** Most of these
tests feed the same JSON at different chunk sizes and assert the same output.
"""

from __future__ import annotations

import json

import pytest
from hypothesis import given
from hypothesis import settings as hyp_settings
from hypothesis import strategies as st

from app.rag.streaming import SentenceStreamParser


def _feed(payload: str, size: int) -> SentenceStreamParser:
    parser = SentenceStreamParser()
    for i in range(0, len(payload), size):
        parser.feed(payload[i : i + size])
    return parser


ANSWER = json.dumps(
    {
        "sentences": [
            {"text": "분진·미스트 발생 시 방진마스크를 착용해야 합니다.", "chunk_ids": [1]},
            {"text": "내산성 보호장갑과 보안경을 착용합니다.", "chunk_ids": [2, 3]},
        ]
    },
    ensure_ascii=False,
)


class TestExtraction:
    def test_sentences_are_recovered(self):
        parser = _feed(ANSWER, len(ANSWER))
        assert parser.texts == [
            "분진·미스트 발생 시 방진마스크를 착용해야 합니다.",
            "내산성 보호장갑과 보안경을 착용합니다.",
        ]

    @pytest.mark.parametrize("size", [1, 2, 3, 5, 7, 13, 64, 1000])
    def test_chunk_boundaries_do_not_matter(self, size):
        assert _feed(ANSWER, size).texts == _feed(ANSWER, len(ANSWER)).texts

    def test_ascii_escaped_payload_is_recovered(self):
        """`ensure_ascii=True` turns every Hangul character into `\\uXXXX`."""
        escaped = json.dumps(json.loads(ANSWER), ensure_ascii=True)
        assert _feed(escaped, 3).texts == _feed(ANSWER, 1000).texts

    def test_split_unicode_escape(self):
        """A `\\uXXXX` escape cut in half across two deltas."""
        parser = SentenceStreamParser()
        parser.feed('{"sentences":[{"text":"\\u5b')
        parser.feed('89전"}]}')
        assert parser.texts == ["安전"]

    def test_escaped_quote_does_not_end_the_sentence(self):
        parser = SentenceStreamParser()
        parser.feed('{"sentences":[{"text":"그는 \\"안전\\" 이라 말했다."}]}')
        assert parser.texts == ['그는 "안전" 이라 말했다.']

    def test_chunk_ids_before_text_are_skipped(self):
        """Key order is the model's choice, not ours."""
        payload = '{"sentences":[{"chunk_ids":[1,2],"text":"본문."}]}'
        assert _feed(payload, 4).texts == ["본문."]

    def test_other_top_level_keys_are_ignored(self):
        payload = '{"note":"sentences are below","sentences":[{"text":"본문."}]}'
        assert _feed(payload, 5).texts == ["본문."]


class TestCallbacks:
    def test_deltas_arrive_with_their_sentence_index(self):
        seen: list[tuple[int, str]] = []
        parser = SentenceStreamParser(on_delta=lambda i, t: seen.append((i, t)))
        parser.feed(ANSWER)
        assert {i for i, _ in seen} == {0, 1}
        assert "".join(t for i, t in seen if i == 0) == parser.texts[0]

    def test_sentence_end_fires_once_per_sentence(self):
        ends: list[int] = []
        parser = SentenceStreamParser(on_sentence_end=ends.append)
        parser.feed(ANSWER)
        assert ends == [0, 1]

    def test_partial_stream_still_yields_what_arrived(self):
        """NFR-1 — the point is showing progress before the stream completes."""
        parser = SentenceStreamParser()
        parser.feed('{"sentences":[{"text":"분진·미스')
        assert parser.texts == ["분진·미스"]


class TestRobustness:
    @pytest.mark.parametrize(
        "payload",
        [
            "",
            "{}",
            '{"sentences":[]}',
            '{"sentences":[{}]}',
            '{"sentences":[{"text":null}]}',
            "not json at all",
            '{"sentences":[{"text":',
        ],
    )
    def test_malformed_input_never_raises(self, payload):
        SentenceStreamParser().feed(payload)

    @hyp_settings(max_examples=100, deadline=None)
    @given(
        sentences=st.lists(
            st.text(alphabet="가나다 abc.\\\"\n", min_size=0, max_size=40),
            min_size=0,
            max_size=5,
        ),
        size=st.integers(min_value=1, max_value=32),
    )
    def test_any_payload_survives_any_chunking(self, sentences, size):
        payload = json.dumps(
            {"sentences": [{"text": s, "chunk_ids": [1]} for s in sentences]},
            ensure_ascii=False,
        )
        assert _feed(payload, size).texts == sentences
