import logging

from apps.accounts.models import User

logger = logging.getLogger(__name__)


def update_display_name(user: User, display_name: str) -> User:
    """Persist a pre-validated display_name for the user."""
    user.display_name = display_name.strip()
    user.save(update_fields=["display_name", "updated_at"])
    logger.info("display_name_updated", extra={"event": "display_name_updated", "user_id": user.pk})
    return user


def register_or_get_user(firebase_uid: str, email: str, display_name: str) -> tuple[User, bool]:
    """Get the User for the given firebase_uid, creating it if it does not exist."""
    user, created = User.objects.get_or_create(
        firebase_uid=firebase_uid,
        defaults={"email": email, "display_name": display_name},
    )
    if created:
        logger.info(
            "user_created",
            extra={"event": "user_created", "user_id": user.pk, "firebase_uid": firebase_uid},
        )
    else:
        changed = False
        if email and user.email != email:
            user.email = email
            changed = True
        if display_name and user.display_name != display_name:
            user.display_name = display_name
            changed = True
        if changed:
            user.save(update_fields=["email", "display_name", "updated_at"])
    return user, created
