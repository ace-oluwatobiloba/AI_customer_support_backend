"""
Root URL configuration for the AI Customer Support Backend.
"""

from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),

    # Registration, email verification, and JWT authentication.
    path(
        "api/v1/auth/",
        include("apps.accounts.urls"),
    ),

    # Knowledge-base document upload API.
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