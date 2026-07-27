"""Celery application. Workers handle embedding, triage and RAG generation
off the request path so the API stays fast."""
import os

from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

app = Celery("insightdesk")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()

app.conf.beat_schedule = {
    "refresh-analytics-rollups": {
        "task": "apps.analytics.tasks.refresh_rollups",
        "schedule": 300.0,
    }
}
