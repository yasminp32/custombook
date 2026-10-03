from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from apps.accounts.responses import api_error, api_success
from apps.feedback.constants import CATEGORY_LABELS, MAX_STARS, SUBJECT_MAX_LENGTH
from apps.feedback.models import Feedback
from apps.feedback.services import current_organization, feedback_payload, form_payload


class FeedbackView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return api_success(data=form_payload())

    def post(self, request):
        rating = request.data.get("rating")
        if isinstance(rating, bool) or not isinstance(rating, int) or rating < 1 or rating > MAX_STARS:
            return api_error(
                f"Rating must be a whole number from 1 to {MAX_STARS}.",
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        category = (request.data.get("category") or "").strip()
        if category not in CATEGORY_LABELS:
            return api_error(
                "Invalid category. Allowed values: " + ", ".join(CATEGORY_LABELS) + ".",
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        subject = (request.data.get("subject") or "").strip()
        if not subject:
            return api_error("Subject is required.", status_code=status.HTTP_400_BAD_REQUEST)
        if len(subject) > SUBJECT_MAX_LENGTH:
            return api_error(
                f"Subject cannot be longer than {SUBJECT_MAX_LENGTH} characters.",
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        message = (request.data.get("message") or "").strip()
        if not message:
            return api_error("Your Feedback is required.", status_code=status.HTTP_400_BAD_REQUEST)
        feedback = Feedback.objects.create(
            user=request.user,
            organization=current_organization(request.user),
            rating=rating,
            category=category,
            subject=subject,
            message=message,
        )
        return api_success(
            data=feedback_payload(feedback),
            message="Feedback submitted.",
            status_code=status.HTTP_201_CREATED,
        )


class FeedbackListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        rows = Feedback.objects.filter(user=request.user)
        return api_success(data={"count": rows.count(), "results": [feedback_payload(row) for row in rows]})
