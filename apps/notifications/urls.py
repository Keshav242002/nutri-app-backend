from django.urls import path

from .views import (
    DeviceDeleteView,
    DeviceView,
    MarkAllReadView,
    MarkReadView,
    NotificationListView,
    UnreadCountView,
)

urlpatterns = [
    path("", NotificationListView.as_view(), name="notification-list"),
    path("unread-count/", UnreadCountView.as_view(), name="notification-unread-count"),
    path("mark-all-read/", MarkAllReadView.as_view(), name="notification-mark-all-read"),
    path("<int:notification_id>/read/", MarkReadView.as_view(), name="notification-read"),
    path("devices/", DeviceView.as_view(), name="notification-device"),
    path("devices/<str:fcm_token>/", DeviceDeleteView.as_view(), name="notification-device-delete"),
]
