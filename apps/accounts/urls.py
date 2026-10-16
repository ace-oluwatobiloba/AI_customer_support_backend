"""
URL configuration for account registration and authentication.
"""

from django.urls import path

from apps.accounts.views import (
    CustomerRegistrationView,
    EmailVerificationView,
    EligibleAccountTokenRefreshView,
    VerifiedEmailTokenObtainPairView,
)


app_name = "accounts"


urlpatterns = [
    path(
        "register/",
        CustomerRegistrationView.as_view(),
        name="register",
    ),
    path(
        "verify-email/",
        EmailVerificationView.as_view(),
        name="verify-email",
    ),
    path(
        "token/",
        VerifiedEmailTokenObtainPairView.as_view(),
        name="token-obtain-pair",
    ),
    path(
        "token/refresh/",
        EligibleAccountTokenRefreshView.as_view(),
        name="token-refresh",
    ),
]