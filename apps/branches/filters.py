import django_filters

from apps.branches.models import Branch


class BranchFilter(django_filters.FilterSet):
    id = django_filters.UUIDFilter(field_name="id")
    organization_id = django_filters.UUIDFilter(field_name="organization_id")
    status = django_filters.ChoiceFilter(choices=Branch.Status.choices)
    is_primary = django_filters.BooleanFilter()
    name = django_filters.CharFilter(lookup_expr="icontains")

    class Meta:
        model = Branch
        fields = ("id", "organization_id", "status", "is_primary", "name")
