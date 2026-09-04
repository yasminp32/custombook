import django_filters

from apps.attachments.models import Attachment


class AttachmentFilter(django_filters.FilterSet):
    attachment_id = django_filters.UUIDFilter(field_name="id")
    id = django_filters.UUIDFilter(field_name="id")
    organization_id = django_filters.UUIDFilter(field_name="organization_id")
    file_name = django_filters.CharFilter(lookup_expr="icontains")
    mime_type = django_filters.CharFilter(lookup_expr="icontains")
    attachable_type = django_filters.CharFilter(lookup_expr="iexact")
    attachable_id = django_filters.UUIDFilter(field_name="attachable_id")

    class Meta:
        model = Attachment
        fields = (
            "attachment_id",
            "id",
            "organization_id",
            "file_name",
            "mime_type",
            "attachable_type",
            "attachable_id",
        )
