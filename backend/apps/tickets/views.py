from __future__ import annotations

from django.db.models import Prefetch
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import status, viewsets
from rest_framework.decorators import action, api_view
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle

from apps.ml.classifier import triage as run_triage
from apps.ml.embeddings import embed
from apps.ml.vectorstore import hybrid_search, similar_tickets
from apps.rag.pipeline import retrieve

from .filters import TicketFilter
from .models import KBArticle, ReplyDraft, Ticket, TriageResult
from .serializers import (
    KBArticleSerializer,
    ReplyDraftSerializer,
    SearchResultSerializer,
    TicketCreateSerializer,
    TicketDetailSerializer,
    TicketListSerializer,
)
from .tasks import generate_draft, process_new_ticket


class TicketViewSet(viewsets.ModelViewSet):
    queryset = Ticket.objects.prefetch_related(
        Prefetch("triage_results", queryset=TriageResult.objects.order_by("-created_at")),
        Prefetch("drafts", queryset=ReplyDraft.objects.order_by("-created_at")),
    )
    filterset_class = TicketFilter
    search_fields = ("subject", "body", "external_id")
    ordering_fields = ("received_at", "priority", "csat")

    def get_serializer_class(self):
        if self.action == "create":
            return TicketCreateSerializer
        if self.action in {"retrieve", "partial_update", "update"}:
            return TicketDetailSerializer
        return TicketListSerializer

    def perform_create(self, serializer):
        ticket = serializer.save()
        process_new_ticket.delay(str(ticket.id))

    @extend_schema(summary="Run triage synchronously (used by the console's Re-run button)")
    @action(detail=True, methods=["post"])
    def triage(self, request, pk=None):
        ticket = self.get_object()
        result = run_triage(ticket.text)
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
        return Response(result.dict())

    @extend_schema(summary="Accept or reject the model's triage — this is the training signal")
    @action(detail=True, methods=["post"], url_path="triage/feedback")
    def triage_feedback(self, request, pk=None):
        ticket = self.get_object()
        latest = ticket.triage_results.first()
        if not latest:
            return Response({"detail": "No triage to rate."}, status=status.HTTP_404_NOT_FOUND)
        latest.accepted_by_agent = bool(request.data.get("accepted"))
        latest.save(update_fields=["accepted_by_agent"])
        if not latest.accepted_by_agent:
            ticket.queue = request.data.get("queue", ticket.queue)
            ticket.priority = request.data.get("priority", ticket.priority)
            ticket.save(update_fields=["queue", "priority", "updated_at"])
        return Response({"ok": True, "accepted": latest.accepted_by_agent})

    @extend_schema(summary="Queue a grounded reply draft")
    @action(detail=True, methods=["post"], throttle_classes=[ScopedRateThrottle])
    def draft(self, request, pk=None):
        ticket = self.get_object()
        task = generate_draft.delay(str(ticket.id))
        return Response({"task_id": task.id}, status=status.HTTP_202_ACCEPTED)

    draft.throttle_scope = "rag"

    @extend_schema(summary="Tickets that look like this one, with how they were resolved")
    @action(detail=True, methods=["get"])
    def similar(self, request, pk=None):
        ticket = self.get_object()
        vector = getattr(getattr(ticket, "embedding", None), "vector", None)
        vector = list(vector) if vector is not None else embed(ticket.text)
        matches = similar_tickets(vector, limit=8, exclude_id=ticket.id)
        return Response(SearchResultSerializer([m.__dict__ for m in matches], many=True).data)


class KBArticleViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = KBArticle.objects.all()
    serializer_class = KBArticleSerializer
    search_fields = ("title", "body", "intent")
    filterset_fields = ("category", "intent")


class ReplyDraftViewSet(viewsets.ModelViewSet):
    queryset = ReplyDraft.objects.select_related("ticket")
    serializer_class = ReplyDraftSerializer
    http_method_names = ["get", "patch", "head", "options"]


@extend_schema(
    summary="Hybrid semantic + keyword search across every ticket",
    parameters=[
        OpenApiParameter("q", str, required=True),
        OpenApiParameter("limit", int),
        OpenApiParameter("scope", str, enum=["tickets", "kb"]),
    ],
)
@api_view(["GET"])
def search(request):
    query = request.query_params.get("q", "").strip()
    if not query:
        return Response({"detail": "Pass ?q= to search."}, status=status.HTTP_400_BAD_REQUEST)
    limit = int(request.query_params.get("limit", 20))
    scope = request.query_params.get("scope", "tickets")

    if scope == "kb":
        matches = retrieve(query)
    else:
        matches = hybrid_search(query, embed(query), limit=limit)
    return Response(
        {
            "query": query,
            "scope": scope,
            "count": len(matches),
            "results": SearchResultSerializer([m.__dict__ for m in matches], many=True).data,
        }
    )


@api_view(["GET"])
def healthz(request):
    from django.db import connection

    with connection.cursor() as cur:
        cur.execute("SELECT 1")
    return Response({"status": "ok"})
