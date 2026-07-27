import django_filters as df

from .models import Ticket


class TicketFilter(df.FilterSet):
    received_after = df.IsoDateTimeFilter(field_name="received_at", lookup_expr="gte")
    received_before = df.IsoDateTimeFilter(field_name="received_at", lookup_expr="lte")
    queue = df.BaseInFilter(field_name="queue")
    priority = df.BaseInFilter(field_name="priority")
    status = df.BaseInFilter(field_name="status")
    untriaged = df.BooleanFilter(method="filter_untriaged")

    class Meta:
        model = Ticket
        fields = ("queue", "priority", "status", "language", "channel")

    def filter_untriaged(self, qs, name, value):
        return qs.filter(triage_results__isnull=True) if value else qs
