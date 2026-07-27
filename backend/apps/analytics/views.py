from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework.decorators import api_view
from rest_framework.response import Response

from . import queries

DAYS = OpenApiParameter("days", int, description="Look-back window, default 30")


def _days(request) -> int:
    return max(1, min(int(request.query_params.get("days", 30)), 365))


@extend_schema(parameters=[DAYS])
@api_view(["GET"])
def overview(request):
    return Response(queries.overview(_days(request)))


@extend_schema(parameters=[DAYS])
@api_view(["GET"])
def volume(request):
    return Response(queries.volume_timeseries(_days(request)))


@extend_schema(parameters=[DAYS])
@api_view(["GET"])
def queues(request):
    return Response(queries.queue_distribution(_days(request)))


@extend_schema(parameters=[DAYS])
@api_view(["GET"])
def priorities(request):
    return Response(queries.priority_mix(_days(request)))


@extend_schema(parameters=[DAYS])
@api_view(["GET"])
def confusion(request):
    return Response(queries.triage_confusion(_days(request)))


@extend_schema(parameters=[DAYS])
@api_view(["GET"])
def deflection(request):
    return Response(queries.deflection(_days(request)))
