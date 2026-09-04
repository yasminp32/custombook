from rest_framework.pagination import PageNumberPagination

from apps.accounts.responses import api_success


class OrganizationPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 100

    def get_paginated_response(self, data):
        return api_success(
            data={
                "count": self.page.paginator.count,
                "next": self.get_next_link(),
                "previous": self.get_previous_link(),
                "results": data,
            }
        )


def paginate_queryset(request, queryset_or_list, serializer=None, serializer_context=None):
    paginator = OrganizationPagination()
    page = paginator.paginate_queryset(queryset_or_list, request)
    if page is None:
        return None

    if serializer is not None:
        context = serializer_context or {}
        data = serializer(page, many=True, context=context).data
    else:
        data = page

    return paginator.get_paginated_response(data)
