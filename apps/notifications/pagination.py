"""Pagination policy for the notification feed."""

from rest_framework.pagination import PageNumberPagination


class NotificationPagination(PageNumberPagination):
    """Keep notification feed responses bounded and predictable."""

    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 100
