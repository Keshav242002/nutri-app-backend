from django.contrib import admin

from .models import DeviceToken, Notification


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "category", "title", "read_at", "created_at")
    list_filter = ("category", "created_at")
    search_fields = ("user__email", "title", "body", "dedup_key")
    ordering = ("-created_at",)
    date_hierarchy = "created_at"
    raw_id_fields = ["user"]
    readonly_fields = ["dedup_key"]
    list_per_page = 50


@admin.register(DeviceToken)
class DeviceTokenAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "platform", "last_seen_at", "created_at")
    list_filter = ("platform", "created_at")
    search_fields = ("user__email", "fcm_token")
    ordering = ("-last_seen_at",)
    raw_id_fields = ["user"]
    list_per_page = 50
