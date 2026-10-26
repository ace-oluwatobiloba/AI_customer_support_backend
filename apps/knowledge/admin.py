from django.contrib import admin

from apps.accounts.admin import secure_admin_site
from apps.knowledge.models import (
    DocumentChunk,
    KnowledgeDocument,
    KnowledgeDocumentVersion,
)


class ReadOnlyKnowledgeAdmin(admin.ModelAdmin):
    """Provide inspection-only access to knowledge-base records."""

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(KnowledgeDocument, site=secure_admin_site)
class KnowledgeDocumentAdmin(ReadOnlyKnowledgeAdmin):
    list_display = (
        "title",
        "status",
        "created_by",
        "created_at",
        "updated_at",
    )

    list_filter = ("status", "created_at")

    search_fields = (
        "title",
        "description",
        "created_by__email",
    )

    ordering = ("-created_at",)


@admin.register(
    KnowledgeDocumentVersion,
    site=secure_admin_site,
)
class KnowledgeDocumentVersionAdmin(ReadOnlyKnowledgeAdmin):
    list_display = (
        "original_filename",
        "document",
        "version_number",
        "file_type",
        "processing_status",
        "file_size",
        "created_at",
    )

    list_filter = (
        "file_type",
        "processing_status",
        "created_at",
    )

    search_fields = (
        "original_filename",
        "document__title",
        "checksum",
    )

    ordering = ("-created_at",)


@admin.register(DocumentChunk, site=secure_admin_site)
class DocumentChunkAdmin(ReadOnlyKnowledgeAdmin):
    list_display = (
        "document_version",
        "chunk_index",
        "token_count",
        "created_at",
    )

    search_fields = (
        "content",
        "document_version__original_filename",
        "document_version__document__title",
    )

    ordering = (
        "document_version",
        "chunk_index",
    )

    readonly_fields = (
        "id",
        "document_version",
        "chunk_index",
        "content",
        "token_count",
        "metadata",
        "embedding",
        "created_at",
    )