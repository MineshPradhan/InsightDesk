"""Load the multilingual support-ticket corpus into Postgres.

Dataset: https://huggingface.co/datasets/Tobi-Bueck/customer-support-tickets
         (mirror: https://www.kaggle.com/datasets/tobiasbueck/multilingual-customer-support-tickets)
~20k email tickets in EN/DE/FR/ES/PT, each labelled with queue, priority, type,
tags and the agent's first response.

    python manage.py shell < scripts/ingest_tickets.py
    # or
    python scripts/ingest_tickets.py --limit 5000
"""
from __future__ import annotations

import argparse
import os
import random
import sys
from datetime import timedelta
from pathlib import Path

import django

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from django.utils import timezone  # noqa: E402

from apps.ml.embeddings import embed_batch  # noqa: E402
from apps.tickets.models import Priority, Queue, Ticket, TicketEmbedding  # noqa: E402

HF_DATASET = "Tobi-Bueck/customer-support-tickets"

QUEUE_MAP = {
    "Technical Support": Queue.TECHNICAL,
    "Customer Service": Queue.CUSTOMER_SERVICE,
    "Billing and Payments": Queue.BILLING,
    "Product Support": Queue.PRODUCT,
    "IT Support": Queue.IT,
    "Returns and Exchanges": Queue.RETURNS,
    "Sales and Pre-Sales": Queue.SALES,
    "Service Outages and Maintenance": Queue.TECHNICAL,
    "General Inquiry": Queue.CUSTOMER_SERVICE,
    "Human Resources": Queue.HR,
}
PRIORITY_MAP = {
    "1 (Low)": Priority.LOW, "low": Priority.LOW,
    "2 (Medium)": Priority.MEDIUM, "medium": Priority.MEDIUM,
    "3 (High)": Priority.HIGH, "high": Priority.HIGH,
    "critical": Priority.CRITICAL,
}


def load_frame(limit: int | None):
    from datasets import load_dataset

    ds = load_dataset(HF_DATASET, split="train")
    df = ds.to_pandas()
    df = df.dropna(subset=["subject", "body"])
    if limit:
        df = df.head(limit)
    return df


def synth_timestamps(i: int, total: int, priority: str):
    """The corpus has no timestamps. Spread tickets across the last 90 days
    with a weekday-heavy arrival pattern so the analytics have real shape."""
    now = timezone.now()
    received = now - timedelta(
        days=random.triangular(0, 90, 20), hours=random.uniform(0, 24)
    )
    handle = {"critical": 45, "high": 180, "medium": 640, "low": 1500}[priority]
    resolved = None
    first = received + timedelta(minutes=random.expovariate(1 / (handle * 0.15)))
    if random.random() < 0.82:
        resolved = received + timedelta(minutes=random.expovariate(1 / handle) + 5)
        if resolved > now:
            resolved = None
    return received, first, resolved


def main(limit: int | None, batch: int) -> None:
    df = load_frame(limit)
    print(f"loaded {len(df)} rows from {HF_DATASET}")

    tickets, texts = [], []
    for i, row in df.reset_index(drop=True).iterrows():
        priority = PRIORITY_MAP.get(str(row.get("priority", "")).strip(), Priority.MEDIUM)
        queue = QUEUE_MAP.get(str(row.get("queue", "")).strip(), Queue.CUSTOMER_SERVICE)
        received, first, resolved = synth_timestamps(i, len(df), priority)
        tags = [str(row[c]) for c in ("tag_1", "tag_2", "tag_3") if row.get(c) and str(row[c]) != "nan"]

        tickets.append(
            Ticket(
                external_id=f"TCK-{i:06d}",
                subject=str(row["subject"])[:512],
                body=str(row["body"]),
                language=str(row.get("language", "en")).lower()[:2],
                queue=queue,
                priority=priority,
                tags=tags,
                status="resolved" if resolved else random.choice(["new", "triaged", "in_progress"]),
                agent_response=str(row.get("answer", "") or ""),
                received_at=received,
                first_response_at=first,
                resolved_at=resolved,
                csat=random.choices([5, 4, 3, 2, 1], weights=[42, 28, 15, 9, 6])[0] if resolved else None,
            )
        )
        texts.append(f"{row['subject']}\n\n{row['body']}")

    Ticket.objects.bulk_create(tickets, batch_size=batch, ignore_conflicts=True)
    print(f"inserted {len(tickets)} tickets")

    print("embedding…")
    vectors = embed_batch(texts)
    saved = Ticket.objects.filter(external_id__in=[t.external_id for t in tickets]).in_bulk(
        field_name="external_id"
    )
    TicketEmbedding.objects.bulk_create(
        [
            TicketEmbedding(
                ticket=saved[t.external_id],
                vector=vectors[i].tolist(),
                model_name=os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2"),
            )
            for i, t in enumerate(tickets)
            if t.external_id in saved
        ],
        batch_size=batch,
        ignore_conflicts=True,
    )
    print("done. run scripts/build_kb.py next.")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--limit", type=int, default=8000)
    p.add_argument("--batch", type=int, default=500)
    a = p.parse_args()
    random.seed(42)
    main(a.limit, a.batch)
