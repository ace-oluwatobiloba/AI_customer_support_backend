"""
Permissions for knowledge-base API endpoints.
"""

from rest_framework.permissions import BasePermission

from apps.accounts.models import User


class IsKnowledgeBaseAdmin(BasePermission):
    """
    Allow only authenticated, active administrators to manage
    knowledge-base documents.
    """

    message = "Only administrators may manage knowledge-base documents."

    def has_permission(self, request, view):
        # Reject anonymous users and inactive accounts.
        user = request.user

        if not user or not user.is_authenticated or not user.is_active:
            return False

        # Enforce the application's explicit role-based access policy.
        return (
            user.status == User.Status.ACTIVE
            and user.role == User.Role.ADMIN
        )