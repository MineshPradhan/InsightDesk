"""Thin query layer over pgvector.

Postgres holds both the relational data and the vectors, so a semantic search
can be filtered by queue/date/language in the same query — no separate vector
DB to keep in sync.
"""
from __future__ import annotations

from dataclasses import dataclass

from django.db.models import F, QuerySet
from pgvector.django import CosineDistance

from apps.tickets.models import KBChunk, Ticket, TicketEmbedding


@dataclass(slots=True)
class Match:
    id: str
    score: float
    text: str
    meta: dict


def search_kb(vector: list[float], limit: int = 25, category: str | None = None) -> list[Match]:
    qs: QuerySet = KBChunk.objects.select_related("article")
    if category:
        qs = qs.filter(article__category=category)
    rows = (
        qs.annotate(distance=CosineDistance("vector", vector))
        .order_by("distance")[:limit]
    )
    return [
        Match(
            id=str(r.id),
            score=1 - float(r.distance),
            text=r.text,
            meta={
                "article_id": r.article_id,
                "title": r.article.title,
                "category": r.article.category,
                "intent": r.article.intent,
                "chunk_index": r.chunk_index,
            },
        )
        for r in rows
    ]


def similar_tickets(vector: list[float], limit: int = 8, exclude_id=None, **filters) -> list[Match]:
    qs = TicketEmbedding.objects.select_related("ticket")
    if exclude_id:
        qs = qs.exclude(ticket_id=exclude_id)
    if filters:
        qs = qs.filter(**{f"ticket__{k}": v for k, v in filters.items()})
    rows = qs.annotate(distance=CosineDistance("vector", vector)).order_by("distance")[:limit]
    return [
        Match(
            id=str(r.ticket_id),
            score=1 - float(r.distance),
            text=r.ticket.subject,
            meta={
                "queue": r.ticket.queue,
                "priority": r.ticket.priority,
                "status": r.ticket.status,
                "resolution_minutes": r.ticket.resolution_minutes,
            },
        )
        for r in rows
    ]


def hybrid_search(query: str, vector: list[float], limit: int = 20) -> list[Match]:
    """Lexical (Postgres FTS) + semantic, fused with Reciprocal Rank Fusion.
    Catches the cases pure vector search misses: order numbers, SKUs, error codes."""
    from django.contrib.postgres.search import SearchQuery, SearchRank, SearchVector

    sv = SearchVector("subject", weight="A") + SearchVector("body", weight="B")
    lexical = list(
        Ticket.objects.annotate(rank=SearchRank(sv, SearchQuery(query)))
        .filter(rank__gt=0.01)
        .order_by("-rank")
        .values_list("id", flat=True)[: limit * 2]
    )
    semantic = [m.id for m in similar_tickets(vector, limit=limit * 2)]

    k = 60
    scores: dict[str, float] = {}
    for rank, tid in enumerate(lexical):
        scores[str(tid)] = scores.get(str(tid), 0) + 1 / (k + rank + 1)
    for rank, tid in enumerate(semantic):
        scores[str(tid)] = scores.get(str(tid), 0) + 1 / (k + rank + 1)

    top = sorted(scores.items(), key=lambda kv: -kv[1])[:limit]
    tickets = Ticket.objects.in_bulk([t[0] for t in top])
    out = []
    for tid, score in top:
        t = tickets.get(tid)
        if t:
            out.append(
                Match(
                    id=str(tid),
                    score=score,
                    text=t.subject,
                    meta={"queue": t.queue, "priority": t.priority, "status": t.status},
                )
            )
    return out
