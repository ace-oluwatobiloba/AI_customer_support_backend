"""
URL configuration for account registration and authentication.
"""

from django.urls import path

from apps.accounts.views import (
    CustomerRegistrationView,
    EmailVerificationView,
    EligibleAccountTokenRefreshView,
    VerifiedEmailTokenObtainPairView,
    EmployeeInvitationView, EmployeeInvitationAcceptView, AgentListView, AgentStatusView,
)


app_name = "accounts"


urlpatterns = [
    path("employees/invitations/", EmployeeInvitationView.as_view(), name="employee-invitations"),
    path("employees/invitations/accept/", EmployeeInvitationAcceptView.as_view(), name="accept-employee-invitation"),
    path("employees/agents/", AgentListView.as_view(), name="agent-list"),
    path("employees/agents/<uuid:user_id>/status/", AgentStatusView.as_view(), name="agent-status"),
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