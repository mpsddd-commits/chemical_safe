"""Incremental extraction of sentence text from a structured-output stream.

BR-79 forces the answer through a JSON schema, so what the model streams is
partial JSON - `{"sentences":[{"text":"분진·미스` - not prose. FQ2-13 and NFR-1
still want the body to appear as it is produced. This parser bridges the two by
pulling `sentences[].text` out of the byte stream as it arrives.

**It is display-only, and that is a safety property rather than a limitation.**
The authoritative answer is parsed from the complete JSON once the stream ends,
and only then does it pass the id whitelist (SP-8) and grounding verification
(BR-85~87). Nothing this parser emits is treated as an answer; it exists so the
user sees progress. Citations are attached after verification (FE-16), so a
sentence that later fails verification was never shown with evidence attached.

Deltas arrive at arbitrary byte boundaries - mid-escape, mid-codepoint, mid-key -
so every state here has to be resumable.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum, auto


class _State(Enum):
    SEEK_SENTENCES = auto()
    SEEK_ARRAY = auto()
    IN_ARRAY = auto()
    IN_OBJECT = auto()
    IN_KEY = auto()
    AFTER_KEY = auto()
    SEEK_VALUE = auto()
    IN_TEXT = auto()
    SKIP_VALUE_STRING = auto()
    SKIP_VALUE_OTHER = auto()


@dataclass
class SentenceStreamParser:
    """Feed it raw deltas; it calls back with text as sentences take shape."""

    on_delta: Callable[[int, str], None] | None = None
    on_sentence_end: Callable[[int], None] | None = None

    _state: _State = _State.SEEK_SENTENCES
    _buffer: str = ""
    _key: str = ""
    _escape: bool = False
    _unicode: str | None = None
    _depth: int = 0
    _index: int = -1
    texts: list[str] = field(default_factory=list)

    def feed(self, delta: str) -> None:
        for char in delta:
            self._consume(char)

    # ---- internals ----

    def _emit(self, text: str) -> None:
        if not text:
            return
        self.texts[self._index] += text
        if self.on_delta:
            self.on_delta(self._index, text)

    def _consume(self, char: str) -> None:  # noqa: C901 - a scanner is a switch
        state = self._state

        if state is _State.SEEK_SENTENCES:
            # Only the `sentences` key matters; everything before it is noise.
            self._buffer = (self._buffer + char)[-11:]
            if self._buffer.endswith('"sentences"'):
                self._state = _State.SEEK_ARRAY
            return

        if state is _State.SEEK_ARRAY:
            if char == "[":
                self._state = _State.IN_ARRAY
            return

        if state is _State.IN_ARRAY:
            if char == "{":
                self._index += 1
                self.texts.append("")
                self._state = _State.IN_OBJECT
            elif char == "]":
                self._state = _State.SEEK_SENTENCES
            return

        if state is _State.IN_OBJECT:
            if char == '"':
                self._key = ""
                self._state = _State.IN_KEY
            elif char == "}":
                if self.on_sentence_end:
                    self.on_sentence_end(self._index)
                self._state = _State.IN_ARRAY
            return

        if state is _State.IN_KEY:
            if char == '"':
                self._state = _State.AFTER_KEY
            else:
                self._key += char
            return

        if state is _State.AFTER_KEY:
            if char == ":":
                self._state = _State.SEEK_VALUE
            return

        if state is _State.SEEK_VALUE:
            if char.isspace():
                return
            if self._key == "text":
                # Only a string is a text value; anything else is malformed and
                # skipping it keeps the stream usable rather than raising.
                self._state = _State.IN_TEXT if char == '"' else _State.SKIP_VALUE_OTHER
                return
            if char == '"':
                self._state = _State.SKIP_VALUE_STRING
            elif char in "[{":
                self._depth = 1
                self._state = _State.SKIP_VALUE_OTHER
            else:
                self._depth = 0
                self._state = _State.SKIP_VALUE_OTHER
            return

        if state is _State.IN_TEXT:
            self._consume_text(char)
            return

        if state is _State.SKIP_VALUE_STRING:
            if self._escape:
                self._escape = False
            elif char == "\\":
                self._escape = True
            elif char == '"':
                self._state = _State.IN_OBJECT
            return

        if state is _State.SKIP_VALUE_OTHER:
            if char in "[{":
                self._depth += 1
            elif char in "]}":
                if self._depth <= 0:
                    # The closing brace belonged to the sentence object.
                    if self.on_sentence_end:
                        self.on_sentence_end(self._index)
                    self._state = _State.IN_ARRAY
                    return
                self._depth -= 1
                if self._depth == 0:
                    self._state = _State.IN_OBJECT
            elif char == "," and self._depth == 0:
                self._state = _State.IN_OBJECT
            return

    def _consume_text(self, char: str) -> None:
        # A `\uXXXX` escape can be split across deltas, so the digits are held
        # until all four arrive.
        if self._unicode is not None:
            self._unicode += char
            if len(self._unicode) == 4:
                try:
                    self._emit(chr(int(self._unicode, 16)))
                except ValueError:
                    pass
                self._unicode = None
            return

        if self._escape:
            self._escape = False
            if char == "u":
                self._unicode = ""
                return
            self._emit(
                {"n": "\n", "t": "\t", "r": "\r", "b": "\b", "f": "\f"}.get(char, char)
            )
            return

        if char == "\\":
            self._escape = True
            return

        if char == '"':
            self._state = _State.IN_OBJECT
            return

        self._emit(char)
