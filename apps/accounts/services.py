import random
import string
from datetime import timedelta

from django.conf import settings
from django.core.mail import send_mail
from django.db.models import Q
from django.utils import timezone

from apps.accounts.models import EmailOTP


def generate_otp_code(length=6):
    return "".join(random.choices(string.digits, k=length))


def cleanup_otps(user=None):
    queryset = EmailOTP.objects.filter(
        Q(expires_at__lte=timezone.now()) | Q(is_used=True)
    )
    if user is not None:
        queryset = queryset.filter(user=user)
    return queryset.delete()


def create_and_send_otp(user):
    EmailOTP.objects.filter(user=user, is_used=False).update(is_used=True)
    cleanup_otps(user=user)

    code = generate_otp_code()
    expires_at = timezone.now() + timedelta(minutes=settings.OTP_EXPIRY_MINUTES)

    otp = EmailOTP.objects.create(
        user=user,
        code=code,
        expires_at=expires_at,
    )

    send_mail(
        subject="Your Techgeum verification code",
        message=(
            f"Your verification code is: {code}\n\n"
            f"This code expires in {settings.OTP_EXPIRY_MINUTES} minutes."
        ),
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[user.email],
        fail_silently=False,
    )

    return otp


def verify_otp(user, code):
    try:
        otp = EmailOTP.objects.get(
            user=user,
            code=code,
            is_used=False,
            expires_at__gt=timezone.now(),
        )
    except EmailOTP.DoesNotExist:
        return False

    otp.is_used = True
    otp.save(update_fields=["is_used", "updated_at"])

    user.is_email_verified = True
    user.save(update_fields=["is_email_verified", "updated_at"])

    cleanup_otps(user=user)
    return True
