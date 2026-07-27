from django.urls import include, path
from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register("tickets", views.TicketViewSet, basename="ticket")
router.register("kb", views.KBArticleViewSet, basename="kb")
router.register("drafts", views.ReplyDraftViewSet, basename="draft")

urlpatterns = [
    path("", include(router.urls)),
    path("search/", views.search, name="search"),
    path("healthz/", views.healthz, name="healthz"),
]
