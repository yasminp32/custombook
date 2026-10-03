from django.urls import path

from apps.sender_emails.views import (
    SenderEmailDeliveryView,
    SenderEmailFormView,
    SenderEmailIndexView,
    SenderEmailListView,
    SenderEmailPrimaryView,
)

urlpatterns = [
    path("", SenderEmailIndexView.as_view(), name="sender-emails"),
    path("form/", SenderEmailFormView.as_view(), name="sender-email-form"),
    path("senders/", SenderEmailListView.as_view(), name="sender-email-senders"),
    path("primary/", SenderEmailPrimaryView.as_view(), name="sender-email-primary"),
    path("delivery-method/", SenderEmailDeliveryView.as_view(), name="sender-email-delivery"),
]
