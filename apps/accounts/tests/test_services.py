import pytest

from apps.accounts.models import User
from apps.accounts.services.accounts import register_or_get_user, update_display_name
from apps.accounts.tests.factories import UserFactory


@pytest.mark.django_db
class TestRegisterOrGetUser:
    def test_register_or_get_user_creates_new_user(self) -> None:
        user, created = register_or_get_user(
            firebase_uid="new-uid-abc",
            email="new@example.com",
            display_name="New User",
        )
        assert created is True
        assert user.firebase_uid == "new-uid-abc"
        assert user.email == "new@example.com"
        assert user.display_name == "New User"
        assert User.objects.filter(firebase_uid="new-uid-abc").exists()

    def test_register_or_get_user_is_idempotent(self) -> None:
        UserFactory(firebase_uid="existing-uid", email="existing@example.com")
        user, created = register_or_get_user(
            firebase_uid="existing-uid",
            email="existing@example.com",
            display_name="Existing User",
        )
        assert created is False
        assert User.objects.filter(firebase_uid="existing-uid").count() == 1

    def test_register_or_get_user_updates_display_name(self) -> None:
        UserFactory(firebase_uid="uid-update", email="u@example.com", display_name="Old Name")
        user, created = register_or_get_user(
            firebase_uid="uid-update",
            email="u@example.com",
            display_name="New Name",
        )
        assert created is False
        assert user.display_name == "New Name"


@pytest.mark.django_db
class TestUpdateDisplayName:
    def test_sets_name_and_persists(self) -> None:
        user = UserFactory(display_name="")
        result = update_display_name(user, "Keshav")
        assert result.display_name == "Keshav"
        user.refresh_from_db()
        assert user.display_name == "Keshav"

    def test_strips_whitespace(self) -> None:
        user = UserFactory(display_name="")
        result = update_display_name(user, "  Keshav  ")
        assert result.display_name == "Keshav"

    def test_idempotent_same_name(self) -> None:
        user = UserFactory(display_name="Keshav")
        result = update_display_name(user, "Keshav")
        assert result.display_name == "Keshav"
