from apps.accounts.models import User


def register_or_get_user(firebase_uid: str, email: str, display_name: str) -> tuple[User, bool]:
    """Get the User for the given firebase_uid, creating it if it does not exist."""
    user, created = User.objects.get_or_create(
        firebase_uid=firebase_uid,
        defaults={"email": email, "display_name": display_name},
    )
    if not created:
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
