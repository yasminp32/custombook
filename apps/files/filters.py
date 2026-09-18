from django.db.models import Q
import django_filters

from apps.files.models import StoredFile

FILE_TYPE_FILTERS = (
    ("all_types", "All Types"),
    ("pdf", "PDF"),
    ("image", "Image"),
    ("spreadsheet", "Spreadsheet"),
    ("document", "Document"),
    ("other", "Other"),
)


def normalize_key(value):
    return (value or "").strip().lower().replace(" ", "_").rstrip(".")


class StoredFileFilter(django_filters.FilterSet):
    file_id = django_filters.UUIDFilter(field_name="id")
    document_id = django_filters.UUIDFilter(field_name="id")
    id = django_filters.UUIDFilter(field_name="id")
    organization_id = django_filters.UUIDFilter(field_name="organization_id")
    name = django_filters.CharFilter(lookup_expr="icontains")
    file_type = django_filters.CharFilter(method="filter_file_type")
    type = django_filters.CharFilter(method="filter_file_type")
    folder = django_filters.CharFilter(lookup_expr="iexact")
    search = django_filters.CharFilter(method="filter_search")
    filter = django_filters.CharFilter(method="filter_type_alias")

    class Meta:
        model = StoredFile
        fields = (
            "file_id",
            "document_id",
            "id",
            "organization_id",
            "name",
            "file_type",
            "type",
            "folder",
            "search",
            "filter",
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
        return self._filter_by_type(queryset, value)

    def filter_type_alias(self, queryset, name, value):
        type_value = normalize_key(self.data.get("type") or self.data.get("file_type"))
        if type_value and type_value not in ("", "all", "all_types"):
            return queryset
        return self._filter_by_type(queryset, value)

    def _filter_by_type(self, queryset, value):
        key = normalize_key(value)
        if not key or key in ("all", "all_types"):
            return queryset
        allowed = {choice[0] for choice in FILE_TYPE_FILTERS}
        if key not in allowed:
            return queryset.none()
        if key == "all_types":
            return queryset
        return queryset.filter(file_type=key)
