"""Integration tests for centralized audit recording in business services."""

from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.accounts.services.employee_onboarding import (
    accept_employee_invitation,
    invite_employee,
)
from apps.audit.models import AuditLog
from apps.conversations.models import Conversation
from apps.conversations.services.handover_service import (
    create_human_reply,
    take_over_conversation,
)
from apps.support.models import Ticket, TicketAssignment
from apps.support.services import (
    assign_ticket,
    auto_assign_ticket,
    create_customer_ticket,
    escalate_ticket,
)


User = get_user_model()


class AuditBusinessIntegrationTests(TestCase):
    def setUp(self):
        self.customer = User.objects.create_user(
            email="audit-customer@example.com",
            password="Customer-Test-Password-123!",
            role=User.Role.CUSTOMER,
            status=User.Status.ACTIVE,
            is_active=True,
            email_verified=True,
        )
        self.agent = User.objects.create_user(
            email="audit-agent@example.com",
            password="Agent-Test-Password-123!",
            role=User.Role.AGENT,
            status=User.Status.ACTIVE,
            is_active=True,
            email_verified=True,
        )
        self.second_agent = User.objects.create_user(
            email="audit-agent-two@example.com",
            password="Agent-Test-Password-123!",
            role=User.Role.AGENT,
            status=User.Status.ACTIVE,
            is_active=True,
            email_verified=True,
        )
        self.admin = User.objects.create_user(
            email="audit-admin@example.com",
            password="Admin-Test-Password-123!",
            role=User.Role.ADMIN,
            status=User.Status.ACTIVE,
            is_active=True,
            is_staff=True,
            email_verified=True,
        )

    def _create_ticket(self, ticket_number="TKT-AUDIT-0001", status=Ticket.Status.OPEN):
        return Ticket.objects.create(
            ticket_number=ticket_number,
            customer=self.customer,
            created_by=self.customer,
            created_source=Ticket.CreatedSource.CUSTOMER,
            title="Audit integration test",
            description="Ticket used to verify audit integration.",
            category=Ticket.Category.OTHER,
            status=status,
        )

    def test_customer_ticket_creation_records_audit_event(self):
        ticket = create_customer_ticket(
            customer=self.customer,
            title="Cannot sign in",
            description="Login fails.",
            category=Ticket.Category.ACCOUNT,
        )

        event = AuditLog.objects.get(
            action="TICKET_CREATED",
            entity_id=ticket.pk,
        )
        self.assertEqual(event.actor, self.customer)
        self.assertEqual(event.entity_type, "Ticket")
        self.assertEqual(event.metadata["ticket_number"], ticket.ticket_number)
        self.assertEqual(
            event.metadata["created_source"],
            Ticket.CreatedSource.CUSTOMER,
        )

    def test_manual_ticket_assignment_records_audit_event(self):
        ticket = self._create_ticket()
        assignment = assign_ticket(
            ticket_id=ticket.pk,
            agent_id=self.agent.pk,
            assigned_by=self.admin,
            reason="Specialist assignment",
        )

        event = AuditLog.objects.get(
            action="TICKET_ASSIGNED",
            entity_id=ticket.pk,
        )
        self.assertEqual(event.actor, self.admin)
        self.assertEqual(event.metadata["assignment_id"], str(assignment.pk))
        self.assertEqual(event.metadata["agent_id"], str(self.agent.pk))
        self.assertIsNone(event.metadata["previous_agent_id"])

    def test_automated_ticket_assignment_records_system_audit_event(self):
        ticket = self._create_ticket()
        assignment = auto_assign_ticket(ticket_id=ticket.pk)

        event = AuditLog.objects.get(
            action="TICKET_AUTO_ASSIGNED",
            entity_id=ticket.pk,
        )
        self.assertIsNone(event.actor)
        self.assertEqual(event.metadata["assignment_id"], str(assignment.pk))
        self.assertEqual(event.metadata["agent_id"], str(assignment.agent_id))
        self.assertEqual(event.metadata["assignment_method"], "LEAST_LOADED")

    def test_ticket_escalation_records_audit_event(self):
        ticket = self._create_ticket()
        escalation = escalate_ticket(
            ticket_id=ticket.pk,
            escalated_by=self.agent,
            reason="Requires specialist investigation.",
            trigger="AGENT_REQUEST",
        )

        event = AuditLog.objects.get(
            action="TICKET_ESCALATED",
            entity_id=ticket.pk,
        )
        self.assertEqual(event.actor, self.agent)
        self.assertEqual(event.metadata["escalation_id"], str(escalation.pk))
        self.assertEqual(event.metadata["trigger"], "AGENT_REQUEST")

    def test_conversation_takeover_and_human_reply_are_audited(self):
        ticket = self._create_ticket(
            ticket_number="TKT-AUDIT-0002",
            status=Ticket.Status.ESCALATED,
        )
        conversation = Conversation.objects.create(
            customer=self.customer,
            ticket=ticket,
            title="Audit handover test",
            status=Conversation.Status.ESCALATED,
        )
        TicketAssignment.objects.create(
            ticket=ticket,
            agent=self.agent,
            assigned_by=self.admin,
            reason="Audit integration test assignment",
        )

        take_over_conversation(
            conversation_id=conversation.pk,
            actor=self.agent,
        )
        reply = create_human_reply(
            conversation_id=conversation.pk,
            actor=self.agent,
            content="I am reviewing your request.",
        )

        takeover_event = AuditLog.objects.get(
            action="CONVERSATION_TAKEN_OVER",
            entity_id=conversation.pk,
        )
        reply_event = AuditLog.objects.get(
            action="CONVERSATION_HUMAN_REPLY",
            entity_id=conversation.pk,
        )
        self.assertEqual(takeover_event.actor, self.agent)
        self.assertEqual(reply_event.actor, self.agent)
        self.assertEqual(reply_event.metadata["message_id"], str(reply.pk))

    @patch(
        "apps.accounts.services.employee_onboarding.send_mail",
        return_value=1,
    )
    def test_employee_invitation_and_acceptance_use_central_audit_service(
        self,
        mocked_send_mail,
    ):
        with patch(
            "apps.accounts.services.employee_onboarding.secrets.token_urlsafe",
            return_value="audit-test-invitation-token",
        ):
            invitation = invite_employee(
                invited_by=self.admin,
                email="new-audit-agent@example.com",
                employee_code="AUDIT-TEST-AGENT-001",
                department="Customer Support",
                specialization="Accounts",
            )

        invited_event = AuditLog.objects.get(
            action="EMPLOYEE_INVITED",
            entity_id=invitation.pk,
        )
        self.assertEqual(invited_event.actor, self.admin)
        self.assertEqual(invited_event.entity_type, "EmployeeInvitation")

        new_agent = accept_employee_invitation(
            token="audit-test-invitation-token",
            password="Agent-Onboarding-Test-Password-923!",
            password_confirm="Agent-Onboarding-Test-Password-923!",
        )
        accepted_event = AuditLog.objects.get(
            action="EMPLOYEE_INVITATION_ACCEPTED",
            entity_id=invitation.pk,
        )
        self.assertEqual(accepted_event.actor, new_agent)
        self.assertEqual(new_agent.role, User.Role.AGENT)
        self.assertTrue(new_agent.email_verified)
        mocked_send_mail.assert_called_once()
