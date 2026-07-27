"""Background work. The API never blocks on a model."""
from __future__ import annotations

import logging

from celery import shared_task

from apps.ml.classifier import triage
from apps.ml.embeddings import embed
from apps.rag.pipeline import draft_reply

from .models import ReplyDraft, Ticket, TicketEmbedding, TriageResult

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3, default_retry_delay=10)
def embed_ticket(self, ticket_id: str) -> str:
    from django.conf import settings

    ticket = Ticket.objects.get(pk=ticket_id)
    vector = embed(ticket.text, use_cache=False)
    TicketEmbedding.objects.update_or_create(
        ticket=ticket,
        defaults={"vector": vector, "model_name": settings.EMBEDDING_MODEL},
    )
    return ticket_id


@shared_task(bind=True, max_retries=3, default_retry_delay=10)
def triage_ticket(self, ticket_id: str) -> dict:
    ticket = Ticket.objects.select_related("embedding").get(pk=ticket_id)
    vector = getattr(getattr(ticket, "embedding", None), "vector", None)
    result = triage(ticket.text, vector=list(vector) if vector is not None else None)

    TriageResult.objects.create(
        ticket=ticket,
        predicted_queue=result.queue,
        predicted_priority=result.priority,
        queue_confidence=result.queue_confidence,
        priority_confidence=result.priority_confidence,
        sentiment=result.sentiment,
        model_version=result.model_version,
        latency_ms=result.latency_ms,
    )
    # Auto-apply only when the model is confident; otherwise a human decides.
    if result.queue_confidence >= 0.70 and ticket.status == Ticket._meta.get_field("status").default:
        ticket.queue = ticket.queue or result.queue
        ticket.priority = ticket.priority or result.priority
        ticket.status = "triaged"
        ticket.save(update_fields=["queue", "priority", "status", "updated_at"])
    return result.dict()


@shared_task(bind=True, max_retries=2, default_retry_delay=15)
def generate_draft(self, ticket_id: str) -> str:
    ticket = Ticket.objects.get(pk=ticket_id)
    answer = draft_reply(ticket)
    draft = ReplyDraft.objects.create(
        ticket=ticket,
        text=answer.text,
        citations=answer.citations,
        retrieval_scores=answer.scores,
        model=answer.model,
        prompt_tokens=answer.prompt_tokens,
        completion_tokens=answer.completion_tokens,
        latency_ms=answer.latency_ms,
        grounded=answer.grounded,
    )
    return str(draft.id)


@shared_task
def process_new_ticket(ticket_id: str) -> None:
    """Chained pipeline fired on ticket creation."""
    from celery import chain

    chain(embed_ticket.s(ticket_id), triage_ticket.si(ticket_id), generate_draft.si(ticket_id))()
