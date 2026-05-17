from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.db import models


class UserManager(BaseUserManager["User"]):
    def create_user(self, firebase_uid: str, email: str, **extra: object) -> "User":
        user = self.model(firebase_uid=firebase_uid, email=self.normalize_email(email), **extra)
        user.set_unusable_password()
        user.save(using=self._db)
        return user

    def create_superuser(self, firebase_uid: str, email: str, **extra: object) -> "User":
        extra.setdefault("is_staff", True)
        extra.setdefault("is_superuser", True)
        return self.create_user(firebase_uid, email, **extra)


class User(AbstractBaseUser, PermissionsMixin):
    firebase_uid = models.CharField(max_length=128, unique=True, db_index=True)
    email = models.EmailField(unique=True)
    display_name = models.CharField(max_length=120, blank=True)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    USERNAME_FIELD = "firebase_uid"
    REQUIRED_FIELDS = ["email"]

    objects: UserManager = UserManager()

    class Meta:
        db_table = "accounts_user"

    def __str__(self) -> str:
        return self.email
