from django.contrib import admin

from .models import ChatMessage, ChatSession


@admin.register(ChatSession)
class ChatSessionAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "title", "started_at", "last_message_at")
    list_filter = ("started_at",)
    search_fields = ("user__email", "title")
    ordering = ("-last_message_at",)
    date_hierarchy = "started_at"
    raw_id_fields = ["user"]
    list_per_page = 50


@admin.register(ChatMessage)
class ChatMessageAdmin(admin.ModelAdmin):
    list_display = ("id", "session", "role", "created_at")
    list_filter = ("role", "created_at")
    search_fields = ("session__user__email", "content")
    ordering = ("-created_at",)
    raw_id_fields = ["session"]
    readonly_fields = ["content", "metadata"]
    list_per_page = 50
