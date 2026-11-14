"""
Root URL configuration for the AI Customer Support Backend.
"""

from apps.accounts.admin import secure_admin_site
from django.urls import include, path
from rest_framework.authentication import SessionAuthentication
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularRedocView,
    SpectacularSwaggerView,
)

from config.home_views import home
from config.permissions import ActiveStaffOnly
from config.staff_views import staff_login, staff_logout, staff_portal

from apps.conversations.views import chat_page


# Browser documentation uses Django sessions (not the API's JWT-only defaults).
DOC_AUTHENTICATION = [SessionAuthentication]
DOC_PERMISSION = [ActiveStaffOnly]


urlpatterns = [
    # Project landing page.
    path("", home, name="home"),

    # Staff-only browser portal.
    path("staff/login/", staff_login, name="staff-login"),
    path("staff/", staff_portal, name="staff-portal"),
    path("staff/logout/", staff_logout, name="staff-logout"),

    # Django administration.
    path(
        "admin/",
        secure_admin_site.urls,
    ),

    # OpenAPI schema and interactive documentation.
    path(
        "api/schema/",
        SpectacularAPIView.as_view(
            authentication_classes=DOC_AUTHENTICATION,
            permission_classes=DOC_PERMISSION,
        ),
        name="schema",
    ),
    path(
        "api/docs/",
        SpectacularSwaggerView.as_view(
            url_name="schema",
            authentication_classes=DOC_AUTHENTICATION,
            permission_classes=DOC_PERMISSION,
        ),
        name="swagger-ui",
    ),
    path(
        "api/redoc/",
        SpectacularRedocView.as_view(
            url_name="schema",
            authentication_classes=DOC_AUTHENTICATION,
            permission_classes=DOC_PERMISSION,
        ),
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

    # User notification API.
    path(
        "api/v1/notifications/",
        include("apps.notifications.urls"),
    ),

    # Administrator-only audit API.
    path(
        "api/v1/audit/",
        include("apps.audit.urls"),
    ),

    # Support ticket API.
    path(
        "api/v1/support/",
        include("apps.support.urls"),
    ),

    # Conversation and messaging API.
    path(
        "api/v1/conversations/",
        include("apps.conversations.urls"),
    ),

    # Chat page for customer support.
    path("chat/", chat_page, name="chat-page"),
]
