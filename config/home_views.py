"""
Homepage views for the AI Customer Support Backend.
"""

from django.shortcuts import render


def home(request):
    """Render the project landing page."""

    return render(request, "home.html")