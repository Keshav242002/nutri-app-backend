from typing import Any

from rest_framework import serializers

from .models import ChatMessage, ChatSession


class ChatSessionSerializer(serializers.ModelSerializer[ChatSession]):
    message_count = serializers.SerializerMethodField()

    class Meta:
        model = ChatSession
        fields = ["id", "title", "started_at", "last_message_at", "message_count"]
        read_only_fields = ["id", "started_at", "last_message_at", "message_count"]

    def get_message_count(self, obj: ChatSession) -> int:
        return obj.messages.count()


class ChatMessageSerializer(serializers.ModelSerializer[ChatMessage]):
    class Meta:
        model = ChatMessage
        fields = ["id", "role", "content", "metadata", "created_at"]
        read_only_fields = ["id", "role", "content", "metadata", "created_at"]


class CreateSessionSerializer(serializers.Serializer[Any]):
    title = serializers.CharField(max_length=200, required=False, default="", allow_blank=True)


class SendMessageSerializer(serializers.Serializer[Any]):
    content = serializers.CharField(min_length=1)
    mode = serializers.ChoiceField(choices=["chat", "ingredient"], default="chat")
    ingredients = serializers.ListField(
        child=serializers.CharField(min_length=1),
        required=False,
        allow_empty=True,
        default=list,
    )

    def validate(self, data: dict[str, Any]) -> dict[str, Any]:
        if data.get("mode") == "ingredient" and not data.get("ingredients"):
            raise serializers.ValidationError(
                {"ingredients": "ingredients is required when mode is 'ingredient'."}
            )
        return data
