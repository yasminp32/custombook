from django.urls import path

from apps.payment_terms.views import PaymentTermView

urlpatterns = [
    path("", PaymentTermView.as_view(), name="payment-terms"),
]
