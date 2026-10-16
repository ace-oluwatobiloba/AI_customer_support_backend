from django.test import TestCase
from django.contrib.auth import get_user_model

from .models import CustomerProfile, AgentProfile


User = get_user_model()


class UserManagerTest(TestCase):
    """Tests for UserManager behavior."""

    def test_create_user(self):
        user = User.objects.create_user(
            email="customer@example.com",
            password="CustomerPass123!",
        )

        self.assertEqual(user.email, "customer@example.com")
        self.assertTrue(user.check_password("CustomerPass123!"))
        self.assertNotEqual(user.password, "CustomerPass123!")

        self.assertEqual(
            user.role,
            User.Role.CUSTOMER
        )

        self.assertEqual(
            user.status,
            User.Status.ACTIVE
        )

    def test_create_user_requires_email(self):
        with self.assertRaises(ValueError):
            User.objects.create_user(
                email="",
                password="CustomerPass123!",
            )

    def test_create_user_without_password(self):
        user = User.objects.create_user(
            email="nopassword@example.com"
        )

        self.assertFalse(
            user.has_usable_password()
        )

    def test_create_superuser(self):
        admin = User.objects.create_superuser(
            email="admin@example.com",
            password="AdminPass123!",
        )

        self.assertEqual(
            admin.role,
            User.Role.ADMIN
        )

        self.assertTrue(admin.is_staff)
        self.assertTrue(admin.is_superuser)

        self.assertTrue(
            admin.check_password("AdminPass123!")
        )


class UserModelTest(TestCase):
    """Tests for the custom User model."""

    def test_user_has_uuid_primary_key(self):
        user = User.objects.create_user(
            email="uuid@example.com",
            password="Password123!",
        )

        self.assertIsNotNone(user.id)

    def test_email_is_unique(self):
        User.objects.create_user(
            email="unique@example.com",
            password="Password123!",
        )

        with self.assertRaises(Exception):
            User.objects.create_user(
                email="unique@example.com",
                password="AnotherPass123!",
            )

    def test_email_verification_defaults(self):
        user = User.objects.create_user(
            email="verify@example.com",
            password="Password123!",
        )

        self.assertFalse(user.email_verified)
        self.assertIsNone(user.email_verified_at)

    def test_user_timestamps_are_created(self):
        user = User.objects.create_user(
            email="timestamps@example.com",
            password="Password123!",
        )

        self.assertIsNotNone(user.created_at)
        self.assertIsNotNone(user.updated_at)

    def test_phone_is_optional(self):
        user = User.objects.create_user(
            email="phone@example.com",
            password="Password123!",
        )

        self.assertIsNone(user.phone)


class CustomerProfileTest(TestCase):
    """Tests for CustomerProfile and its relationship with User."""

    def setUp(self):
        self.customer = User.objects.create_user(
            email="customer@example.com",
            password="CustomerPass123!",
            role=User.Role.CUSTOMER,
        )

    def test_create_customer_profile(self):
        profile = CustomerProfile.objects.create(
            user=self.customer,
            first_name="John",
            last_name="Doe",
            address="Lagos, Nigeria",
        )

        self.assertEqual(
            profile.user,
            self.customer
        )

        self.assertEqual(
            profile.first_name,
            "John"
        )

        self.assertEqual(
            profile.last_name,
            "Doe"
        )

    def test_customer_profile_reverse_relationship(self):
        profile = CustomerProfile.objects.create(
            user=self.customer,
            first_name="John",
            last_name="Doe",
        )

        self.assertEqual(
            self.customer.customer_profile,
            profile
        )

    def test_customer_profile_cascades_when_user_deleted(self):
        profile = CustomerProfile.objects.create(
            user=self.customer,
            first_name="John",
            last_name="Doe",
        )

        profile_id = profile.id

        self.customer.delete()

        self.assertFalse(
            CustomerProfile.objects.filter(
                id=profile_id
            ).exists()
        )


class AgentProfileTest(TestCase):
    """Tests for AgentProfile and its relationship with User."""

    def setUp(self):
        self.agent = User.objects.create_user(
            email="agent@example.com",
            password="AgentPass123!",
            role=User.Role.AGENT,
        )

    def test_create_agent_profile(self):
        profile = AgentProfile.objects.create(
            user=self.agent,
            employee_code="AGT-001",
            department="Technical Support",
            specialization="Backend Engineering",
        )

        self.assertEqual(
            profile.user,
            self.agent
        )

        self.assertEqual(
            profile.employee_code,
            "AGT-001"
        )

    def test_agent_profile_reverse_relationship(self):
        profile = AgentProfile.objects.create(
            user=self.agent,
            employee_code="AGT-002",
        )

        self.assertEqual(
            self.agent.agent_profile,
            profile
        )

    def test_employee_code_is_unique(self):
        AgentProfile.objects.create(
            user=self.agent,
            employee_code="AGT-003",
        )

        another_agent = User.objects.create_user(
            email="agent2@example.com",
            password="AgentPass123!",
            role=User.Role.AGENT,
        )

        with self.assertRaises(Exception):
            AgentProfile.objects.create(
                user=another_agent,
                employee_code="AGT-003",
            )

    def test_agent_profile_cascades_when_user_deleted(self):
        profile = AgentProfile.objects.create(
            user=self.agent,
            employee_code="AGT-004",
        )

        profile_id = profile.id

        self.agent.delete()

        self.assertFalse(
            AgentProfile.objects.filter(
                id=profile_id
            ).exists()
        )


class AccountsIntegrationTest(TestCase):
    """
    Integration test covering User + CustomerProfile +
    AgentProfile together.
    """

    def test_complete_accounts_setup(self):
        customer = User.objects.create_user(
            email="customer@support.com",
            password="CustomerPass123!",
            role=User.Role.CUSTOMER,
        )

        agent = User.objects.create_user(
            email="agent@support.com",
            password="AgentPass123!",
            role=User.Role.AGENT,
        )

        admin = User.objects.create_superuser(
            email="admin@support.com",
            password="AdminPass123!",
        )

        customer_profile = CustomerProfile.objects.create(
            user=customer,
            first_name="John",
            last_name="Customer",
            address="Lagos, Nigeria",
        )

        agent_profile = AgentProfile.objects.create(
            user=agent,
            employee_code="AGT-100",
            department="Customer Support",
            specialization="Technical Support",
        )

        # User relationships
        self.assertEqual(
            customer.customer_profile,
            customer_profile
        )

        self.assertEqual(
            agent.agent_profile,
            agent_profile
        )

        # Roles
        self.assertEqual(
            customer.role,
            User.Role.CUSTOMER
        )

        self.assertEqual(
            agent.role,
            User.Role.AGENT
        )

        self.assertEqual(
            admin.role,
            User.Role.ADMIN
        )

        # Authentication
        self.assertTrue(
            customer.check_password("CustomerPass123!")
        )

        self.assertTrue(
            agent.check_password("AgentPass123!")
        )

        self.assertTrue(
            admin.check_password("AdminPass123!")
        )

        # Admin permissions
        self.assertTrue(admin.is_staff)
        self.assertTrue(admin.is_superuser)

        # Default account status
        self.assertEqual(
            customer.status,
            User.Status.ACTIVE
        )

        self.assertEqual(
            agent.status,
            User.Status.ACTIVE
        )

        self.assertEqual(
            admin.status,
            User.Status.ACTIVE
        )