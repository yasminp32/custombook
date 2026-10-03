from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from apps.about.services import about_payload
from apps.accounts.responses import api_success


class AboutView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return api_success(data=about_payload(request))
