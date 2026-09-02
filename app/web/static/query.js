/* P5 streaming client (FQ2-13, NFR-1).
 *
 * Progressive enhancement, matching u1's DD-17: without JavaScript the form
 * posts to /query and gets a server-rendered answer. This file intercepts the
 * submit and streams instead, so the body appears while it is generated.
 *
 * The rule this file must not break: **streamed text carries no citation
 * badges.** Deltas are provisional - not yet id-checked (SP-8), not yet
 * verified (BR-85~87). Badges and evidence cards are rendered only from the
 * `final` event. Showing a badge early would let someone read and trust a
 * citation that is about to be withdrawn.
 */
(function () {
  "use strict";

  const form = document.querySelector('[data-testid="query-form"]');
  if (!form || !window.fetch || !window.TextDecoder) return; // fall back to POST /query

  const input = document.querySelector('[data-testid="query-input"]');
  const status = document.querySelector('[data-testid="query-status"]');
  const answerSection = document.querySelector('[data-testid="answer-section"]');
  const answerBody = document.querySelector('[data-testid="answer-body"]');
  const removedNotice = document.querySelector('[data-testid="removed-notice"]');
  const evidenceSection = document.querySelector('[data-testid="evidence-section"]');
  const evidenceList = document.querySelector('[data-testid="evidence-list"]');
  const refusalSection = document.querySelector('[data-testid="refusal-section"]');
  const refusalReason = document.querySelector('[data-testid="refusal-reason"]');
  const refusalLinks = document.querySelector('[data-testid="refusal-links"]');

  // Internal reason codes never reach the screen (frontend-components.md).
  const REFUSAL_TEXT = {
    no_candidates: "관련 문서를 찾지 못했습니다.",
    below_threshold: "검색된 문서의 관련도가 기준에 미치지 못했습니다.",
    all_sentences_unsupported: "생성된 문장이 근거로 뒷받침되지 않았습니다.",
    provider_refusal: "모델이 이 질문에 대한 답변을 거부했습니다.",
    // BR-73a. Must stay in step with REFUSAL_TEXT in web/routers/pages.py:
    // the SSR and the streaming path render the same refusal from two maps,
    // and a reason present in one but not the other silently degrades to the
    // generic fallback. A unit test pins the two together.
    unknown_subject:
      "어떤 물질에 대한 질문인지 확인하지 못했습니다. 물질명이나 CAS 번호를 함께 " +
      "적어 주시면 해당 물질의 자료로 답변합니다. 아래는 검색된 문서입니다."
  };

  function setStatus(text) {
    status.textContent = text;
    status.hidden = !text;
  }

  function reset() {
    answerSection.hidden = true;
    evidenceSection.hidden = true;
    refusalSection.hidden = true;
    removedNotice.hidden = true;
    answerBody.replaceChildren();
    evidenceList.replaceChildren();
    refusalLinks.replaceChildren();
  }

  const sentenceNodes = new Map();

  function sentenceNode(index) {
    let node = sentenceNodes.get(index);
    if (!node) {
      node = document.createElement("p");
      node.className = "answer-sentence provisional";
      node.dataset.testid = "answer-sentence";
      node.dataset.index = String(index);
      answerBody.appendChild(node);
      sentenceNodes.set(index, node);
    }
    return node;
  }

  function onToken(data) {
    answerSection.hidden = false;
    // textContent, never innerHTML: this text came from documents we did not
    // write, so it is data all the way to the screen.
    sentenceNode(data.sentence).textContent += data.text;
  }

  function onFinal(data) {
    // Re-render from the authoritative result. Provisional nodes are discarded
    // rather than patched: what survived verification may differ from what
    // streamed, and reconciling in place is how the two quietly diverge.
    answerBody.replaceChildren();
    sentenceNodes.clear();
    answerSection.hidden = false;

    const rank = new Map();
    (data.citations || []).forEach(function (c) {
      if (!rank.has(c.chunk_id)) rank.set(c.chunk_id, rank.size + 1);
    });

    (data.sentences || []).forEach(function (s) {
      const p = document.createElement("p");
      p.className = "answer-sentence";
      p.dataset.testid = "answer-sentence";
      p.textContent = s.text + " ";
      (s.chunk_ids || []).forEach(function (id) {
        const badge = document.createElement("sup");
        badge.className = "citation-badge";
        badge.dataset.testid = "citation-badge";
        badge.textContent = "[" + (rank.get(id) || "?") + "]";
        badge.tabIndex = 0;
        badge.addEventListener("click", function () {
          const card = evidenceList.querySelector('[data-chunk-id="' + id + '"]');
          if (card) {
            card.scrollIntoView({ behavior: "smooth", block: "center" });
            card.classList.add("highlight");
            setTimeout(function () { card.classList.remove("highlight"); }, 1600);
          }
        });
        p.appendChild(badge);
      });
      answerBody.appendChild(p);
    });

    if (data.removed) {
      // BR-88 - state the count. An answer must not look complete when it isn't.
      // And say *why*: a sentence we judged unsupported and one we never got to
      // ask about are different facts.
      var note = "ℹ️ 근거가 확인되지 않은 문장 " + data.removed + "개를 제외했습니다.";
      if (data.quota_blocked) {
        note +=
          " (그중 " + data.quota_blocked +
          "개는 판정 결과가 아니라 LLM 할당량 소진으로 확인하지 못한 것입니다.)";
      }
      removedNotice.textContent = note;
      removedNotice.hidden = false;
    }

    const seen = new Set();
    (data.citations || []).forEach(function (c) {
      if (seen.has(c.chunk_id)) return;
      seen.add(c.chunk_id);
      const li = document.createElement("li");
      li.dataset.chunkId = String(c.chunk_id);
      li.dataset.testid = "evidence-card";

      const title = document.createElement("strong");
      title.textContent = c.title || "(제목 없음)";
      li.appendChild(title);

      const label = document.createElement("div");
      label.className = "evidence-label";
      // BR-90 - "섹션 정보 없음" is written out; a blank reads as a load failure.
      label.textContent = c.section_code || "섹션 정보 없음";
      li.appendChild(label);

      const snippet = document.createElement("blockquote");
      snippet.textContent = c.snippet;
      li.appendChild(snippet);

      const link = document.createElement("a");
      link.href = c.source_url;
      link.rel = "noopener noreferrer";
      link.target = "_blank";
      link.textContent = "🔗 원문 보기";
      li.appendChild(link);

      evidenceList.appendChild(li);
    });
    evidenceSection.hidden = seen.size === 0;
    setStatus("");
  }

  function onRefused(data) {
    refusalSection.hidden = false;
    refusalReason.textContent =
      "사유: " + (REFUSAL_TEXT[data.reason] || "답변할 근거가 부족합니다.");
    (data.links || []).forEach(function (l) {
      const li = document.createElement("li");
      const a = document.createElement("a");
      a.href = l.source_url;
      a.rel = "noopener noreferrer";
      a.target = "_blank";
      a.textContent = (l.title || l.source_url) + (l.section_code ? " " + l.section_code : "");
      li.appendChild(a);
      refusalLinks.appendChild(li);
    });
    setStatus("");
  }

  // Exactly one of final/refused always arrives (see the router docstring).
  // This flag is how the client tells "finished" from "connection dropped".
  let terminal = false;

  function dispatch(event, data) {
    if (event === "final" || event === "refused") terminal = true;
    if (event === "retrieval") {
      setStatus(
        data.count > 0
          ? "근거 " + data.count + "건 확인. 답변 생성 중…"
          : "관련 문서를 찾지 못했습니다."
      );
    } else if (event === "token") {
      onToken(data);
    } else if (event === "verifying") {
      setStatus("근거 확인 중…");
    } else if (event === "final") {
      onFinal(data);
    } else if (event === "refused") {
      onRefused(data);
    } else if (event === "quota" || (event === "error" && data.kind === "quota")) {
      // "기다리세요"와 "고장났습니다"가 같게 읽히면 안 된다. 무료 티어에서는
      // 이것이 개발 세션의 평범한 끝이다.
      var wait = data.retry_after_seconds
        ? " 약 " + Math.ceil(data.retry_after_seconds) + "초 후 다시 시도할 수 있습니다."
        : "";
      setStatus("LLM 무료 티어 할당량을 모두 사용했습니다." + wait);
    } else if (event === "error" && data.kind === "configuration") {
      setStatus("LLM이 설정되지 않았습니다: " + (data.message || ""));
    } else if (event === "error") {
      setStatus("오류가 발생했습니다: " + (data.message || data.kind));
    }
  }

  function parseFrames(buffer) {
    const frames = buffer.split("\n\n");
    const remainder = frames.pop();
    frames.forEach(function (frame) {
      let event = "message";
      const dataLines = [];
      frame.split("\n").forEach(function (line) {
        if (line.startsWith("event:")) event = line.slice(6).trim();
        else if (line.startsWith("data:")) dataLines.push(line.slice(5).trim());
      });
      if (!dataLines.length) return;
      try {
        dispatch(event, JSON.parse(dataLines.join("\n")));
      } catch (err) {
        /* a malformed frame must not kill the stream */
      }
    });
    return remainder;
  }

  form.addEventListener("submit", function (submitEvent) {
    submitEvent.preventDefault();
    const question = (input.value || "").trim();
    if (!question) return;

    reset();
    sentenceNodes.clear();
    setStatus("검색 중…");
    terminal = false;

    fetch("/api/query", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question: question })
    })
      .then(function (response) {
        if (!response.ok || !response.body) throw new Error("HTTP " + response.status);
        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = "";

        function pump() {
          return reader.read().then(function (chunk) {
            if (chunk.done) {
              // The stream ending is not success. Exactly one of final/refused
              // is always sent; without it, something went wrong.
              if (!terminal) setStatus("응답이 완료되지 않았습니다. 다시 시도해 주십시오.");
              return;
            }
            buffer += decoder.decode(chunk.value, { stream: true });
            buffer = parseFrames(buffer);
            return pump();
          });
        }
        return pump();
      })
      .catch(function (err) {
        setStatus("요청에 실패했습니다: " + err.message);
      });
  });
})();
