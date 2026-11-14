"""
Session-authenticated staff portal and sign-in views.
"""
from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from apps.accounts.models import User


def _is_active_staff(user):
    return bool(
        user.is_authenticated
        and user.is_active
        and user.status == User.Status.ACTIVE
        and user.role in (User.Role.AGENT, User.Role.ADMIN)
    )


def staff_login(request):
    """Authenticate staff using Django's session authentication."""
    if _is_active_staff(request.user):
        return redirect("staff-portal")

    form = AuthenticationForm(request, data=request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.get_user()
        if not _is_active_staff(user):
            form.add_error(
                None,
                "This portal is available to active agents and administrators only.",
            )
        else:
            login(request, user)
            return redirect("staff-portal")

    return render(request, "staff_login.html", {"form": form})


@login_required(login_url="staff-login")
def staff_portal(request):
    """Show documentation links only to active agents and administrators."""
    if not _is_active_staff(request.user):
        return HttpResponseForbidden(
            "Active agent or administrator access is required."
        )

    return render(
        request,
        "staff_portal.html",
        {"is_admin": request.user.role == User.Role.ADMIN},
    )


@login_required(login_url="staff-login")
@require_POST
def staff_logout(request):
    """End the staff's browser session."""
    logout(request)
    messages.success(request, "You have been signed out.")
    return redirect("staff-login")
