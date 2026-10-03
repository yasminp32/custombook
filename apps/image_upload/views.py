from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from apps.accounts.responses import api_error, api_success
from apps.image_upload.constants import RESOLUTION_CODES
from apps.image_upload.services import get_resolution, resolution_payload


class ImageUploadResolutionView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        preference = get_resolution(request.user)
        return api_success(data=resolution_payload(preference))

    def patch(self, request):
        resolution = (request.data.get("resolution") or "").strip()
        if resolution not in RESOLUTION_CODES:
            return api_error(
                "Invalid resolution. Allowed values: " + ", ".join(sorted(RESOLUTION_CODES)) + ".",
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        preference = get_resolution(request.user)
        preference.resolution = resolution
        preference.save(update_fields=["resolution", "updated_at"])
        return api_success(data=resolution_payload(preference), message="Image upload resolution saved.")
