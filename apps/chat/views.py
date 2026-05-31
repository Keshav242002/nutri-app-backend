from __future__ import annotations

import json
import logging
from typing import Any

from django.http import StreamingHttpResponse
from rest_framework.renderers import JSONRenderer
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from core.exceptions import NotFoundError
from core.pagination import StandardCursorPagination
from core.responses import success_response

from .models import ChatSession
from .serializers import (
    ChatMessageSerializer,
    ChatSessionSerializer,
    CreateSessionSerializer,
    SendMessageSerializer,
)
from .services import chat_service

logger = logging.getLogger(__name__)


class EventStreamRenderer(JSONRenderer):
    """Renderer that accepts text/event-stream for SSE content negotiation."""

    media_type = "text/event-stream"
    format = "event-stream"


def _wants_sse(request: Request) -> bool:
    return request.headers.get("Accept", "") == "text/event-stream"


def _sse_event(data: str) -> str:
    return f"data: {json.dumps({'chunk': data})}\n\n"


def _sse_done() -> str:
    return "data: [DONE]\n\n"


class ChatSessionListCreateView(APIView):
    def get(self, request: Request) -> Response:
        qs = chat_service.list_sessions(request.user)  # type: ignore[arg-type]
        paginator = StandardCursorPagination()
        page = paginator.paginate_queryset(qs, request)
        serializer = ChatSessionSerializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)

    def post(self, request: Request) -> Response:
        serializer = CreateSessionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        session = chat_service.create_session(
            user=request.user,  # type: ignore[arg-type]
            title=serializer.validated_data.get("title", ""),
        )
        return success_response(
            ChatSessionSerializer(session).data, "Session created.", status_code=201
        )


class ChatMessageListCreateView(APIView):
    renderer_classes = [JSONRenderer, EventStreamRenderer]

    def get(self, request: Request, session_id: int) -> Response:
        qs = chat_service.get_session_messages(session_id, request.user)  # type: ignore[arg-type]
        paginator = StandardCursorPagination()
        paginator.ordering = "created_at"
        page = paginator.paginate_queryset(qs, request)
        serializer = ChatMessageSerializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)

    def post(self, request: Request, session_id: int) -> Response | StreamingHttpResponse:
        try:
            session = ChatSession.objects.get(pk=session_id, user_id=request.user.pk)  # type: ignore[misc]
        except ChatSession.DoesNotExist as exc:
            raise NotFoundError(message="Chat session not found.") from exc

        serializer = SendMessageSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        content: str = serializer.validated_data["content"]
        mode: str = serializer.validated_data["mode"]
        ingredients: list[str] = serializer.validated_data.get("ingredients", [])

        if mode == "chat" and _wants_sse(request):
            return self._stream_response(session, content, request.user)

        if mode == "ingredient":
            msg = chat_service.send_message_ingredient(
                session=session,
                content=content,
                ingredients=ingredients,
                user=request.user,  # type: ignore[arg-type]
            )
        else:
            msg = chat_service.send_message_chat(
                session=session,
                content=content,
                user=request.user,  # type: ignore[arg-type]
            )

        return success_response(ChatMessageSerializer(msg).data, "Message sent.", status_code=201)

    def _stream_response(
        self, session: ChatSession, content: str, user: Any
    ) -> StreamingHttpResponse:
        def _generate() -> Any:
            try:
                for chunk in chat_service.send_message_chat_stream(session, content, user):
                    yield _sse_event(chunk)
                yield _sse_done()
            except Exception as exc:
                logger.error(
                    "sse_stream_error",
                    extra={
                        "event": "sse_stream_error",
                        "session_id": session.pk,
                        "error": str(exc),
                    },
                )
                yield f"data: {json.dumps({'error': str(exc)})}\n\n"

        response = StreamingHttpResponse(_generate(), content_type="text/event-stream")
        response["Cache-Control"] = "no-cache"
        response["X-Accel-Buffering"] = "no"
        return response
