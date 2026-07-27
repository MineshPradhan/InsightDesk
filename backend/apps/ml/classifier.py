"""Ticket triage: which queue, how urgent.

Two backends behind one interface:
  * `centroid`  — kNN over the embedding of every historically-labelled ticket.
                  Zero training, improves as agents correct labels, ~5 ms.
  * `zeroshot`  — NLI entailment for cold start, when there is no labelled
                  history at all.
"""
from __future__ import annotations

import functools
import re
import time
from dataclasses import asdict, dataclass

import numpy as np
from django.conf import settings

from apps.ml.embeddings import embed
from apps.tickets.models import Priority, Queue

MODEL_VERSION = "triage-centroid-v1.2"

URGENCY_CUES = {
    "critical": [r"\bdown\b", r"\boutage\b", r"\bcannot (log|access)", r"\burgent(ly)?\b",
                 r"\bimmediate", r"\bdata loss", r"\bbreach", r"\bproduction\b", r"\bescalat"],
    "high": [r"\basap\b", r"\bblocked\b", r"\bstill (not|no)", r"\bthird time\b",
             r"\brefund\b", r"\bcharged twice", r"\bdeadline\b", r"\bfrustrat"],
    "low": [r"\bwhen you (get|have)", r"\bno rush\b", r"\bjust wondering\b", r"\bfeature request\b"],
}
NEGATIVE = [r"\bunacceptable\b", r"\bterrible\b", r"\bangry\b", r"\bworst\b", r"\bdisappoint",
            r"\bcancel my\b", r"\blawyer\b", r"\bnever again\b"]
POSITIVE = [r"\bthanks?\b", r"\bappreciate\b", r"\bgreat\b", r"\bhelpful\b", r"\bexcellent\b"]


@dataclass(slots=True)
class Triage:
    queue: str
    priority: str
    queue_confidence: float
    priority_confidence: float
    sentiment: float
    model_version: str
    latency_ms: int
    rationale: str

    def dict(self) -> dict:
        return asdict(self)


@functools.lru_cache(maxsize=1)
def _queue_centroids() -> tuple[list[str], np.ndarray] | None:
    """Mean embedding per queue, computed from labelled tickets."""
    from apps.tickets.models import TicketEmbedding

    rows = (
        TicketEmbedding.objects.exclude(ticket__queue="")
        .values_list("ticket__queue", "vector")
    )
    buckets: dict[str, list] = {}
    for q, v in rows:
        buckets.setdefault(q, []).append(np.asarray(v, dtype=np.float32))
    if len(buckets) < 2:
        return None
    labels = sorted(buckets)
    mat = np.stack([np.mean(buckets[label], axis=0) for label in labels])
    mat /= np.linalg.norm(mat, axis=1, keepdims=True) + 1e-9
    return labels, mat


def reset_centroids() -> None:
    _queue_centroids.cache_clear()


def _softmax(x: np.ndarray, temp: float = 0.07) -> np.ndarray:
    z = np.exp((x - x.max()) / temp)
    return z / z.sum()


def _sentiment(text: str) -> float:
    low = text.lower()
    neg = sum(bool(re.search(p, low)) for p in NEGATIVE)
    pos = sum(bool(re.search(p, low)) for p in POSITIVE)
    return float(np.tanh(0.6 * (pos - neg)))


def _priority(text: str, sentiment: float) -> tuple[str, float, str]:
    low = text.lower()
    hits = {lvl: [p for p in pats if re.search(p, low)] for lvl, pats in URGENCY_CUES.items()}
    if hits["critical"]:
        return Priority.CRITICAL, 0.88, f"urgency cue: {hits['critical'][0]}"
    if hits["high"] or sentiment < -0.5:
        why = hits["high"][0] if hits["high"] else "negative sentiment"
        return Priority.HIGH, 0.76, f"urgency cue: {why}"
    if hits["low"]:
        return Priority.LOW, 0.71, f"low-urgency cue: {hits['low'][0]}"
    return Priority.MEDIUM, 0.62, "no strong urgency signal"


def _zero_shot_queue(text: str) -> tuple[str, float]:
    from transformers import pipeline

    clf = pipeline("zero-shot-classification", model=settings.ZERO_SHOT_MODEL)
    labels = [q.label for q in Queue]
    res = clf(text[:1000], candidate_labels=labels)
    label_to_value = {q.label: q.value for q in Queue}
    return label_to_value[res["labels"][0]], float(res["scores"][0])


def triage(text: str, vector: list[float] | None = None) -> Triage:
    started = time.perf_counter()
    vec = np.asarray(vector if vector is not None else embed(text), dtype=np.float32)

    centroids = _queue_centroids()
    if centroids:
        labels, mat = centroids
        sims = mat @ vec
        probs = _softmax(sims)
        idx = int(np.argmax(probs))
        queue, q_conf = labels[idx], float(probs[idx])
        rationale = f"nearest queue centroid (cos={float(sims[idx]):.3f})"
    else:
        queue, q_conf = _zero_shot_queue(text)
        rationale = "zero-shot NLI (no labelled history yet)"

    sentiment = _sentiment(text)
    priority, p_conf, why = _priority(text, sentiment)

    return Triage(
        queue=queue,
        priority=priority,
        queue_confidence=round(q_conf, 4),
        priority_confidence=round(p_conf, 4),
        sentiment=round(sentiment, 3),
        model_version=MODEL_VERSION,
        latency_ms=int((time.perf_counter() - started) * 1000),
        rationale=f"{rationale}; {why}",
    )
