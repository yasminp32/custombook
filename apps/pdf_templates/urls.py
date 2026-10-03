from django.urls import path

from apps.pdf_templates.views import (
    PdfTemplateBankDetailsView,
    PdfTemplateDetailView,
    PdfTemplateIndexView,
    PdfTemplateListView,
    PdfTemplateOptionsView,
    PdfTemplateSignatureView,
)

urlpatterns = [
    path("", PdfTemplateIndexView.as_view(), name="pdf-templates"),
    path("options/", PdfTemplateOptionsView.as_view(), name="pdf-template-options"),
    path("list/", PdfTemplateListView.as_view(), name="pdf-template-list"),
    path("detail/", PdfTemplateDetailView.as_view(), name="pdf-template-detail"),
    path("bank-details/", PdfTemplateBankDetailsView.as_view(), name="pdf-template-bank-details"),
    path("signature/", PdfTemplateSignatureView.as_view(), name="pdf-template-signature"),
]
