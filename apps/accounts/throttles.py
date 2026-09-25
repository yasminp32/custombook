import math

from rest_framework import status
from rest_framework.exceptions import Throttled
from rest_framework.throttling import SimpleRateThrottle

from apps.accounts.responses import api_error


class EmailRateThrottle(SimpleRateThrottle):
    """Limits requests per submitted email; client IPs are spoofable behind the proxy."""

    def get_cache_key(self, request, view):
        data = request.data if isinstance(request.data, dict) else {}
        email = str(data.get("email") or "").strip().lower()
        if not email:
            return None
        return self.cache_format % {"scope": self.scope, "ident": email}


class ForgotPasswordThrottle(EmailRateThrottle):
    scope = "forgot_password"


class ResetPasswordThrottle(EmailRateThrottle):
    scope = "reset_password"


class VerifyOTPThrottle(EmailRateThrottle):
    scope = "verify_otp"


class ThrottledResponseMixin:
    def handle_exception(self, exc):
        if isinstance(exc, Throttled):
            wait = math.ceil(exc.wait) if exc.wait else None
            message = "Too many requests. Please try again later."
            if wait:
                message = f"Too many requests. Please try again in {wait} seconds."
            return api_error(message, status_code=status.HTTP_429_TOO_MANY_REQUESTS)
        return super().handle_exception(exc)
