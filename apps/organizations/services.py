def get_current_organization(user):
    current_id = getattr(user, "current_organization_id", None)
    if current_id:
        organization = user.owned_organizations.filter(pk=current_id).first()
        if organization:
            return organization
    return user.owned_organizations.order_by("created_at").first()


def set_current_organization(user, organization):
    if user.current_organization_id == organization.id:
        return organization
    user.current_organization = organization
    user.save(update_fields=["current_organization"])
    return organization
