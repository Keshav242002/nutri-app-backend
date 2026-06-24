from typing import Any

from rest_framework import serializers

from .models import PLATFORM_CHOICES, DeviceToken, Notification


class NotificationSerializer(serializers.ModelSerializer[Notification]):
    class Meta:
        model = Notification
        fields = ["id", "category", "title", "body", "data", "read_at", "created_at"]
        read_only_fields = fields


class DeviceTokenSerializer(serializers.ModelSerializer[DeviceToken]):
    class Meta:
        model = DeviceToken
        fields = ["id", "fcm_token", "platform", "last_seen_at", "created_at"]
        read_only_fields = ["id", "last_seen_at", "created_at"]


class RegisterDeviceSerializer(serializers.Serializer[Any]):
    fcm_token = serializers.CharField(max_length=255, min_length=1)
    platform = serializers.ChoiceField(choices=[c[0] for c in PLATFORM_CHOICES])
