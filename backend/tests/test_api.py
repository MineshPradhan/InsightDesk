import pytest
from django.urls import reverse
from rest_framework.test import APIClient


@pytest.fixture
def client():
    return APIClient()


@pytest.mark.django_db
def test_healthz(client):
    assert client.get("/api/healthz/").status_code == 200


@pytest.mark.django_db
def test_list_tickets(client, ticket):
    res = client.get("/api/tickets/")
    assert res.status_code == 200
    assert res.data["count"] == 1
    assert res.data["results"][0]["subject"] == ticket.subject


@pytest.mark.django_db
def test_filter_by_priority(client, ticket):
    ticket.priority = "critical"
    ticket.save()
    assert client.get("/api/tickets/?priority=critical").data["count"] == 1
    assert client.get("/api/tickets/?priority=low").data["count"] == 0


@pytest.mark.django_db
def test_search_requires_query(client):
    assert client.get("/api/search/").status_code == 400


@pytest.mark.django_db
def test_triage_feedback_404_without_result(client, ticket):
    res = client.post(f"/api/tickets/{ticket.id}/triage/feedback", {"accepted": True}, follow=True)
    assert res.status_code == 404


@pytest.mark.django_db
def test_analytics_overview(client, ticket):
    res = client.get("/api/analytics/overview/?days=30")
    assert res.status_code == 200
    assert res.data["tickets"] == 1
    assert "triage_accuracy" in res.data
