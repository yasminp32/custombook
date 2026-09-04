import django_filters

from apps.permissions.models import RolePermission


class RolePermissionFilter(django_filters.FilterSet):
    permission_id = django_filters.UUIDFilter(field_name="id")
    id = django_filters.UUIDFilter(field_name="id")
    role_id = django_filters.UUIDFilter(field_name="role_id")
    module = django_filters.CharFilter(lookup_expr="icontains")
    permission_level = django_filters.ChoiceFilter(choices=RolePermission.PermissionLevel.choices)

    class Meta:
        model = RolePermission
        fields = ("permission_id", "id", "role_id", "module", "permission_level")
