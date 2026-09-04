from rest_framework_simplejwt.tokens import RefreshToken


class OrganizationRefreshToken(RefreshToken):
    @classmethod
    def for_user(cls, user, organization_id=None):
        token = super().for_user(user)
        if organization_id is not None:
            token["organization_id"] = str(organization_id)
        return token

    @property
    def access_token(self):
        access = super().access_token
        if "organization_id" in self:
            access["organization_id"] = self["organization_id"]
        return access
