from rest_framework import serializers

from apps.accounts.models import User


class UserSerializer(serializers.ModelSerializer[User]):
    has_profile = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ["id", "firebase_uid", "email", "display_name", "has_profile"]
        read_only_fields = fields

    def get_has_profile(self, obj: User) -> bool:
        try:
            return obj.profile is not None  # type: ignore[attr-defined]  # M2 adds reverse relation
        except AttributeError:
            return False


class RegisterResponseSerializer(UserSerializer):
    created = serializers.SerializerMethodField()

    class Meta(UserSerializer.Meta):
        fields = [*UserSerializer.Meta.fields, "created"]
        read_only_fields = fields

    def get_created(self, obj: User) -> bool:
        return bool(self.context.get("created", False))
