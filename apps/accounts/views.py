from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.views import APIView
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from apps.accounts.countries import (
    get_country_states_payload,
    get_registration_options,
    is_valid_country,
)
from apps.accounts.responses import api_error, api_success
from apps.accounts.serializers import (
    CustomTokenObtainPairSerializer,
    ForgotPasswordSerializer,
    OrganizationSerializer,
    RegisterResponseSerializer,
    RegisterSerializer,
    ResetPasswordSerializer,
    UserSerializer,
    VerifyOTPSerializer,
)
from apps.accounts.password_reset import create_and_send_password_reset, reset_password_with_otp
from apps.accounts.services import verify_otp

User = get_user_model()


class RegistrationOptionsView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        return api_success(data=get_registration_options())


class CountryStatesView(APIView):
    permission_classes = [AllowAny]

    def get(self, request, country_code):
        if not is_valid_country(country_code):
            return api_error("Unsupported country.")
        return api_success(data=get_country_states_payload(country_code))


class StatesView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        if "country" not in request.query_params:
            return api_error("country is required.")
        country = request.query_params.get("country")
        if country is None or not str(country).strip():
            return api_error("country cannot be empty.")
        country = str(country).strip()
        if not is_valid_country(country):
            return api_error("Unsupported country.")
        return api_success(data=get_country_states_payload(country))


class RegisterView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        if not serializer.is_valid():
            return api_error("Validation error", errors=serializer.errors)

        result = serializer.save()
        if result.get("skip_email_otp"):
            message = "Registration successful. Email OTP is disabled. You can log in now."
        elif result.get("email_sent", True):
            message = "Registration successful. Please verify your email with the OTP sent."
        else:
            message = (
                "Registration successful, but the OTP email could not be sent "
                "(mail provider limit or SMTP error). Use otp_code from this "
                "response in DEBUG, or check the server console."
            )
        return api_success(
            data=RegisterResponseSerializer(result).data,
            message=message,
            status_code=status.HTTP_201_CREATED,
        )


class VerifyOTPView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = VerifyOTPSerializer(data=request.data)
        if not serializer.is_valid():
            return api_error("Validation error", errors=serializer.errors)

        email = serializer.validated_data["email"]
        code = serializer.validated_data["code"]

        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            return api_error("User not found", status_code=status.HTTP_404_NOT_FOUND)

        if verify_otp(user, code):
            return api_success(
                data=UserSerializer(user).data,
                message="Email verified successfully.",
            )
        return api_error("Invalid or expired OTP")


class ForgotPasswordView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = ForgotPasswordSerializer(data=request.data)
        if not serializer.is_valid():
            return api_error("Validation error", errors=serializer.errors)

        email = User.objects.normalize_email(serializer.validated_data["email"])
        user = User.objects.filter(email=email, is_email_verified=True).first()
        if user:
            create_and_send_password_reset(user)

        return api_success(
            message=(
                "If an account with that email exists, "
                "a password reset code has been sent."
            )
        )


class ResetPasswordView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = ResetPasswordSerializer(data=request.data)
        if not serializer.is_valid():
            return api_error("Validation error", errors=serializer.errors)

        email = User.objects.normalize_email(serializer.validated_data["email"])
        user = reset_password_with_otp(
            User.objects.filter(email=email, is_email_verified=True).first(),
            serializer.validated_data["otp"],
            serializer.validated_data["password"],
        )
        if not user:
            return api_error(
                "Invalid or expired reset code.",
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        return api_success(message="Password reset successfully. You can now log in.")


class LoginView(TokenObtainPairView):
    permission_classes = [AllowAny]
    serializer_class = CustomTokenObtainPairSerializer


class TokenRefreshAPIView(TokenRefreshView):
    permission_classes = [AllowAny]


class MeView(APIView):
    def get(self, request):
        organization = request.user.owned_organizations.order_by("created_at").first()
        return api_success(
            data={
                "user": UserSerializer(request.user).data,
                "organization": (
                    OrganizationSerializer(organization).data if organization else None
                ),
            }
        )
