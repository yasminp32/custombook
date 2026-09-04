from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/accounts/", include("apps.accounts.urls")),
    path("api/dashboard/", include("apps.dashboard.urls")),
    path("api/organizations/", include("apps.organizations.urls")),
    path("api/branches/", include("apps.branches.urls")),
    path("api/users/", include("apps.users.urls")),
    path("api/roles/", include("apps.roles.urls")),
    path("api/permissions/", include("apps.permissions.urls")),
    path("api/customers/", include("apps.customers.urls")),
    path("api/payment-terms/", include("apps.payment_terms.urls")),
    path("api/attachments/", include("apps.attachments.urls")),
    path("api/audit-logs/", include("apps.audit_logs.urls")),
    path("api/vendors/", include("apps.vendors.urls")),
    path("api/items/", include("apps.items.urls")),
    path("api/inventory/", include("apps.inventory.urls")),
    path("api/banking/", include("apps.banking.urls")),
    path("api/quotes/", include("apps.quotes.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
