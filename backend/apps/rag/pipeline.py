"""Retrieval-augmented reply drafting.

    embed → vector recall (k=25) → cross-encoder rerank (k=5)
          → grounding gate → LLM → citation validation

The grounding gate and the citation validation are the two pieces that keep
this from hallucinating policy at customers.
"""
from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field

from django.conf import settings
from tenacity import retry, stop_after_attempt, wait_exponential

from apps.ml.embeddings import embed, rerank
from apps.ml.vectorstore import Match, search_kb
from apps.rag import prompts

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class RagAnswer:
    text: str
    citations: list[dict] = field(default_factory=list)
    scores: list[float] = field(default_factory=list)
    grounded: bool = True
    model: str = ""
    prompt_tokens: int = 0
    completion_tokens: int = 0
    latency_ms: int = 0


def retrieve(query: str, category: str | None = None) -> list[Match]:
    vec = embed(query)
    candidates = search_kb(vec, limit=settings.RAG_CANDIDATE_K, category=category)
    if not candidates:
        return []
    ce_scores = rerank(query, [c.text for c in candidates])
    ranked = sorted(zip(candidates, ce_scores, strict=True), key=lambda p: -p[1])
    top = []
    for match, score in ranked[: settings.RAG_TOP_K]:
        match.meta["rerank_score"] = float(score)
        top.append(match)
    return top


def _build_context(matches: list[Match]) -> str:
    return "\n\n".join(
        f"[{i}] ({m.meta['title']} · {m.meta['category']})\n{m.text}"
        for i, m in enumerate(matches, start=1)
    )


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, max=8))
def _call_llm(system: str, user: str) -> tuple[str, int, int]:
    if settings.LLM_PROVIDER == "echo":  # used in CI, no network, no key
        return json.dumps({"reply": "[echo] " + user[:200], "used_passages": [1],
                           "answerable": True, "missing": None}), 0, 0

    from openai import OpenAI

    client = OpenAI(api_key=settings.OPENAI_API_KEY)
    resp = client.chat.completions.create(
        model=settings.LLM_MODEL,
        messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
        temperature=0.2,
        response_format={"type": "json_object"},
    )
    usage = resp.usage
    return resp.choices[0].message.content, usage.prompt_tokens, usage.completion_tokens


def _validate_citations(reply: str, n_passages: int) -> bool:
    """A draft that cites [7] when only 5 passages were supplied is a
    hallucination signal — flag it rather than shipping it."""
    import re

    cited = {int(m) for m in re.findall(r"\[(\d+)\]", reply)}
    return bool(cited) and all(1 <= c <= n_passages for c in cited)


def draft_reply(ticket) -> RagAnswer:
    started = time.perf_counter()
    matches = retrieve(ticket.text)
    best = matches[0].meta.get("rerank_score", 0) if matches else -99
    top_sim = matches[0].score if matches else 0.0

    if not matches or top_sim < settings.RAG_MIN_SIMILARITY:
        return RagAnswer(
            text=prompts.NO_CONTEXT.format(score=top_sim, threshold=settings.RAG_MIN_SIMILARITY),
            grounded=False,
            model=settings.LLM_MODEL,
            latency_ms=int((time.perf_counter() - started) * 1000),
        )

    user = prompts.USER.format(
        subject=ticket.subject,
        queue=ticket.queue or "unassigned",
        priority=ticket.priority or "unset",
        language=ticket.language,
        body=ticket.body[:4000],
        context=_build_context(matches),
    )
    raw, p_tok, c_tok = _call_llm(prompts.SYSTEM, user)

    try:
        parsed = json.loads(raw)
        reply = parsed.get("reply", "").strip()
        answerable = parsed.get("answerable", True)
    except json.JSONDecodeError:
        logger.warning("llm returned non-json, falling back to raw text")
        reply, answerable = raw.strip(), True

    grounded = answerable and _validate_citations(reply, len(matches))
    logger.info("rag draft ticket=%s grounded=%s best_ce=%.3f", ticket.id, grounded, best)

    return RagAnswer(
        text=reply,
        citations=[
            {
                "n": i,
                "chunk_id": m.id,
                "article_id": m.meta["article_id"],
                "title": m.meta["title"],
                "similarity": round(m.score, 4),
                "rerank_score": round(m.meta.get("rerank_score", 0), 4),
            }
            for i, m in enumerate(matches, start=1)
        ],
        scores=[round(m.score, 4) for m in matches],
        grounded=grounded,
        model=settings.LLM_MODEL,
        prompt_tokens=p_tok,
        completion_tokens=c_tok,
        latency_ms=int((time.perf_counter() - started) * 1000),
    )
