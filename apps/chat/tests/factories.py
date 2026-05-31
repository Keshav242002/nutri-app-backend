import factory
from factory.django import DjangoModelFactory

from apps.accounts.tests.factories import UserFactory
from apps.chat.models import ChatMessage, ChatSession


class ChatSessionFactory(DjangoModelFactory):
    class Meta:
        model = ChatSession

    user = factory.SubFactory(UserFactory)
    title = factory.Sequence(lambda n: f"Session {n}")


class ChatMessageFactory(DjangoModelFactory):
    class Meta:
        model = ChatMessage

    session = factory.SubFactory(ChatSessionFactory)
    role = ChatMessage.Role.USER
    content = factory.Sequence(lambda n: f"Message content {n}")
    metadata = None
