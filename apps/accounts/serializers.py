from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError as DjangoValidationError
from django.conf import settings
from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

from apps.accounts.countries import PHONE_COUNTRY_CODES
from apps.accounts.login_security import (
    get_lockout_message,
    is_account_locked,
    record_failed_login,
    reset_login_security,
)
from apps.accounts.registration import register_user_with_organization
from apps.accounts.tokens import OrganizationRefreshToken
from apps.accounts.validators import (
    validate_country_code,
    validate_password_strength,
    validate_phone_country_code,
    validate_phone_number,
    validate_state_for_country,
)
from apps.organizations.serializers import OrganizationSerializer

User = get_user_model()


class UserSerializer(serializers.ModelSerializer):
    terms_accepted = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = (
            "id",
            "email",
            "user_type",
            "phone_country_code",
            "phone",
            "first_name",
            "last_name",
            "is_email_verified",
            "terms_accepted",
            "created_at",
        )
        read_only_fields = ("id", "is_email_verified", "terms_accepted", "created_at")

    def get_terms_accepted(self, obj):
        return obj.terms_accepted_at is not None


class RegisterSerializer(serializers.Serializer):
    user_type = serializers.ChoiceField(choices=User.UserType.choices)
    company_name = serializers.CharField(max_length=255, required=False, allow_blank=True)
    email = serializers.EmailField()
    phone_country_code = serializers.CharField(max_length=5)
    phone = serializers.CharField(max_length=15)
    password = serializers.CharField(write_only=True)
    country = serializers.CharField(max_length=2)
    state = serializers.CharField(max_length=100, required=False, allow_blank=True)
    terms_accepted = serializers.BooleanField()

    def validate_email(self, value):
        email = User.objects.normalize_email(value)
        existing_user = User.objects.filter(email=email).first()
        if existing_user:
            if existing_user.is_email_verified:
                raise serializers.ValidationError(
                    "An account with this email already exists. Please log in instead."
                )
            raise serializers.ValidationError(
                "This email is already registered but not verified. "
                "Use verify-otp with your OTP, or register with a different email."
            )
        return email

    def validate_password(self, value):
        validate_password_strength(value)
        return value

    def validate_phone_country_code(self, value):
        return validate_phone_country_code(value)

    def validate_phone(self, value):
        return validate_phone_number(value)

    def validate_country(self, value):
        return validate_country_code(value)

    def validate_terms_accepted(self, value):
        if not value:
            raise serializers.ValidationError(
                "You must accept the Terms of Service and Privacy Policy."
            )
        return value

    def validate(self, attrs):
        user_type = attrs.get("user_type")
        company_name = attrs.get("company_name", "").strip()
        country = attrs.get("country")
        state = attrs.get("state", "").strip()
        phone_country_code = attrs.get("phone_country_code")
        country_phone_code = PHONE_COUNTRY_CODES.get(country)

        if user_type in (User.UserType.BUSINESS_USER, User.UserType.TAX_CONSULTANT):
            if not company_name:
                raise serializers.ValidationError(
                    {"company_name": "Company name is required for this account type."}
                )

        if country_phone_code and phone_country_code != country_phone_code:
            raise serializers.ValidationError(
                {
                    "phone_country_code": (
                        f"Phone country code must match the selected country ({country_phone_code})."
                    )
                }
            )

        try:
            attrs["state"] = validate_state_for_country(country, state)
        except DjangoValidationError as exc:
            raise serializers.ValidationError({"state": exc.messages}) from exc

        attrs["company_name"] = company_name
        return attrs

    def create(self, validated_data):
        return register_user_with_organization(validated_data)


class RegisterResponseSerializer(serializers.Serializer):
    user = UserSerializer()
    organization = OrganizationSerializer(allow_null=True)
    data_center = serializers.CharField()
    email_sent = serializers.BooleanField(required=False)
    skip_email_otp = serializers.BooleanField(required=False)
    otp_code = serializers.CharField(required=False, allow_blank=True)


class VerifyOTPSerializer(serializers.Serializer):
    email = serializers.EmailField()
    code = serializers.CharField(max_length=6)


class ForgotPasswordSerializer(serializers.Serializer):
    email = serializers.EmailField()


class ResetPasswordSerializer(serializers.Serializer):
    email = serializers.EmailField()
    otp = serializers.CharField(max_length=6)
    password = serializers.CharField(write_only=True)
    confirm_password = serializers.CharField(write_only=True)

    def validate_password(self, value):
        validate_password_strength(value)
        return value

    def validate(self, attrs):
        if attrs["password"] != attrs["confirm_password"]:
            raise serializers.ValidationError(
                {"confirm_password": "Passwords do not match."}
            )
        return attrs


class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    username_field = User.USERNAME_FIELD

    @classmethod
    def get_token(cls, user):
        organization = user.owned_organizations.order_by("created_at").first()
        organization_id = organization.id if organization else None
        return OrganizationRefreshToken.for_user(user, organization_id=organization_id)

    def validate(self, attrs):
        email = attrs.get(self.username_field)
        user = None
        if email:
            user = User.objects.filter(email=User.objects.normalize_email(email)).first()
            if user and is_account_locked(user):
                raise serializers.ValidationError(get_lockout_message(user))

        try:
            data = super().validate(attrs)
        except serializers.ValidationError as exc:
            if user:
                record_failed_login(user)
                if is_account_locked(user):
                    raise serializers.ValidationError(get_lockout_message(user)) from exc

                remaining = settings.MAX_FAILED_LOGIN_ATTEMPTS - user.failed_login_attempts
                if remaining > 0:
                    raise serializers.ValidationError(
                        f"Invalid email or password. {remaining} attempt(s) remaining."
                    ) from exc
                raise serializers.ValidationError(get_lockout_message(user)) from exc
            raise

        if not self.user.is_email_verified and not settings.SKIP_EMAIL_OTP:
            raise serializers.ValidationError("Email is not verified. Please verify your OTP.")

        reset_login_security(self.user)
        data["user"] = UserSerializer(self.user).data
        organization = self.user.owned_organizations.order_by("created_at").first()
        data["organization"] = (
            OrganizationSerializer(organization).data if organization else None
        )
        return data
