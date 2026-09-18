from django.db.models import Q
import django_filters

from apps.inbox.models import InboxDocument


def normalize_key(value):
    return (value or "").strip().lower().replace(" ", "_").rstrip(".")


class InboxDocumentFilter(django_filters.FilterSet):
    document_id = django_filters.UUIDFilter(field_name="id")
    inbox_id = django_filters.UUIDFilter(field_name="id")
    id = django_filters.UUIDFilter(field_name="id")
    organization_id = django_filters.UUIDFilter(field_name="organization_id")
    name = django_filters.CharFilter(lookup_expr="icontains")
    file_type = django_filters.CharFilter(method="filter_file_type")
    type = django_filters.CharFilter(method="filter_file_type")
    folder = django_filters.CharFilter(lookup_expr="iexact")
    search = django_filters.CharFilter(method="filter_search")

    class Meta:
        model = InboxDocument
        fields = (
            "document_id",
            "inbox_id",
            "id",
            "organization_id",
            "name",
            "file_type",
            "type",
            "folder",
            "search",
        )

    def filter_search(self, queryset, name, value):
        value = (value or "").strip()
        if not value:
            return queryset
        return queryset.filter(
            Q(name__icontains=value)
            | Q(file_type__icontains=value)
            | Q(folder__icontains=value)
        )

    def filter_file_type(self, queryset, name, value):
        key = normalize_key(value)
        aliases = {
            "pdf": InboxDocument.FileType.PDF,
            "image": InboxDocument.FileType.IMAGE,
            "spreadsheet": InboxDocument.FileType.SPREADSHEET,
            "document": InboxDocument.FileType.DOCUMENT,
        }
        if not key or key in ("all", "all_types"):
            return queryset
        if key not in aliases:
            return queryset.none()
        return queryset.filter(file_type=aliases[key])
