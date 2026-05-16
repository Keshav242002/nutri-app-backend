from rest_framework.pagination import CursorPagination


class StandardCursorPagination(CursorPagination):
    """Single pagination class used by all list endpoints."""

    page_size = 20
    ordering = "-created_at"
    page_size_query_param = "page_size"
    max_page_size = 100
