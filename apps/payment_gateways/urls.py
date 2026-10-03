from django.urls import path

from apps.payment_gateways.views import (
    PaymentGatewayDetailView,
    PaymentGatewayIndexView,
    PaymentGatewayListView,
    PaymentGatewaySetupView,
)

urlpatterns = [
    path("", PaymentGatewayIndexView.as_view(), name="payment-gateways"),
    path("list/", PaymentGatewayListView.as_view(), name="payment-gateway-list"),
    path("detail/", PaymentGatewayDetailView.as_view(), name="payment-gateway-detail"),
    path("setup/", PaymentGatewaySetupView.as_view(), name="payment-gateway-setup"),
]
