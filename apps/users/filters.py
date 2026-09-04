import django_filters

from apps.users.models import User


class UserFilter(django_filters.FilterSet):
    id = django_filters.UUIDFilter(field_name="id")
    email = django_filters.CharFilter(lookup_expr="icontains")
    full_name = django_filters.CharFilter(lookup_expr="icontains")
    status = django_filters.ChoiceFilter(choices=User.Status.choices)

    class Meta:
        model = User
        fields = ("id", "email", "full_name", "status")
