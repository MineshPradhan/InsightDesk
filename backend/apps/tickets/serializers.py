from rest_framework import serializers

from .models import KBArticle, ReplyDraft, Ticket, TriageResult


class TriageResultSerializer(serializers.ModelSerializer):
    queue_is_correct = serializers.BooleanField(read_only=True)

    class Meta:
        model = TriageResult
        fields = (
            "id", "predicted_queue", "predicted_priority", "queue_confidence",
            "priority_confidence", "sentiment", "model_version", "latency_ms",
            "accepted_by_agent", "queue_is_correct", "created_at",
        )


class ReplyDraftSerializer(serializers.ModelSerializer):
    class Meta:
        model = ReplyDraft
        fields = (
            "id", "text", "citations", "grounded", "model", "latency_ms",
            "prompt_tokens", "completion_tokens", "agent_rating", "was_sent", "created_at",
        )
        read_only_fields = ("citations", "grounded", "model", "latency_ms")


class TicketListSerializer(serializers.ModelSerializer):
    latest_triage = serializers.SerializerMethodField()

    class Meta:
        model = Ticket
        fields = (
            "id", "external_id", "subject", "queue", "priority", "status",
            "language", "channel", "received_at", "csat", "latest_triage",
        )

    def get_latest_triage(self, obj):
        result = obj.triage_results.all()[:1]
        return TriageResultSerializer(result[0]).data if result else None


class TicketDetailSerializer(TicketListSerializer):
    triage_results = TriageResultSerializer(many=True, read_only=True)
    drafts = ReplyDraftSerializer(many=True, read_only=True)

    class Meta(TicketListSerializer.Meta):
        fields = TicketListSerializer.Meta.fields + (
            "body", "tags", "customer_email", "agent_response",
            "first_response_at", "resolved_at", "triage_results", "drafts",
        )


class TicketCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Ticket
        fields = ("external_id", "subject", "body", "language", "channel",
                  "customer_email", "received_at")


class KBArticleSerializer(serializers.ModelSerializer):
    chunk_count = serializers.IntegerField(source="chunks.count", read_only=True)

    class Meta:
        model = KBArticle
        fields = ("id", "slug", "title", "category", "intent", "source_url", "chunk_count")


class SearchResultSerializer(serializers.Serializer):
    id = serializers.CharField()
    score = serializers.FloatField()
    text = serializers.CharField()
    meta = serializers.DictField()
