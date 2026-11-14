"""
Public customer portal homepage.
"""
from django.conf import settings
from django.shortcuts import render


def home(request):
    """Render the public, organization-branded customer support portal."""
    context = {
        "organization_name": settings.ORGANIZATION_NAME,
        "organization_tagline": settings.ORGANIZATION_TAGLINE,
        "support_email": settings.ORGANIZATION_SUPPORT_EMAIL,
        "support_phone": settings.ORGANIZATION_SUPPORT_PHONE,
    }
    return render(request, "home.html", context)
