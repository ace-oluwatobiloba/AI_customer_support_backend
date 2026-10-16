"""
Serializers for public customer registration and email verification.
"""

from django.contrib.auth.password_validation import validate_password

from rest_framework import serializers

from apps.accounts.models import User


class CustomerRegistrationSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(
        write_only=True,
        trim_whitespace=False,
        style={"input_type": "password"},
    )
    password_confirm = serializers.CharField(
        write_only=True,
        trim_whitespace=False,
        style={"input_type": "password"},
    )

    def validate_email(self, value):
        normalized_email = User.objects.normalize_email(value)

        if User.objects.filter(
            email__iexact=normalized_email
        ).exists():
            raise serializers.ValidationError(
                "An account with this email address already exists."
            )

        return normalized_email

    def validate(self, attrs):
        password = attrs["password"]
        password_confirm = attrs["password_confirm"]

        if password != password_confirm:
            raise serializers.ValidationError(
                {
                    "password_confirm": [
                        "The passwords do not match."
                    ]
                }
            )

        validate_password(password)

        return attrs


class EmailVerificationSerializer(serializers.Serializer):
    token = serializers.CharField(
        write_only=True,
        trim_whitespace=False,
    )