from django.urls import path

from apps.feedback.views import FeedbackListView, FeedbackView

urlpatterns = [
    path("", FeedbackView.as_view(), name="feedback"),
    path("submissions/", FeedbackListView.as_view(), name="feedback-submissions"),
]
