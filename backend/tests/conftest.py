import uuid

import pytest
from django.utils import timezone

from apps.tickets.models import KBArticle, KBChunk, Ticket


@pytest.fixture
def ticket(db):
    return Ticket.objects.create(
        external_id=f"T-{uuid.uuid4().hex[:8]}",
        subject="Cannot log in after password reset",
        body="I reset my password twice and the login page keeps rejecting it. Urgent.",
        received_at=timezone.now(),
    )


@pytest.fixture
def kb_article(db):
    article = KBArticle.objects.create(
        slug="account-recover-password",
        title="Recover Password",
        body="If a reset link fails, request a new one from the sign-in page. "
             "Links expire after 30 minutes. Clear cached credentials first.",
        category="account",
        intent="recover_password",
    )
    KBChunk.objects.create(
        article=article, chunk_index=0, text=article.body, vector=[0.01] * 384
    )
    return article
