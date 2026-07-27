"""Domain model.

Ticket ─1:N─ TriageResult      (every model run is kept: audit + accuracy)
Ticket ─1:N─ ReplyDraft        (RAG output + citations + agent feedback)
Ticket ─1:1─ TicketEmbedding   (vector for "similar tickets" search)
KBArticle ─1:N─ KBChunk        (chunked + embedded knowledge base for RAG)
"""
from __future__ import annotations

import uuid

from django.contrib.postgres.fields import ArrayField
from django.db import models
from pgvector.django import HnswIndex, VectorField

EMBEDDING_DIM = 384


class Queue(models.TextChoices):
    TECHNICAL = "technical_support", "Technical Support"
    CUSTOMER_SERVICE = "customer_service", "Customer Service"
    BILLING = "billing_and_payments", "Billing and Payments"
    PRODUCT = "product_support", "Product Support"
    IT = "it_support", "IT Support"
    RETURNS = "returns_and_exchanges", "Returns and Exchanges"
    SALES = "sales_and_presales", "Sales and Pre-Sales"
    HR = "human_resources", "Human Resources"


class Priority(models.TextChoices):
    LOW = "low", "Low"
    MEDIUM = "medium", "Medium"
    HIGH = "high", "High"
    CRITICAL = "critical", "Critical"


class Status(models.TextChoices):
    NEW = "new", "New"
    TRIAGED = "triaged", "Triaged"
    IN_PROGRESS = "in_progress", "In progress"
    WAITING = "waiting_on_customer", "Waiting on customer"
    RESOLVED = "resolved", "Resolved"


class TimeStamped(models.Model):
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class Ticket(TimeStamped):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    external_id = models.CharField(max_length=64, unique=True)
    subject = models.CharField(max_length=512)
    body = models.TextField()
    language = models.CharField(max_length=8, default="en", db_index=True)
    channel = models.CharField(max_length=32, default="email")
    customer_email = models.EmailField(blank=True)

    # Ground truth (from the dataset / from the agent who worked it)
    queue = models.CharField(max_length=48, choices=Queue.choices, blank=True, db_index=True)
    priority = models.CharField(max_length=16, choices=Priority.choices, blank=True, db_index=True)
    tags = ArrayField(models.CharField(max_length=48), default=list, blank=True)

    status = models.CharField(max_length=24, choices=Status.choices, default=Status.NEW, db_index=True)
    agent_response = models.TextField(blank=True)

    received_at = models.DateTimeField(db_index=True)
    first_response_at = models.DateTimeField(null=True, blank=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    csat = models.SmallIntegerField(null=True, blank=True)

    class Meta:
        ordering = ("-received_at",)
        indexes = [
            models.Index(fields=["status", "priority"]),
            models.Index(fields=["queue", "received_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.external_id} · {self.subject[:60]}"

    @property
    def text(self) -> str:
        return f"{self.subject}\n\n{self.body}"

    @property
    def resolution_minutes(self) -> float | None:
        if not self.resolved_at:
            return None
        return (self.resolved_at - self.received_at).total_seconds() / 60


class TicketEmbedding(TimeStamped):
    ticket = models.OneToOneField(Ticket, on_delete=models.CASCADE, related_name="embedding")
    vector = VectorField(dimensions=EMBEDDING_DIM)
    model_name = models.CharField(max_length=128)

    class Meta:
        indexes = [
            HnswIndex(
                name="ticket_vec_hnsw",
                fields=["vector"],
                m=16,
                ef_construction=64,
                opclasses=["vector_cosine_ops"],
            )
        ]


class TriageResult(TimeStamped):
    """One inference run. Never overwritten — this is how triage accuracy
    is measured over time and how a bad model version gets caught."""

    ticket = models.ForeignKey(Ticket, on_delete=models.CASCADE, related_name="triage_results")
    predicted_queue = models.CharField(max_length=48, choices=Queue.choices)
    predicted_priority = models.CharField(max_length=16, choices=Priority.choices)
    queue_confidence = models.FloatField()
    priority_confidence = models.FloatField()
    sentiment = models.FloatField(default=0.0, help_text="-1 angry .. +1 happy")
    model_version = models.CharField(max_length=64)
    latency_ms = models.IntegerField()
    accepted_by_agent = models.BooleanField(null=True)

    class Meta:
        ordering = ("-created_at",)
        indexes = [models.Index(fields=["model_version", "created_at"])]

    @property
    def queue_is_correct(self) -> bool | None:
        if not self.ticket.queue:
            return None
        return self.ticket.queue == self.predicted_queue


class KBArticle(TimeStamped):
    slug = models.SlugField(max_length=160, unique=True)
    title = models.CharField(max_length=256)
    body = models.TextField()
    category = models.CharField(max_length=64, db_index=True)
    intent = models.CharField(max_length=64, blank=True, db_index=True)
    source_url = models.URLField(blank=True)

    def __str__(self) -> str:
        return self.title


class KBChunk(TimeStamped):
    article = models.ForeignKey(KBArticle, on_delete=models.CASCADE, related_name="chunks")
    chunk_index = models.IntegerField()
    text = models.TextField()
    vector = VectorField(dimensions=EMBEDDING_DIM)

    class Meta:
        unique_together = ("article", "chunk_index")
        indexes = [
            HnswIndex(
                name="kbchunk_vec_hnsw",
                fields=["vector"],
                m=16,
                ef_construction=64,
                opclasses=["vector_cosine_ops"],
            )
        ]


class ReplyDraft(TimeStamped):
    """A grounded answer. `citations` stores the chunk ids + scores actually
    used, so any sentence in the draft can be traced back to a KB article."""

    ticket = models.ForeignKey(Ticket, on_delete=models.CASCADE, related_name="drafts")
    text = models.TextField()
    citations = models.JSONField(default=list)
    retrieval_scores = models.JSONField(default=list)
    model = models.CharField(max_length=64)
    prompt_tokens = models.IntegerField(default=0)
    completion_tokens = models.IntegerField(default=0)
    latency_ms = models.IntegerField(default=0)
    grounded = models.BooleanField(default=True)
    agent_rating = models.SmallIntegerField(null=True, blank=True)
    was_sent = models.BooleanField(default=False)

    class Meta:
        ordering = ("-created_at",)
