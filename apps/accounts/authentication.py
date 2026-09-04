from django.core.exceptions import ValidationError
from rest_framework.exceptions import AuthenticationFailed
from rest_framework_simplejwt.authentication import JWTAuthentication


class UUIDJWTAuthentication(JWTAuthentication):
    def get_user(self, validated_token):
        try:
            return super().get_user(validated_token)
        except (ValidationError, ValueError, self.user_model.DoesNotExist) as exc:
            raise AuthenticationFailed(
                "Invalid or expired token. Please log in again.",
                code="invalid_token",
            ) from exc
