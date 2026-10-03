from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from apps.accounts.responses import api_error, api_success
from apps.privacy_security.constants import AUTO_LOCK_LABELS, PRIVACY_SECTIONS, TERMS_SECTIONS
from apps.privacy_security.services import clear_cache, document_payload, get_privacy_security, screen_payload

TOGGLE_FIELDS = (
    "enable_app_lock",
    "biometric_unlock",
    "lock_on_app_exit",
    "hide_amounts_on_dashboard",
)


class PrivacySecurityView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        preference = get_privacy_security(request.user)
        return api_success(data=screen_payload(preference))

    def patch(self, request):
        preference = get_privacy_security(request.user)
        updated = False
        for field in TOGGLE_FIELDS:
            if field not in request.data:
                continue
            value = request.data.get(field)
            if not isinstance(value, bool):
                return api_error(f"{field} must be true or false.", status_code=status.HTTP_400_BAD_REQUEST)
            setattr(preference, field, value)
            updated = True
        if "auto_lock_after" in request.data:
            value = (request.data.get("auto_lock_after") or "").strip()
            if value not in AUTO_LOCK_LABELS:
                return api_error(
                    "Invalid auto_lock_after. Allowed values: " + ", ".join(AUTO_LOCK_LABELS) + ".",
                    status_code=status.HTTP_400_BAD_REQUEST,
                )
            preference.auto_lock_after = value
            updated = True
        if not updated:
            return api_error("No settings were provided.", status_code=status.HTTP_400_BAD_REQUEST)
        preference.save()
        return api_success(data=screen_payload(preference), message="Privacy and security settings saved.")


class PrivacySecurityClearCacheView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        preference = clear_cache(get_privacy_security(request.user))
        return api_success(
            data={
                "cleared": True,
                "cache_cleared_at": preference.cache_cleared_at,
            },
            message="Temporary files cleared.",
        )


class PrivacyPolicyView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return api_success(data=document_payload("Privacy Policy", PRIVACY_SECTIONS))


class TermsOfServiceView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return api_success(data=document_payload("Terms of Service", TERMS_SECTIONS))
