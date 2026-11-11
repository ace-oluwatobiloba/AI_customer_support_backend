"""Serializers for administrator employee onboarding."""

from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers

from apps.accounts.models import EmployeeInvitation, User


class EmployeeInvitationCreateSerializer(serializers.Serializer):
    email = serializers.EmailField()
    employee_code = serializers.CharField(max_length=50)
    department = serializers.CharField(max_length=100, required=False, allow_blank=True)
    specialization = serializers.CharField(max_length=255, required=False, allow_blank=True)


class EmployeeInvitationAcceptSerializer(serializers.Serializer):
    token = serializers.CharField(write_only=True, trim_whitespace=False)
    password = serializers.CharField(write_only=True, trim_whitespace=False)
    password_confirm = serializers.CharField(write_only=True, trim_whitespace=False)

    def validate(self, attrs):
        if attrs["password"] != attrs["password_confirm"]:
            raise serializers.ValidationError({"password_confirm": "Passwords do not match."})
        validate_password(attrs["password"])
        return attrs


class AgentManagementSerializer(serializers.ModelSerializer):
    employee_code = serializers.SerializerMethodField()
    department = serializers.SerializerMethodField()
    specialization = serializers.SerializerMethodField()

    def get_employee_code(self, obj):
        return getattr(getattr(obj, "agent_profile", None), "employee_code", None)

    def get_department(self, obj):
        return getattr(getattr(obj, "agent_profile", None), "department", None)

    def get_specialization(self, obj):
        return getattr(getattr(obj, "agent_profile", None), "specialization", None)

    class Meta:
        model = User
        fields = ("id", "email", "status", "is_active", "employee_code", "department", "specialization")
        read_only_fields = fields


class AgentStatusSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=[User.Status.ACTIVE, User.Status.INACTIVE, User.Status.SUSPENDED])
