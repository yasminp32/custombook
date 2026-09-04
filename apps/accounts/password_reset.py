import secrets
from datetime import timedelta

from django.conf import settings
from django.core.mail import send_mail
from django.db.models import Q
from django.utils import timezone

from apps.accounts.login_security import reset_login_security
from apps.accounts.models import PasswordResetToken


def generate_reset_token():
    return secrets.token_urlsafe(48)


def cleanup_password_reset_tokens(user=None):
    queryset = PasswordResetToken.objects.filter(
        Q(expires_at__lte=timezone.now()) | Q(is_used=True)
    )
    if user is not None:
        queryset = queryset.filter(user=user)
    return queryset.delete()


def create_and_send_password_reset(user):
    PasswordResetToken.objects.filter(user=user, is_used=False).update(is_used=True)
    cleanup_password_reset_tokens(user=user)

    reset_token = generate_reset_token()
    expires_at = timezone.now() + timedelta(minutes=settings.PASSWORD_RESET_EXPIRY_MINUTES)

    PasswordResetToken.objects.create(
        user=user,
        reset_token=reset_token,
        expires_at=expires_at,
    )

    reset_url = settings.FRONTEND_PASSWORD_RESET_URL.rstrip("/")
    send_mail(
        subject="Reset your Techgeum password",
        message=(
            "We received a request to reset your password.\n\n"
            f"Reset token: {reset_token}\n\n"
            f"Or use this link: {reset_url}?reset_token={reset_token}\n\n"
            f"This link expires in {settings.PASSWORD_RESET_EXPIRY_MINUTES} minutes.\n\n"
            "If you did not request this, you can ignore this email."
        ),
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[user.email],
        fail_silently=False,
    )

    return reset_token


def reset_password_with_token(reset_token, new_password):
    try:
        token = PasswordResetToken.objects.select_related("user").get(
            reset_token=reset_token,
            is_used=False,
            expires_at__gt=timezone.now(),
        )
    except PasswordResetToken.DoesNotExist:
        return None

    user = token.user
    user.set_password(new_password)
    user.save(update_fields=["password", "updated_at"])

    token.is_used = True
    token.used_at = timezone.now()
    token.save(update_fields=["is_used", "used_at"])

    reset_login_security(user)
    cleanup_password_reset_tokens(user=user)
    return user
