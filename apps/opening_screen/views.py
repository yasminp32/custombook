from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from apps.accounts.responses import api_error, api_success
from apps.opening_screen.constants import SCREEN_CODES
from apps.opening_screen.services import get_opening_screen, screen_payload


class OpeningScreenView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        preference = get_opening_screen(request.user)
        return api_success(data=screen_payload(preference))

    def patch(self, request):
        screen = (request.data.get("screen") or "").strip()
        if screen not in SCREEN_CODES:
            return api_error(
                "Invalid screen. Allowed values: " + ", ".join(SCREEN_CODES) + ".",
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        preference = get_opening_screen(request.user)
        preference.screen = screen
        preference.save(update_fields=["screen", "updated_at"])
        return api_success(data=screen_payload(preference), message="Opening screen saved.")
