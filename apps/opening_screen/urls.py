from django.urls import path

from apps.opening_screen.views import OpeningScreenView

urlpatterns = [
    path("", OpeningScreenView.as_view(), name="opening-screen"),
]
