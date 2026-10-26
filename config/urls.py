"""
Root URL configuration for the AI Customer Support Backend.
"""

from apps.accounts.admin import secure_admin_site
from django.urls import include, path
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularRedocView,
    SpectacularSwaggerView,
)

from config.home_views import home


urlpatterns = [
    # Project landing page.
    path("", home, name="home"),

    # Django administration.
    path(
    "admin/",
    secure_admin_site.urls,
    ),

    # OpenAPI schema and interactive documentation.
    path(
        "api/schema/",
        SpectacularAPIView.as_view(),
        name="schema",
    ),
    path(
        "api/docs/",
        SpectacularSwaggerView.as_view(url_name="schema"),
        name="swagger-ui",
    ),
    path(
        "api/redoc/",
        SpectacularRedocView.as_view(url_name="schema"),
        name="redoc",
    ),

    # Registration, email verification, and JWT authentication.
    path(
        "api/v1/auth/",
        include("apps.accounts.urls"),
    ),

    # Knowledge-base document API.
    path(
        "api/v1/knowledge/",
        include("apps.knowledge.urls"),
    ),

    # Support ticket API.
    path(
        "api/v1/support/",
        include("apps.support.urls"),
    ),
]