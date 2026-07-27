from celery import shared_task
from django.core.cache import cache

from . import queries


@shared_task
def refresh_rollups() -> dict:
    """Warm the dashboard cache every 5 minutes so the Insights page opens instantly."""
    payload = {
        "overview": queries.overview(30),
        "volume": queries.volume_timeseries(30),
        "queues": queries.queue_distribution(30),
    }
    cache.set("analytics:rollup:30d", payload, timeout=900)
    return {"keys": list(payload)}
