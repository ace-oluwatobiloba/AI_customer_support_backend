"""
Authorization policies for support ticket operations.
"""

from rest_framework.permissions import BasePermission

from apps.accounts.models import User


class IsActiveAccount(BasePermission):
    """
    Allow authenticated users whose accounts are active
    and whose application status is ACTIVE.
    """

    message = "Your account is not permitted to perform this action."

    def has_permission(self, request, view):
        user = request.user

        return bool(
            user
            and user.is_authenticated
            and user.is_active
            and user.status == User.Status.ACTIVE
        )


class IsCustomer(IsActiveAccount):
    """Allow active customers only."""

    message = "Only active customers may perform this action."

    def has_permission(self, request, view):
        return (
            super().has_permission(request, view)
            and request.user.role == User.Role.CUSTOMER
        )


class IsAgent(IsActiveAccount):
    """Allow active agents only."""

    message = "Only active support agents may perform this action."

    def has_permission(self, request, view):
        return (
            super().has_permission(request, view)
            and request.user.role == User.Role.AGENT
        )


class IsAdmin(IsActiveAccount):
    """Allow active administrators only."""

    message = "Only active administrators may perform this action."

    def has_permission(self, request, view):
        return (
            super().has_permission(request, view)
            and request.user.role == User.Role.ADMIN
        )