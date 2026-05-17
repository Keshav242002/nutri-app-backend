import factory

from apps.accounts.models import User


class UserFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = User

    firebase_uid = factory.Sequence(lambda n: f"firebase-uid-{n}")
    email = factory.Sequence(lambda n: f"user{n}@example.com")
    display_name = factory.Sequence(lambda n: f"User {n}")
    is_active = True
    is_staff = False
