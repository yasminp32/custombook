from django.urls import path

from apps.branches.views import BranchView

urlpatterns = [
    path("", BranchView.as_view(), name="branches"),
]
