from django.urls import path

from apps.support.views import (
    TicketDetailView,
    TicketListCreateView,
    TicketAssignmentListCreateView,
    TicketEscalationListCreateView
)

from apps.support.views import TicketAssignmentListCreateView

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
    path(
        "tickets/<uuid:ticket_id>/assignments/",
        TicketAssignmentListCreateView.as_view(),
        name="ticket-assignment-list-create",
    ),
    path(
    "tickets/<uuid:ticket_id>/escalations/",
    TicketEscalationListCreateView.as_view(),
    name="ticket-escalation-list-create",
),
]