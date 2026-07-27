"""The analytics the support lead actually asks for in the weekly review.

All aggregation happens in Postgres — pulling rows into Python to count them
is the classic way these endpoints fall over at 100k tickets.
"""
from __future__ import annotations

from datetime import timedelta

from django.db.models import Avg, Count, F, FloatField, Q, Value
from django.db.models.functions import Cast, Coalesce, TruncDay
from django.utils import timezone

from apps.tickets.models import ReplyDraft, Ticket, TriageResult


def _window(days: int):
    return timezone.now() - timedelta(days=days)


def overview(days: int = 30) -> dict:
    since = _window(days)
    qs = Ticket.objects.filter(received_at__gte=since)
    total = qs.count()
    resolved = qs.filter(resolved_at__isnull=False)

    ttr = [t.resolution_minutes for t in resolved.only("received_at", "resolved_at")]
    ttr.sort()

    def pct(p: float) -> float:
        return round(ttr[int(len(ttr) * p)], 1) if ttr else 0.0

    triage_qs = TriageResult.objects.filter(created_at__gte=since).select_related("ticket")
    scored = [r for r in triage_qs if r.queue_is_correct is not None]
    accuracy = sum(r.queue_is_correct for r in scored) / len(scored) if scored else 0.0

    drafts = ReplyDraft.objects.filter(created_at__gte=since)
    return {
        "window_days": days,
        "tickets": total,
        "open": qs.exclude(status="resolved").count(),
        "backlog_critical": qs.filter(priority="critical").exclude(status="resolved").count(),
        "median_resolution_minutes": pct(0.5),
        "p90_resolution_minutes": pct(0.9),
        "avg_csat": round(qs.aggregate(v=Avg("csat"))["v"] or 0, 2),
        "triage_accuracy": round(accuracy, 4),
        "triage_p50_latency_ms": round(triage_qs.aggregate(v=Avg("latency_ms"))["v"] or 0),
        "drafts_generated": drafts.count(),
        "drafts_grounded_pct": round(
            100 * (drafts.filter(grounded=True).count() / drafts.count()) if drafts.count() else 0, 1
        ),
        "drafts_sent_pct": round(
            100 * (drafts.filter(was_sent=True).count() / drafts.count()) if drafts.count() else 0, 1
        ),
    }


def volume_timeseries(days: int = 30) -> list[dict]:
    rows = (
        Ticket.objects.filter(received_at__gte=_window(days))
        .annotate(day=TruncDay("received_at"))
        .values("day")
        .annotate(
            total=Count("id"),
            critical=Count("id", filter=Q(priority="critical")),
            resolved=Count("id", filter=Q(resolved_at__isnull=False)),
        )
        .order_by("day")
    )
    return [
        {
            "day": r["day"].date().isoformat(),
            "total": r["total"],
            "critical": r["critical"],
            "resolved": r["resolved"],
        }
        for r in rows
    ]


def queue_distribution(days: int = 30) -> list[dict]:
    rows = (
        Ticket.objects.filter(received_at__gte=_window(days))
        .exclude(queue="")
        .values("queue")
        .annotate(
            count=Count("id"),
            avg_csat=Coalesce(Avg("csat"), Value(0.0), output_field=FloatField()),
            critical=Count("id", filter=Q(priority="critical")),
        )
        .order_by("-count")
    )
    return list(rows)


def priority_mix(days: int = 30) -> list[dict]:
    rows = (
        Ticket.objects.filter(received_at__gte=_window(days))
        .exclude(priority="")
        .values("priority")
        .annotate(count=Count("id"))
        .order_by("-count")
    )
    return list(rows)


def triage_confusion(days: int = 30) -> list[dict]:
    """Actual vs predicted queue — where the routing model leaks."""
    rows = (
        TriageResult.objects.filter(created_at__gte=_window(days))
        .exclude(ticket__queue="")
        .values(actual=F("ticket__queue"), predicted=F("predicted_queue"))
        .annotate(count=Count("id"))
        .order_by("-count")
    )
    return list(rows)


def deflection(days: int = 30) -> dict:
    """Minutes saved: drafts an agent sent as-is, valued at the median
    handle time for that queue."""
    since = _window(days)
    sent = ReplyDraft.objects.filter(created_at__gte=since, was_sent=True).count()
    median = overview(days)["median_resolution_minutes"] or 0
    return {
        "drafts_sent_as_is": sent,
        "median_handle_minutes": median,
        "estimated_minutes_saved": round(sent * median * 0.6, 1),
    }
