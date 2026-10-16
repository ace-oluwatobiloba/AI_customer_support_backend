from django.urls import path

from apps.support.views import (
    TicketDetailView,
    TicketListCreateView,
)

app_name = "support"

urlpatterns = [
    path(
        "tickets/",
        TicketListCreateView.as_view(),
        name="ticket-list-create",
    ),
    path(
        "tickets/<uuid:ticket_id>/",
        TicketDetailView.as_view(),
        name="ticket-detail",
    ),
]