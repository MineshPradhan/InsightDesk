from django.contrib import admin

from .models import KBArticle, KBChunk, ReplyDraft, Ticket, TriageResult


@admin.register(Ticket)
class TicketAdmin(admin.ModelAdmin):
    list_display = ("external_id", "subject", "queue", "priority", "status", "received_at")
    list_filter = ("queue", "priority", "status", "language")
    search_fields = ("external_id", "subject", "body")
    date_hierarchy = "received_at"


@admin.register(TriageResult)
class TriageResultAdmin(admin.ModelAdmin):
    list_display = ("ticket", "predicted_queue", "predicted_priority", "queue_confidence", "model_version")
    list_filter = ("model_version", "predicted_queue")


@admin.register(KBArticle)
class KBArticleAdmin(admin.ModelAdmin):
    list_display = ("title", "category", "intent")
    search_fields = ("title", "body")


admin.site.register([KBChunk, ReplyDraft])
