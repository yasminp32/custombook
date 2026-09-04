from django.urls import path

from apps.attachments.views import AttachmentView

urlpatterns = [
    path("", AttachmentView.as_view(), name="attachments"),
]
