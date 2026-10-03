from django.urls import path

from apps.users.views import UserInviteView, UserRoleOptionsView, UserView

urlpatterns = [
    path("", UserView.as_view(), name="users"),
    path("roles/", UserRoleOptionsView.as_view(), name="user-roles"),
    path("invite/", UserInviteView.as_view(), name="user-invite"),
]
