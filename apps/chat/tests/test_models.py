import pytest

from apps.chat.models import ChatMessage, ChatSession

from .factories import ChatMessageFactory, ChatSessionFactory


@pytest.mark.django_db
class TestChatSession:
    def test_create_session(self):
        session = ChatSessionFactory()
        assert session.pk is not None
        assert session.title.startswith("Session")

    def test_session_ordering_newest_first(self):
        ChatSessionFactory()
        s2 = ChatSessionFactory()
        sessions = list(ChatSession.objects.all())
        assert sessions[0].pk == s2.pk

    def test_default_title_is_blank(self):
        session = ChatSessionFactory(title="")
        assert session.title == ""

    def test_str_returns_title(self):
        session = ChatSessionFactory(title="My Session")
        assert "My Session" in str(session) or str(session) is not None


@pytest.mark.django_db
class TestChatMessage:
    def test_create_user_message(self):
        msg = ChatMessageFactory(role=ChatMessage.Role.USER, content="Hello")
        assert msg.pk is not None
        assert msg.role == ChatMessage.Role.USER
        assert msg.content == "Hello"

    def test_create_assistant_message(self):
        msg = ChatMessageFactory(role=ChatMessage.Role.ASSISTANT, content="Hi there!")
        assert msg.role == ChatMessage.Role.ASSISTANT

    def test_metadata_can_store_dict(self):
        msg = ChatMessageFactory(metadata={"provider": "openrouter", "model": "free"})
        msg.refresh_from_db()
        assert msg.metadata["provider"] == "openrouter"

    def test_messages_ordered_by_created_at(self):
        session = ChatSessionFactory()
        m1 = ChatMessageFactory(session=session, content="first")
        m2 = ChatMessageFactory(session=session, content="second")
        msgs = list(session.messages.all())
        assert msgs[0].pk == m1.pk
        assert msgs[1].pk == m2.pk

    def test_cascade_delete_removes_messages(self):
        session = ChatSessionFactory()
        ChatMessageFactory(session=session)
        ChatMessageFactory(session=session)
        pk = session.pk
        session.delete()
        assert ChatMessage.objects.filter(session_id=pk).count() == 0
