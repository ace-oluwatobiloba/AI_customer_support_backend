"""
Permissions for browser-facing staff API documentation.
"""
from rest_framework.permissions import BasePermission

from apps.accounts.models import User


class ActiveStaffOnly(BasePermission):
    """Allow active agent and administrator accounts to inspect API docs."""

    message = "Active agent or administrator access is required."

    def has_permission(self, request, view):
        user = request.user
        return bool(
            user
            and user.is_authenticated
            and user.is_active
            and user.status == User.Status.ACTIVE
            and user.role in (User.Role.AGENT, User.Role.ADMIN)
        )
