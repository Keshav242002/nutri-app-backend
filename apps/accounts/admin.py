from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from apps.accounts.models import User


@admin.register(User)
class UserAdmin(BaseUserAdmin):  # type: ignore[type-arg]
    list_display = ["firebase_uid", "email", "display_name", "is_active", "is_staff", "created_at"]
    list_filter = ["is_active", "is_staff"]
    search_fields = ["firebase_uid", "email", "display_name"]
    ordering = ["-created_at"]
    readonly_fields = ["firebase_uid", "created_at", "updated_at"]

    fieldsets = (
        (None, {"fields": ("firebase_uid", "email", "display_name")}),
        (
            "Permissions",
            {"fields": ("is_active", "is_staff", "is_superuser", "groups", "user_permissions")},
        ),
        ("Timestamps", {"fields": ("created_at", "updated_at")}),
    )
    add_fieldsets = ((None, {"fields": ("firebase_uid", "email", "display_name")}),)
    filter_horizontal = ["groups", "user_permissions"]
