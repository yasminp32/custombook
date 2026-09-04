from datetime import timedelta

from django.conf import settings
from django.utils import timezone


def clear_expired_lock(user):
    if user.locked_until and user.locked_until <= timezone.now():
        user.failed_login_attempts = 0
        user.locked_until = None
        user.save(update_fields=["failed_login_attempts", "locked_until", "updated_at"])


def is_account_locked(user):
    clear_expired_lock(user)
    return user.locked_until is not None and user.locked_until > timezone.now()


def get_lockout_message(user):
    locked_until = timezone.localtime(user.locked_until)
    return (
        f"Account is locked due to too many failed login attempts. "
        f"Try again after {locked_until.strftime('%Y-%m-%d %H:%M:%S')}."
    )


def record_failed_login(user):
    user.failed_login_attempts += 1
    update_fields = ["failed_login_attempts", "updated_at"]

    if user.failed_login_attempts >= settings.MAX_FAILED_LOGIN_ATTEMPTS:
        user.locked_until = timezone.now() + timedelta(minutes=settings.ACCOUNT_LOCKOUT_MINUTES)
        update_fields.append("locked_until")

    user.save(update_fields=update_fields)
    return user


def reset_login_security(user):
    if user.failed_login_attempts == 0 and user.locked_until is None:
        return user

    user.failed_login_attempts = 0
    user.locked_until = None
    user.save(update_fields=["failed_login_attempts", "locked_until", "updated_at"])
    return user
