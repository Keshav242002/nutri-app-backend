from django.contrib import admin
from django.db import OperationalError, connection
from django.http import HttpRequest, JsonResponse
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularRedocView, SpectacularSwaggerView


def healthz(request: HttpRequest) -> JsonResponse:
    """Liveness + DB readiness probe."""
    try:
        connection.ensure_connection()
        db_status = "ok"
    except OperationalError:
        db_status = "error"

    status_code = 200 if db_status == "ok" else 500
    payload = {"status": "ok" if db_status == "ok" else "error", "db": db_status}
    return JsonResponse(payload, status=status_code)


urlpatterns = [
    path("admin/", admin.site.urls),
    path("healthz", healthz, name="healthz"),
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),
    path("api/redoc/", SpectacularRedocView.as_view(url_name="schema"), name="redoc"),
    path("api/v1/", include("nutriplan.api_router")),
]
