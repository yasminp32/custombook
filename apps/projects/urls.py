from django.urls import path

from apps.projects.views import (
    ProjectCancelView,
    ProjectExportView,
    ProjectFormView,
    ProjectMarkCompletedView,
    ProjectMarkOnHoldView,
    ProjectOptionsView,
    ProjectRefreshView,
    ProjectView,
)

urlpatterns = [
    path("", ProjectView.as_view(), name="projects"),
    path("options/", ProjectOptionsView.as_view(), name="project-options"),
    path("form/", ProjectFormView.as_view(), name="project-form"),
    path("refresh/", ProjectRefreshView.as_view(), name="project-refresh"),
    path("export/", ProjectExportView.as_view(), name="project-export"),
    path("mark-completed/", ProjectMarkCompletedView.as_view(), name="project-mark-completed"),
    path("mark-on-hold/", ProjectMarkOnHoldView.as_view(), name="project-mark-on-hold"),
    path("cancel/", ProjectCancelView.as_view(), name="project-cancel"),
]
