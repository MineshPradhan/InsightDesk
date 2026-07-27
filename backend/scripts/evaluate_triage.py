"""Offline evaluation. Run in CI on a held-out split; fail the build if
queue accuracy regresses below the baseline recorded in docs/METRICS.md.

    python scripts/evaluate_triage.py --sample 1500 --min-accuracy 0.78
"""
from __future__ import annotations

import argparse
import os
import sys
from collections import Counter
from pathlib import Path

import django

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from sklearn.metrics import classification_report  # noqa: E402

from apps.ml.classifier import triage  # noqa: E402
from apps.tickets.models import Ticket  # noqa: E402


def main(sample: int, min_accuracy: float) -> int:
    tickets = list(
        Ticket.objects.exclude(queue="").select_related("embedding").order_by("?")[:sample]
    )
    y_true, y_pred, latencies = [], [], []
    for t in tickets:
        vec = getattr(getattr(t, "embedding", None), "vector", None)
        r = triage(t.text, vector=list(vec) if vec is not None else None)
        y_true.append(t.queue)
        y_pred.append(r.queue)
        latencies.append(r.latency_ms)

    print(classification_report(y_true, y_pred, zero_division=0))
    acc = sum(a == b for a, b in zip(y_true, y_pred, strict=True)) / len(y_true)
    latencies.sort()
    print(f"accuracy      {acc:.4f}")
    print(f"p50 latency   {latencies[len(latencies)//2]} ms")
    print(f"p95 latency   {latencies[int(len(latencies)*0.95)]} ms")
    print(f"pred spread   {Counter(y_pred).most_common(5)}")

    if acc < min_accuracy:
        print(f"FAIL: accuracy {acc:.4f} < threshold {min_accuracy}")
        return 1
    return 0


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--sample", type=int, default=1500)
    p.add_argument("--min-accuracy", type=float, default=0.75)
    a = p.parse_args()
    sys.exit(main(a.sample, a.min_accuracy))
