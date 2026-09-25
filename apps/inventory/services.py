from decimal import Decimal

from django.db import transaction
from django.db.models import Sum
from django.db.models.functions import Coalesce

from apps.inventory.models import InventoryAdjustment, InventoryAdjustmentActivity

ZERO = Decimal("0.00")
ATTACHABLE_TYPE = "inventory_adjustment"


def log_activity(
    adjustment,
    message,
    user=None,
    activity_type=InventoryAdjustmentActivity.ActivityType.HISTORY,
):
    return InventoryAdjustmentActivity.objects.create(
        adjustment=adjustment,
        activity_type=activity_type,
        message=message,
        created_by=user,
    )


def display_name_for_user(user, organization=None):
    if user:
        full_name = (user.get_full_name() or "").strip()
        if full_name:
            return full_name
        first = (getattr(user, "first_name", "") or "").strip()
        last = (getattr(user, "last_name", "") or "").strip()
        combined = f"{first} {last}".strip()
        if combined:
            return combined
        if user.email:
            return user.email
    if organization and organization.name:
        return organization.name
    return ""


def refresh_totals(adjustment):
    totals = adjustment.lines.aggregate(
        quantity=Coalesce(Sum("quantity_adjusted"), ZERO),
        value=Coalesce(Sum("value"), ZERO),
    )
    adjustment.quantity_change = totals["quantity"] or ZERO
    adjustment.adjustment_value = totals["value"] or ZERO
    adjustment.save(update_fields=["quantity_change", "adjustment_value", "updated_at"])
    return adjustment


def apply_stock(adjustment):
    if adjustment.stock_applied:
        return adjustment
    if adjustment.status != InventoryAdjustment.Status.COMPLETED:
        return adjustment
    if adjustment.adjustment_type != InventoryAdjustment.AdjustmentType.QUANTITY:
        adjustment.stock_applied = True
        adjustment.save(update_fields=["stock_applied", "updated_at"])
        return adjustment

    with transaction.atomic():
        for line in adjustment.lines.select_related("item"):
            item = line.item
            if not item or not item.track_inventory:
                continue
            current = item.opening_stock or ZERO
            item.opening_stock = current + (line.quantity_adjusted or ZERO)
            item.save(update_fields=["opening_stock", "updated_at"])
        adjustment.stock_applied = True
        adjustment.save(update_fields=["stock_applied", "updated_at"])
    return adjustment
