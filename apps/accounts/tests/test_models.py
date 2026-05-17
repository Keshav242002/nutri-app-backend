import pytest

from apps.accounts.tests.factories import UserFactory


@pytest.mark.django_db
class TestUserModel:
    def test_str_returns_email(self) -> None:
        user = UserFactory(email="hello@example.com")
        assert str(user) == "hello@example.com"

    def test_firebase_uid_is_username_field(self) -> None:
        from apps.accounts.models import User

        assert User.USERNAME_FIELD == "firebase_uid"

    def test_required_fields_contains_email(self) -> None:
        from apps.accounts.models import User

        assert "email" in User.REQUIRED_FIELDS
