import uuid

from django.db import models

from apps.roles.models import Role


class RolePermission(models.Model):
    class PermissionLevel(models.TextChoices):
        NONE = "none", "None"
        VIEW = "view", "View"
        CREATE = "create", "Create"
        EDIT = "edit", "Edit"
        FULL = "full", "Full"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    role = models.ForeignKey(
        Role,
        on_delete=models.CASCADE,
        related_name="permissions",
    )
    module = models.CharField(max_length=100)
    permission_level = models.CharField(max_length=50, choices=PermissionLevel.choices)

    class Meta:
        db_table = "role_permissions"
        ordering = ["module"]
        constraints = [
            models.UniqueConstraint(
                fields=["role", "module"],
                name="unique_role_module_permission",
            ),
        ]

    def __str__(self):
        return f"{self.role.role_code}:{self.module}={self.permission_level}"
