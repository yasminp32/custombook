from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView

from apps.accounts.views import (
    CountryStatesView,
    ForgotPasswordView,
    LoginView,
    MeView,
    RegisterView,
    RegistrationOptionsView,
    ResetPasswordView,
    VerifyOTPView,
)

urlpatterns = [
    path("registration-options/", RegistrationOptionsView.as_view(), name="registration-options"),
    path("countries/<str:country_code>/states/", CountryStatesView.as_view(), name="country-states"),
    path("register/", RegisterView.as_view(), name="register"),
    path("login/", LoginView.as_view(), name="login"),
    path("verify-otp/", VerifyOTPView.as_view(), name="verify-otp"),
    path("forgot-password/", ForgotPasswordView.as_view(), name="forgot-password"),
    path("reset-password/", ResetPasswordView.as_view(), name="reset-password"),
    path("token/refresh/", TokenRefreshView.as_view(), name="token-refresh"),
    path("me/", MeView.as_view(), name="me"),
]
