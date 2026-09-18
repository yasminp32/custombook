from django.db.models import Q
import django_filters

from apps.folders.models import Folder


class FolderFilter(django_filters.FilterSet):
    folder_id = django_filters.UUIDFilter(field_name="id")
    id = django_filters.UUIDFilter(field_name="id")
    organization_id = django_filters.UUIDFilter(field_name="organization_id")
    name = django_filters.CharFilter(lookup_expr="icontains")
    search = django_filters.CharFilter(method="filter_search")

    class Meta:
        model = Folder
        fields = (
            "folder_id",
            "id",
            "organization_id",
            "name",
            "search",
        )

    def filter_search(self, queryset, name, value):
        value = (value or "").strip()
        if not value:
            return queryset
        return queryset.filter(Q(name__icontains=value))
