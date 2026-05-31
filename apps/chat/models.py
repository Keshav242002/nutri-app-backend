from django.conf import settings
from django.db import models

from core.mixins import TimestampedModel


class ChatSession(TimestampedModel):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="chat_sessions",
        db_index=True,
    )
    title = models.CharField(max_length=200, blank=True, default="")
    started_at = models.DateTimeField(auto_now_add=True)
    last_message_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-last_message_at"]

    def __str__(self) -> str:
        return f"Session {self.pk} ({self.user_id})"


class ChatMessage(TimestampedModel):
    class Role(models.TextChoices):
        USER = "user", "User"
        ASSISTANT = "assistant", "Assistant"
        SYSTEM = "system", "System"

    session = models.ForeignKey(
        ChatSession,
        on_delete=models.CASCADE,
        related_name="messages",
        db_index=True,
    )
    role = models.CharField(max_length=20, choices=Role.choices)
    content = models.TextField()
    # Stores provider, model, token counts for assistant messages;
    # recipes list for ingredient-mode responses.
    metadata = models.JSONField(null=True, blank=True)

    class Meta:
        ordering = ["created_at"]
        indexes = [
            models.Index(fields=["session", "created_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.role} message in session {self.session_id}"
