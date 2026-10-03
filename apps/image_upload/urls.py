from django.urls import path

from apps.image_upload.views import ImageUploadResolutionView

urlpatterns = [
    path("", ImageUploadResolutionView.as_view(), name="image-upload-resolution"),
]
