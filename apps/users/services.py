import logging

from django.conf import settings
from django.core.mail import send_mail

from apps.organizations.services import get_current_organization
from apps.roles.models import Role

logger = logging.getLogger(__name__)

SYSTEM_ROLES = (
    {
        "role_code": "admin",
        "role_name": "Admin",
        "description": "Full access to all modules, transactions, settings, and data.",
    },
    {
        "role_code": "staff_assigned_customers",
        "role_name": "Staff (Assigned Customers Only)",
        "description": (
            "Access to all modules, transactions and data of assigned customers "
            "and all vendors except banking, reports, settings and accountant."
        ),
    },
    {
        "role_code": "staff_all_customers",
        "role_name": "Staff (All Customers)",
        "description": (
            "Access to all modules, transactions and data of all customers and "
            "vendors except banking, reports, settings and accountant."
        ),
    },
    {
        "role_code": "time_tracking",
        "role_name": "Time Tracking Only",
        "description": "Access only to time tracking and project modules.",
    },
)

DEFAULT_INVITE_ROLE = "staff_assigned_customers"


def resolve_user_organization(auth_user, organization_id=None):
    organizations = auth_user.owned_organizations
    if organization_id:
        return organizations.filter(pk=organization_id).first()
    return get_current_organization(auth_user)


def ensure_system_roles(organization):
    roles = []
    for row in SYSTEM_ROLES:
        role, _created = Role.objects.get_or_create(
            organization=organization,
            role_code=row["role_code"],
            defaults={
                "role_name": row["role_name"],
                "description": row["description"],
                "is_system_role": True,
            },
        )
        changed = []
        if role.role_name != row["role_name"]:
            role.role_name = row["role_name"]
            changed.append("role_name")
        if role.description != row["description"]:
            role.description = row["description"]
            changed.append("description")
        if not role.is_system_role:
            role.is_system_role = True
            changed.append("is_system_role")
        if changed:
            role.save(update_fields=changed + ["updated_at"])
        roles.append(role)
    return roles


def role_option(role):
    return {
        "role_id": role.id,
        "role_code": role.role_code,
        "role_name": role.role_name,
        "description": role.description,
    }


def find_system_role(organization, role_id=None, role_code=None):
    ensure_system_roles(organization)
    queryset = Role.objects.filter(organization=organization, is_system_role=True)
    if role_id:
        return queryset.filter(pk=role_id).first()
    code = (role_code or "").strip().lower().replace(" ", "_").replace("-", "_")
    aliases = {
        "admin": "admin",
        "staff_assigned_customers_only": "staff_assigned_customers",
        "staff_assigned_customers": "staff_assigned_customers",
        "staff_all_customers": "staff_all_customers",
        "time_tracking_only": "time_tracking",
        "time_tracking": "time_tracking",
    }
    mapped = aliases.get(code, code)
    role = queryset.filter(role_code=mapped).first()
    if role:
        return role
    return queryset.filter(role_name__iexact=(role_code or "").strip()).first()


def send_invite_email(user, organization, invited_by):
    role_name = user.role.role_name if user.role else "team member"
    subject = f"Invitation to {organization.name}"
    body = "\n".join(
        [
            f"Hello {user.full_name or user.email},",
            "",
            f"You have been invited to {organization.name} as {role_name}.",
            f"Invited by: {invited_by.email}",
            "",
            "Sign in with this email address after your account is ready.",
        ]
    )
    send_mail(
        subject=subject,
        message=body,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[user.email],
        fail_silently=False,
    )
