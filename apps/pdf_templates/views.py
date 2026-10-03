from django.db import IntegrityError
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from apps.accounts.responses import api_error, api_success
from apps.pdf_templates.constants import DOCUMENT_TYPE_MAP, theme_options
from apps.pdf_templates.models import PdfTemplate
from apps.pdf_templates.serializers import (
    BankDetailsSerializer,
    PdfTemplateSerializer,
    PdfTemplateWriteSerializer,
    SignatureSerializer,
    template_detail,
)
from apps.pdf_templates.services import (
    ensure_standard_templates,
    next_custom_name,
    resolve_organization,
    set_default_template,
)

NO_ORGANIZATION_MESSAGE = "Organization not found. Complete organization setup first."
DUPLICATE_NAME_MESSAGE = "A template with this name already exists for this document."


def organization_id_from(request):
    return request.query_params.get("organization_id") or request.data.get("organization_id")


def load_organization(request, document_type=None):
    organization = resolve_organization(request.user, organization_id_from(request))
    if not organization:
        return None, api_error(NO_ORGANIZATION_MESSAGE, status_code=status.HTTP_400_BAD_REQUEST)
    ensure_standard_templates(organization, document_type)
    return organization, None


def template_queryset(user):
    return PdfTemplate.objects.filter(organization__owner=user).select_related(
        "organization",
        "organization__owner",
    )


def get_template_id(request):
    return request.query_params.get("template_id") or request.query_params.get("id")


def document_type_from(request):
    return (request.query_params.get("document_type") or request.data.get("document_type") or "").strip()


def invalid_document_type():
    return api_error(
        "Invalid document_type. Allowed values: " + ", ".join(DOCUMENT_TYPE_MAP) + ".",
        status_code=status.HTTP_400_BAD_REQUEST,
    )


class PdfTemplateIndexView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        organization, error = load_organization(request)
        if error:
            return error
        sections = []
        for code, info in DOCUMENT_TYPE_MAP.items():
            sections.append(
                {
                    "document_type": code,
                    "label": info["label"],
                    "document_title": info["title"],
                    "url": request.build_absolute_uri(f"/api/pdf-templates/list/?document_type={code}"),
                }
            )
        return api_success(
            data={
                "organization_id": str(organization.id),
                "organization_name": organization.name,
                "sections": sections,
            }
        )


class PdfTemplateOptionsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return api_success(
            data={
                "document_types": [
                    {"value": code, "label": info["label"], "document_title": info["title"]}
                    for code, info in DOCUMENT_TYPE_MAP.items()
                ],
                "themes": theme_options(),
            }
        )


class PdfTemplateListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        document_type = document_type_from(request)
        if document_type not in DOCUMENT_TYPE_MAP:
            return invalid_document_type()
        organization, error = load_organization(request, document_type)
        if error:
            return error
        templates = PdfTemplate.objects.filter(
            organization=organization,
            document_type=document_type,
        ).select_related("organization", "organization__owner")
        selected = templates.filter(is_default=True).first() or templates.first()
        return api_success(
            data={
                "document_type": document_type,
                "document_label": DOCUMENT_TYPE_MAP[document_type]["label"],
                "document_title": DOCUMENT_TYPE_MAP[document_type]["title"],
                "count": templates.count(),
                "selected_template_id": str(selected.id) if selected else None,
                "templates": PdfTemplateSerializer(templates, many=True).data,
                "preview": template_detail(selected)["preview"] if selected else None,
            }
        )

    def post(self, request):
        document_type = document_type_from(request)
        if document_type not in DOCUMENT_TYPE_MAP:
            return invalid_document_type()
        organization, error = load_organization(request, document_type)
        if error:
            return error
        payload = request.data.copy()
        if not (payload.get("name") or "").strip():
            payload["name"] = next_custom_name(organization, document_type)
        if not payload.get("theme"):
            payload["theme"] = "blue"
        serializer = PdfTemplateWriteSerializer(data=payload)
        if not serializer.is_valid():
            return api_error("Validation error", errors=serializer.errors)
        if PdfTemplate.objects.filter(
            organization=organization,
            document_type=document_type,
            name__iexact=serializer.validated_data["name"],
        ).exists():
            return api_error(DUPLICATE_NAME_MESSAGE)
        try:
            template = serializer.save(organization=organization, document_type=document_type)
        except IntegrityError:
            return api_error(DUPLICATE_NAME_MESSAGE)
        if template.is_default:
            set_default_template(template)
        return api_success(
            data=template_detail(template),
            message="Template added.",
            status_code=status.HTTP_201_CREATED,
        )


class PdfTemplateDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        template_id = get_template_id(request)
        if not template_id:
            return api_error(
                "template_id query parameter is required.",
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        template = get_object_or_404(template_queryset(request.user), pk=template_id)
        return api_success(data=template_detail(template))

    def put(self, request):
        return self._update(request, partial=False)

    def patch(self, request):
        return self._update(request, partial=True)

    def _update(self, request, partial):
        template_id = get_template_id(request)
        if not template_id:
            return api_error(
                "template_id query parameter is required.",
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        template = get_object_or_404(template_queryset(request.user), pk=template_id)
        serializer = PdfTemplateWriteSerializer(template, data=request.data, partial=partial)
        if not serializer.is_valid():
            return api_error("Validation error", errors=serializer.errors)
        name = serializer.validated_data.get("name", template.name)
        if (
            PdfTemplate.objects.filter(
                organization=template.organization,
                document_type=template.document_type,
                name__iexact=name,
            )
            .exclude(pk=template.pk)
            .exists()
        ):
            return api_error(DUPLICATE_NAME_MESSAGE)
        make_default = serializer.validated_data.get("is_default", template.is_default)
        if template.is_default and serializer.validated_data.get("is_default") is False:
            return api_error("Choose another template before removing the default.")
        try:
            template = serializer.save()
        except IntegrityError:
            return api_error(DUPLICATE_NAME_MESSAGE)
        if make_default:
            set_default_template(template)
        return api_success(data=template_detail(template), message="Template saved.")

    def delete(self, request):
        template_id = get_template_id(request)
        if not template_id:
            return api_error(
                "template_id query parameter is required.",
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        template = get_object_or_404(template_queryset(request.user), pk=template_id)
        if template.is_system:
            return api_error("The Standard template cannot be deleted.")
        document_type = template.document_type
        organization = template.organization
        was_default = template.is_default
        template.delete()
        if was_default:
            standard = PdfTemplate.objects.filter(
                organization=organization,
                document_type=document_type,
                is_system=True,
            ).first()
            if standard:
                set_default_template(standard)
        return api_success(message="Template deleted.")


class PdfTemplateBankDetailsView(APIView):
    permission_classes = [IsAuthenticated]

    def patch(self, request):
        return self._save(request, partial=True)

    def put(self, request):
        return self._save(request, partial=False)

    def _save(self, request, partial):
        template = self._template(request)
        if isinstance(template, PdfTemplate) is False:
            return template
        serializer = BankDetailsSerializer(template, data=request.data, partial=partial)
        if not serializer.is_valid():
            return api_error("Validation error", errors=serializer.errors)
        template = serializer.save()
        return api_success(data=template_detail(template), message="Bank details saved.")

    def _template(self, request):
        template_id = get_template_id(request)
        if not template_id:
            return api_error(
                "template_id query parameter is required.",
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        return get_object_or_404(template_queryset(request.user), pk=template_id)


class PdfTemplateSignatureView(APIView):
    permission_classes = [IsAuthenticated]

    def patch(self, request):
        return self._save(request, partial=True)

    def put(self, request):
        return self._save(request, partial=False)

    def _save(self, request, partial):
        template_id = get_template_id(request)
        if not template_id:
            return api_error(
                "template_id query parameter is required.",
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        template = get_object_or_404(template_queryset(request.user), pk=template_id)
        serializer = SignatureSerializer(template, data=request.data, partial=partial)
        if not serializer.is_valid():
            return api_error("Validation error", errors=serializer.errors)
        template = serializer.save()
        return api_success(data=template_detail(template), message="Signature saved.")
