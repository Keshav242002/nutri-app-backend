from django.urls import path

from .views import ChatMessageListCreateView, ChatSessionListCreateView

urlpatterns = [
    path("sessions/", ChatSessionListCreateView.as_view(), name="chat-sessions"),
    path(
        "sessions/<int:session_id>/messages/",
        ChatMessageListCreateView.as_view(),
        name="chat-messages",
    ),
]
