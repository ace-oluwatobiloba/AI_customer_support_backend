from django.contrib import admin
from django.contrib.admin.forms import AdminAuthenticationForm
from django.core.exceptions import ValidationError

from apps.accounts.models import User


class SecureAdminAuthenticationForm(AdminAuthenticationForm):
    """
    Restrict Django Admin login to eligible administrator accounts.
    """

    def confirm_login_allowed(self, user):
        super().confirm_login_allowed(user)

        if (
            user.status != User.Status.ACTIVE
            or not user.email_verified
            or user.role != User.Role.ADMIN
        ):
            raise ValidationError(
                "Your account is not permitted to access the admin site.",
                code="admin_access_denied",
            )


class SecureAdminSite(admin.AdminSite):
    """
    Require eligible administrator accounts for every Admin request.
    """

    site_header = "AI Customer Support Administration"
    site_title = "Customer Support Admin"
    index_title = "Administration Dashboard"
    login_form = SecureAdminAuthenticationForm

    def has_permission(self, request):
        user = request.user

        return bool(
            super().has_permission(request)
            and user.status == User.Status.ACTIVE
            and user.email_verified
            and user.role == User.Role.ADMIN
        )


secure_admin_site = SecureAdminSite(name="secure_admin")