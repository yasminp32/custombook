from django.urls import path

from apps.audit_logs.views import AuditLogView

urlpatterns = [
    path("", AuditLogView.as_view(), name="audit-logs"),
]
