from django.db import IntegrityError
from django.shortcuts import get_object_or_404
from rest_framework import serializers
from rest_framework import status
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from apps.accounts.responses import api_error, api_success
from apps.items.filters import ITEM_FILTERS, ItemFilter
from apps.items.models import Item
from apps.items.serializers import ItemSerializer, ItemWriteSerializer
from apps.organizations.models import Organization
from apps.organizations.pagination import paginate_queryset

SORT_FIELDS = {
    "name": "name",
    "sales_price": "selling_price",
    "selling_price": "selling_price",
    "purchase_price": "cost_price",
    "cost_price": "cost_price",
    "created_at": "created_at",
}


def get_user_organizations(user):
    return Organization.objects.filter(owner=user)


def get_item_queryset(user):
    return Item.objects.filter(organization__owner=user).select_related(
        "organization",
        "preferred_vendor",
        "created_by",
    )


def resolve_organization(user, organization_id=None):
    organizations = get_user_organizations(user)
    if organization_id:
        return get_object_or_404(organizations, pk=organization_id)
    return organizations.order_by("created_at").first()


def get_item_id_param(request):
    item_id = request.query_params.get("item_id") or request.query_params.get("id")
    if not item_id:
        return None, api_error(
            "item_id query parameter is required.",
            status_code=status.HTTP_400_BAD_REQUEST,
        )
    return item_id, None


def apply_sorting(queryset, query_params):
    sort_by = (query_params.get("sort_by") or "name").strip().lower()
    sort_order = (query_params.get("sort_order") or "asc").strip().lower()
    field = SORT_FIELDS.get(sort_by)
    if not field:
        return None, api_error(
            "Invalid sort_by.",
            errors={"sort_by": f"Allowed values: {', '.join(SORT_FIELDS.keys())}."},
        )
    if sort_order not in ("asc", "desc"):
        return None, api_error(
            "Invalid sort_order.",
            errors={"sort_order": "Allowed values: asc, desc."},
        )
    prefix = "-" if sort_order == "desc" else ""
    return queryset.order_by(f"{prefix}{field}", "name"), None


class ItemView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [JSONParser, MultiPartParser, FormParser]

    def get(self, request):
        item_id = request.query_params.get("item_id") or request.query_params.get("id")
        if item_id:
            item = get_object_or_404(get_item_queryset(request.user), pk=item_id)
            return api_success(
                data=ItemSerializer(item, context={"request": request}).data
            )

        queryset = get_item_queryset(request.user)
        params = request.query_params.copy()
        if "filter" not in params and "status" not in params:
            params["filter"] = "active_items"

        item_filter = ItemFilter(params, queryset=queryset)
        if not item_filter.is_valid():
            return api_error("Invalid filter parameters.", errors=item_filter.errors)

        queryset, error_response = apply_sorting(item_filter.qs, request.query_params)
        if error_response:
            return error_response

        response = paginate_queryset(
            request,
            queryset,
            serializer=ItemSerializer,
            serializer_context={"request": request},
        )
        if response is not None:
            return response

        return api_success(data=[])

    def post(self, request):
        organization = resolve_organization(
            request.user,
            request.data.get("organization_id"),
        )
        if not organization:
            return api_error(
                "Organization not found. Complete organization setup before creating items.",
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        serializer = ItemWriteSerializer(data=request.data)
        if not serializer.is_valid():
            return api_error("Validation error", errors=serializer.errors)

        created_by = serializer.validate_created_by_reference(request.user)
        try:
            item = serializer.save(organization=organization, created_by=created_by)
        except IntegrityError:
            return api_error(
                "An item with this SKU already exists in the organization.",
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        except serializers.ValidationError as exc:
            return api_error("Validation error", errors=exc.detail)
        return api_success(
            data=ItemSerializer(item, context={"request": request}).data,
            message="Item created successfully.",
            status_code=status.HTTP_201_CREATED,
        )

    def put(self, request):
        item_id, error_response = get_item_id_param(request)
        if error_response:
            return error_response

        item = get_object_or_404(get_item_queryset(request.user), pk=item_id)
        serializer = ItemWriteSerializer(item, data=request.data)
        if not serializer.is_valid():
            return api_error("Validation error", errors=serializer.errors)

        try:
            item = serializer.save()
        except IntegrityError:
            return api_error(
                "An item with this SKU already exists in the organization.",
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        except serializers.ValidationError as exc:
            return api_error("Validation error", errors=exc.detail)
        return api_success(
            data=ItemSerializer(item, context={"request": request}).data,
            message="Item updated successfully.",
        )

    def patch(self, request):
        item_id, error_response = get_item_id_param(request)
        if error_response:
            return error_response

        item = get_object_or_404(get_item_queryset(request.user), pk=item_id)
        serializer = ItemWriteSerializer(item, data=request.data, partial=True)
        if not serializer.is_valid():
            return api_error("Validation error", errors=serializer.errors)

        try:
            item = serializer.save()
        except IntegrityError:
            return api_error(
                "An item with this SKU already exists in the organization.",
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        except serializers.ValidationError as exc:
            return api_error("Validation error", errors=exc.detail)
        return api_success(
            data=ItemSerializer(item, context={"request": request}).data,
            message="Item updated successfully.",
        )

    def delete(self, request):
        item_id, error_response = get_item_id_param(request)
        if error_response:
            return error_response

        item = get_object_or_404(get_item_queryset(request.user), pk=item_id)
        item.delete()
        return api_success(message="Item deleted successfully.")


class ItemOptionsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return api_success(
            data={
                "item_types": [
                    {"key": key, "label": label} for key, label in Item.ItemType.choices
                ],
                "statuses": [
                    {"key": key, "label": label} for key, label in Item.Status.choices
                ],
                "valuation_methods": [
                    {"key": key, "label": label}
                    for key, label in Item.ValuationMethod.choices
                ],
                "filters": [
                    {"key": key, "label": label} for key, label in ITEM_FILTERS
                ],
                "sort_fields": [
                    {"key": "name", "label": "Name"},
                    {"key": "sales_price", "label": "Sales Price"},
                    {"key": "purchase_price", "label": "Purchase Price"},
                ],
                "sales_accounts": ["Sales"],
                "purchase_accounts": ["Cost of Goods Sold"],
                "inventory_accounts": ["Inventory Asset"],
                "units": ["pcs", "kg", "box", "ltr", "hrs"],
            }
        )
