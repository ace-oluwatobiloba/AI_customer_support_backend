# Generated for administrator-controlled employee invitations.
import uuid
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0003_alter_agentprofile_department_and_more"),
        ("audit", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="EmployeeInvitation",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("email", models.EmailField(db_index=True, max_length=254)),
                ("employee_code", models.CharField(max_length=50, unique=True)),
                ("department", models.CharField(blank=True, max_length=100, null=True)),
                ("specialization", models.CharField(blank=True, max_length=255, null=True)),
                ("token_hash", models.CharField(max_length=64, unique=True)),
                ("status", models.CharField(choices=[("PENDING", "Pending"), ("ACCEPTED", "Accepted"), ("REVOKED", "Revoked"), ("EXPIRED", "Expired")], default="PENDING", max_length=12)),
                ("expires_at", models.DateTimeField()),
                ("accepted_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("invited_by", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="employee_invitations_sent", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ["-created_at"]},
        ),
        migrations.AddConstraint(
            model_name="employeeinvitation",
            constraint=models.UniqueConstraint(condition=models.Q(("status", "PENDING")), fields=("email",), name="unique_pending_employee_invite_email"),
        ),
    ]
