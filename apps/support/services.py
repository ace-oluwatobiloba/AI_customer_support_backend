"""
Business services for support ticket management.
"""

import secrets
from datetime import datetime

from django.db import IntegrityError, transaction

from apps.support.models import Ticket


def generate_ticket_number():
    """
    Generate a ticket number.

    Example: TKT-20261015-A1B2C3D4

    The random suffix reduces collisions. The database unique
    constraint remains the final guarantee of uniqueness.
    """
    date_part = datetime.now().strftime("%Y%m%d")
    random_part = secrets.token_hex(4).upper()

    return f"TKT-{date_part}-{random_part}"


@transaction.atomic
def create_customer_ticket(*, customer, title, description, category):
    """
    Create a ticket for an authenticated customer.

    Customer identity and creation source are assigned by the server.
    """
    for attempt in range(3):
        ticket_number = generate_ticket_number()

        try:
            with transaction.atomic():
                return Ticket.objects.create(
                    ticket_number=ticket_number,
                    customer=customer,
                    created_by=customer,
                    created_source=Ticket.CreatedSource.CUSTOMER,
                    title=title,
                    description=description,
                    category=category,
                    priority=Ticket.Priority.MEDIUM,
                    status=Ticket.Status.OPEN,
                )
        except IntegrityError:
            if attempt == 2:
                raise

    raise RuntimeError("Unable to generate a unique ticket number.")