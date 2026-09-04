import django_filters

from apps.roles.models import Role


class RoleFilter(django_filters.FilterSet):
    id = django_filters.UUIDFilter(field_name="id")
    role_name = django_filters.CharFilter(lookup_expr="icontains")
    role_code = django_filters.CharFilter(lookup_expr="icontains")
    is_system_role = django_filters.BooleanFilter()

    class Meta:
        model = Role
        fields = ("id", "role_name", "role_code", "is_system_role")
