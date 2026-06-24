from __future__ import annotations

from drf_spectacular.utils import extend_schema
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.models import User
from apps.notifications.serializers import (
    DeviceTokenSerializer,
    NotificationSerializer,
    RegisterDeviceSerializer,
)
from apps.notifications.services import device_service, notification_service
from core.pagination import StandardCursorPagination
from core.responses import success_response
from core.schema import envelope_list_response, envelope_response, error_response


class NotificationListView(APIView):
    @extend_schema(
        summary="List notifications",
        description=(
            "Cursor-paginated list of the user's notifications, newest first. "
            "Pass `?unread=true` to return only unread notifications."
        ),
        responses={
            200: envelope_list_response(NotificationSerializer, "Notifications."),
            401: error_response("NOT_AUTHENTICATED", "No valid token."),
        },
    )
    def get(self, request: Request) -> Response:
        assert isinstance(request.user, User)
        unread_only = request.query_params.get("unread") == "true"
        qs = notification_service.list_notifications(request.user, unread_only=unread_only)
        paginator = StandardCursorPagination()
        page = paginator.paginate_queryset(qs, request)
        serializer = NotificationSerializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)


class UnreadCountView(APIView):
    @extend_schema(
        summary="Unread notification count",
        description="Returns the number of unread notifications for the badge.",
        responses={
            200: {"type": "object", "description": "{'unread_count': <int>}"},
            401: error_response("NOT_AUTHENTICATED", "No valid token."),
        },
    )
    def get(self, request: Request) -> Response:
        assert isinstance(request.user, User)
        count = notification_service.unread_count(request.user)
        return success_response({"unread_count": count}, "Unread count retrieved.")


class MarkReadView(APIView):
    @extend_schema(
        summary="Mark a notification read",
        responses={
            200: envelope_response(NotificationSerializer, "Notification marked read."),
            401: error_response("NOT_AUTHENTICATED", "No valid token."),
            404: error_response("NOT_FOUND", "Notification not found."),
        },
    )
    def post(self, request: Request, notification_id: int) -> Response:
        assert isinstance(request.user, User)
        notification = notification_service.mark_read(request.user, notification_id)
        return success_response(
            NotificationSerializer(notification).data, "Notification marked read."
        )


class MarkAllReadView(APIView):
    @extend_schema(
        summary="Mark all notifications read",
        responses={
            200: {"type": "object", "description": "{'updated': <int>}"},
            401: error_response("NOT_AUTHENTICATED", "No valid token."),
        },
    )
    def post(self, request: Request) -> Response:
        assert isinstance(request.user, User)
        updated = notification_service.mark_all_read(request.user)
        return success_response({"updated": updated}, "All notifications marked read.")


class DeviceView(APIView):
    @extend_schema(
        summary="Register an FCM device token",
        description="Register (or re-point) an FCM token for push delivery. Idempotent by token.",
        request=RegisterDeviceSerializer,
        responses={
            201: envelope_response(DeviceTokenSerializer, "Device registered."),
            400: error_response("VALIDATION_ERROR", "Validation failed."),
            401: error_response("NOT_AUTHENTICATED", "No valid token."),
        },
    )
    def post(self, request: Request) -> Response:
        assert isinstance(request.user, User)
        serializer = RegisterDeviceSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        device = device_service.register_device(
            request.user,
            serializer.validated_data["fcm_token"],
            serializer.validated_data["platform"],
        )
        return success_response(
            DeviceTokenSerializer(device).data, "Device registered.", status_code=201
        )


class DeviceDeleteView(APIView):
    @extend_schema(
        summary="Unregister an FCM device token",
        responses={
            200: {"type": "object", "description": "{'deleted': <int>}"},
            401: error_response("NOT_AUTHENTICATED", "No valid token."),
        },
    )
    def delete(self, request: Request, fcm_token: str) -> Response:
        assert isinstance(request.user, User)
        deleted = device_service.unregister_device(request.user, fcm_token)
        return success_response({"deleted": deleted}, "Device unregistered.")
