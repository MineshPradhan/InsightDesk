from django.urls import path

from . import views

urlpatterns = [
    path("overview/", views.overview),
    path("volume/", views.volume),
    path("queues/", views.queues),
    path("priorities/", views.priorities),
    path("confusion/", views.confusion),
    path("deflection/", views.deflection),
]
