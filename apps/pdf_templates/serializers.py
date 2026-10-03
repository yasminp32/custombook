import re

from rest_framework import serializers

from apps.pdf_templates.constants import DOCUMENT_TYPE_MAP, SIGNATURE_HINT, THEME_MAP, theme_options
from apps.pdf_templates.models import PdfTemplate
from apps.pdf_templates.services import build_preview

ACCOUNT_RE = re.compile(r"^[A-Za-z0-9 \-]{0,40}$")
CODE_RE = re.compile(r"^[A-Za-z0-9]{0,20}$")


class PdfTemplateSerializer(serializers.ModelSerializer):
    template_id = serializers.UUIDField(source="id", read_only=True)
    document_label = serializers.SerializerMethodField()
    document_title = serializers.SerializerMethodField()
    theme_label = serializers.SerializerMethodField()
    theme_color = serializers.SerializerMethodField()
    themes = serializers.SerializerMethodField()
    bank_details = serializers.SerializerMethodField()
    signature = serializers.SerializerMethodField()

    class Meta:
        model = PdfTemplate
        fields = (
            "template_id",
            "document_type",
            "document_label",
            "document_title",
            "name",
            "theme",
            "theme_label",
            "theme_color",
            "themes",
            "is_default",
            "is_system",
            "bank_details",
            "signature",
            "created_at",
            "updated_at",
        )
        read_only_fields = fields

    def get_document_label(self, obj):
        return DOCUMENT_TYPE_MAP[obj.document_type]["label"]

    def get_document_title(self, obj):
        return DOCUMENT_TYPE_MAP[obj.document_type]["title"]

    def get_theme_label(self, obj):
        return THEME_MAP[obj.theme]["label"]

    def get_theme_color(self, obj):
        return THEME_MAP[obj.theme]["color"]

    def get_themes(self, obj):
        options = theme_options()
        for option in options:
            option["selected"] = option["value"] == obj.theme
        return options

    def get_bank_details(self, obj):
        return {
            "bank_name": obj.bank_name,
            "account_number": obj.account_number,
            "ifsc_swift_code": obj.ifsc_swift_code,
            "branch": obj.branch,
            "is_set": obj.bank_details_set,
        }

    def get_signature(self, obj):
        return {
            "signatory_name": obj.signatory_name,
            "hint": SIGNATURE_HINT,
            "is_set": bool(obj.signatory_name),
        }


class PdfTemplateWriteSerializer(serializers.ModelSerializer):
    is_default = serializers.BooleanField(required=False)

    class Meta:
        model = PdfTemplate
        fields = ("name", "theme", "is_default")

    def validate_name(self, value):
        value = (value or "").strip()
        if not value:
            raise serializers.ValidationError("Template name is required.")
        if len(value) > 100:
            raise serializers.ValidationError("Template name must be 100 characters or less.")
        return value

    def validate_theme(self, value):
        if value not in THEME_MAP:
            raise serializers.ValidationError(
                "Theme must be one of: " + ", ".join(THEME_MAP) + "."
            )
        return value


class BankDetailsSerializer(serializers.Serializer):
    bank_name = serializers.CharField(required=False, allow_blank=True, max_length=100)
    account_number = serializers.CharField(required=False, allow_blank=True, max_length=40)
    ifsc_swift_code = serializers.CharField(required=False, allow_blank=True, max_length=20)
    branch = serializers.CharField(required=False, allow_blank=True, max_length=100)

    def validate_bank_name(self, value):
        return value.strip()

    def validate_branch(self, value):
        return value.strip()

    def validate_account_number(self, value):
        value = value.strip()
        if value and not ACCOUNT_RE.match(value):
            raise serializers.ValidationError(
                "Account number may contain letters, numbers, spaces, and hyphens."
            )
        return value

    def validate_ifsc_swift_code(self, value):
        value = value.strip().upper()
        if value and not CODE_RE.match(value):
            raise serializers.ValidationError("IFSC / SWIFT code may contain only letters and numbers.")
        return value

    def update(self, instance, validated_data):
        for field, value in validated_data.items():
            setattr(instance, field, value)
        instance.save()
        return instance


class SignatureSerializer(serializers.Serializer):
    signatory_name = serializers.CharField(required=False, allow_blank=True, max_length=200)

    def validate_signatory_name(self, value):
        return value.strip()

    def update(self, instance, validated_data):
        instance.signatory_name = validated_data.get("signatory_name", instance.signatory_name)
        instance.save()
        return instance


def template_detail(template):
    data = PdfTemplateSerializer(template).data
    data["preview"] = build_preview(template)
    return data
