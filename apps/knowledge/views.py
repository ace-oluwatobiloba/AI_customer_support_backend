"""
REST API views for knowledge-base document uploads.

The views handle HTTP concerns:
- Request validation
- Administrator authorization
- Calling the upload service
- Returning consistent API responses

File storage and database operations remain in upload_service.py.
"""

from django.shortcuts import get_object_or_404

from rest_framework import status
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.knowledge.models import KnowledgeDocument
from apps.knowledge.serial.permissions import IsKnowledgeBaseAdmin
from apps.knowledge.serial.serializers import (
    KnowledgeDocumentUploadSerializer,
    KnowledgeDocumentVersionUploadSerializer,
)
from apps.knowledge.services.upload_service import (
    DocumentUploadError,
    create_knowledge_document,
    create_knowledge_document_version,
)


class KnowledgeDocumentUploadView(APIView):
    """
    Create a new knowledge-base document and its first version.
    """

    # Require JWT authentication and administrator-level access.
    permission_classes = [
        IsAuthenticated,
        IsKnowledgeBaseAdmin,
    ]

    # Accept file uploads submitted as multipart form data.
    parser_classes = [
        MultiPartParser,
        FormParser,
    ]

    def post(self, request):
        # Validate the incoming title, description, and file.
        serializer = KnowledgeDocumentUploadSerializer(
            data=request.data
        )
        serializer.is_valid(raise_exception=True)

        validated_data = serializer.validated_data

        try:
            # Create a new logical document and version 1.
            document, version = create_knowledge_document(
                title=validated_data["title"],
                description=validated_data.get("description"),
                uploaded_file=validated_data["file"],
                uploaded_by=request.user,
            )

        except DocumentUploadError:
            # Avoid exposing internal storage or database details.
            return Response(
                {
                    "detail": (
                        "The knowledge-base document could not be uploaded."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Return the public metadata, not the internal storage key.
        return Response(
            {
                "message": "Knowledge-base document created successfully.",
                "document": {
                    "id": str(document.id),
                    "title": document.title,
                    "description": document.description,
                    "status": document.status,
                },
                "version": {
                    "id": str(version.id),
                    "version_number": version.version_number,
                    "original_filename": version.original_filename,
                    "file_type": version.file_type,
                    "file_size": version.file_size,
                    "checksum": version.checksum,
                    "processing_status": version.processing_status,
                    "created_at": version.created_at,
                },
            },
            status=status.HTTP_201_CREATED,
        )


class KnowledgeDocumentVersionUploadView(APIView):
    """
    Add a new version to an explicitly identified document.
    """

    # Prevent customers and agents from managing the knowledge base.
    permission_classes = [
        IsAuthenticated,
        IsKnowledgeBaseAdmin,
    ]

    # Support uploaded files and ordinary form fields.
    parser_classes = [
        MultiPartParser,
        FormParser,
    ]

    def post(self, request, document_id):
        # Resolve the document ID before invoking the upload service.
        # This gives API clients a proper 404 for nonexistent documents.
        document = get_object_or_404(
            KnowledgeDocument,
            pk=document_id,
        )

        # Reject archived documents before accepting the upload.
        if document.status != KnowledgeDocument.Status.ACTIVE:
            return Response(
                {
                    "detail": (
                        "Cannot add a version to an archived document."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Validate the file and any optional description update.
        serializer = KnowledgeDocumentVersionUploadSerializer(
            data=request.data
        )
        serializer.is_valid(raise_exception=True)

        validated_data = serializer.validated_data

        try:
            # The service calculates the next version number and persists
            # the file and its database record.
            document, version = create_knowledge_document_version(
                document_id=document.id,
                uploaded_file=validated_data["file"],
                uploaded_by=request.user,
                description=validated_data.get("description"),
            )

        except DocumentUploadError:
            # Return a controlled response instead of exposing internals.
            return Response(
                {
                    "detail": (
                        "The new document version could not be uploaded."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response(
            {
                "message": "Document version uploaded successfully.",
                "document": {
                    "id": str(document.id),
                    "title": document.title,
                    "description": document.description,
                    "status": document.status,
                },
                "version": {
                    "id": str(version.id),
                    "version_number": version.version_number,
                    "original_filename": version.original_filename,
                    "file_type": version.file_type,
                    "file_size": version.file_size,
                    "checksum": version.checksum,
                    "processing_status": version.processing_status,
                    "created_at": version.created_at,
                },
            },
            status=status.HTTP_201_CREATED,
        )