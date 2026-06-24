import factory
from factory.django import DjangoModelFactory

from apps.accounts.tests.factories import UserFactory
from apps.notifications.models import (
    CATEGORY_DAILY_TARGET,
    PLATFORM_ANDROID,
    DeviceToken,
    Notification,
)


class NotificationFactory(DjangoModelFactory):
    class Meta:
        model = Notification

    user = factory.SubFactory(UserFactory)
    category = CATEGORY_DAILY_TARGET
    title = "Target hit!"
    body = "You met your goals today."
    data = factory.LazyAttribute(lambda _: {"route": "tracker/today"})
    read_at = None
    dedup_key = factory.Sequence(lambda n: f"test-key-{n}")


class DeviceTokenFactory(DjangoModelFactory):
    class Meta:
        model = DeviceToken

    user = factory.SubFactory(UserFactory)
    fcm_token = factory.Sequence(lambda n: f"fcm-token-{n}")
    platform = PLATFORM_ANDROID
