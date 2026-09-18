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
    path("api/sales-orders/", include("apps.sales_orders.urls")),
    path("api/delivery-challans/", include("apps.delivery_challans.urls")),
    path("api/invoices/", include("apps.invoices.urls")),
    path("api/payments-received/", include("apps.payments_received.urls")),
    path("api/recurring-invoices/", include("apps.recurring_invoices.urls")),
    path("api/credit-notes/", include("apps.credit_notes.urls")),
    path("api/expenses/", include("apps.expenses.urls")),
    path("api/purchase-orders/", include("apps.purchase_orders.urls")),
    path("api/bills/", include("apps.bills.urls")),
    path("api/payments-made/", include("apps.payments_made.urls")),
    path("api/vendor-credits/", include("apps.vendor_credits.urls")),
    path("api/projects/", include("apps.projects.urls")),
    path("api/time-entries/", include("apps.time_entries.urls")),
    path("api/timer/", include("apps.timer.urls")),
    path("api/manual-journals/", include("apps.manual_journals.urls")),
    path("api/inbox/", include("apps.inbox.urls")),
    path("api/files/", include("apps.files.urls")),
    path("api/folders/", include("apps.folders.urls")),
    path("api/reports/", include("apps.reports.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
