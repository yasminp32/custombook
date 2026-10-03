from django.urls import path

from apps.privacy_security.views import (
    PrivacyPolicyView,
    PrivacySecurityClearCacheView,
    PrivacySecurityView,
    TermsOfServiceView,
)

urlpatterns = [
    path("", PrivacySecurityView.as_view(), name="privacy-security"),
    path("clear-cache/", PrivacySecurityClearCacheView.as_view(), name="privacy-security-clear-cache"),
    path("privacy-policy/", PrivacyPolicyView.as_view(), name="privacy-policy"),
    path("terms/", TermsOfServiceView.as_view(), name="terms-of-service"),
]
