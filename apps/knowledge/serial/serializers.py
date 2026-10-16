"""
Serializers for knowledge-base upload requests.

These serializers validate request data before the upload service
stores documents or creates database records.
"""

from pathlib import Path

from rest_framework import serializers

from apps.knowledge.models import KnowledgeDocumentVersion


# Limit uploaded knowledge-base files to 10 MiB.
MAX_DOCUMENT_SIZE = 10 * 1024 * 1024


# Map supported file extensions to the model's corresponding choices.
SUPPORTED_FILE_TYPES = {
    ".pdf": KnowledgeDocumentVersion.FileType.PDF,
    ".docx": KnowledgeDocumentVersion.FileType.DOCX,
    ".txt": KnowledgeDocumentVersion.FileType.TXT,
}


class KnowledgeDocumentUploadSerializer(serializers.Serializer):
    """
    Validate requests that create a new logical document.
    """

    title = serializers.CharField(max_length=255)

    description = serializers.CharField(
        required=False,
        allow_blank=True,
        allow_null=True,
    )

    file = serializers.FileField(
        write_only=True,
        allow_empty_file=False,
    )

    def validate_title(self, value):
        # Reject titles that contain only whitespace.
        value = value.strip()

        if not value:
            raise serializers.ValidationError(
                "Document title cannot be empty."
            )

        return value

    def validate_file(self, uploaded_file):
        # Extract the filename without accepting client-supplied paths.
        filename = Path(uploaded_file.name).name
        extension = Path(filename).suffix.lower()

        # Reject unsupported formats before calling the upload service.
        file_type = SUPPORTED_FILE_TYPES.get(extension)

        if file_type is None:
            raise serializers.ValidationError(
                "Unsupported file format. Upload a PDF, DOCX, or TXT file."
            )

        # Enforce the application-level document size limit.
        if uploaded_file.size > MAX_DOCUMENT_SIZE:
            raise serializers.ValidationError(
                "File size must not exceed 10 MiB."
            )

        # Pass the validated model choice to the upload service.
        uploaded_file.validated_file_type = file_type

        return uploaded_file


class KnowledgeDocumentVersionUploadSerializer(serializers.Serializer):
    """
    Validate requests that add a version to an existing document.
    """

    file = serializers.FileField(
        write_only=True,
        allow_empty_file=False,
    )

    description = serializers.CharField(
        required=False,
        allow_blank=True,
        allow_null=True,
    )

    def validate_file(self, uploaded_file):
        # Validate the extension using the same rules as new documents.
        filename = Path(uploaded_file.name).name
        extension = Path(filename).suffix.lower()

        file_type = SUPPORTED_FILE_TYPES.get(extension)

        if file_type is None:
            raise serializers.ValidationError(
                "Unsupported file format. Upload a PDF, DOCX, or TXT file."
            )

        # Prevent oversized documents from reaching persistent storage.
        if uploaded_file.size > MAX_DOCUMENT_SIZE:
            raise serializers.ValidationError(
                "File size must not exceed 10 MiB."
            )

        # The service uses this validated value to populate the model.
        uploaded_file.validated_file_type = file_type

        return uploaded_file