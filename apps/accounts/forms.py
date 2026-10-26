from django import forms
from django.contrib.auth.forms import AuthenticationForm

from apps.accounts.models import User


class EligibleAdminAuthenticationForm(AuthenticationForm):
    """
    Permit admin login only for active, email-verified accounts.
    """

    def confirm_login_allowed(self, user):
        super().confirm_login_allowed(user)

        if user.status != User.Status.ACTIVE:
            raise forms.ValidationError(
                "This account is not permitted to access the admin.",
                code="account_not_eligible",
            )

        if not user.email_verified:
            raise forms.ValidationError(
                "Email verification is required to access the admin.",
                code="email_not_verified",
            )