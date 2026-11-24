from django.contrib import admin, messages
from django.db import transaction
from django.shortcuts import redirect, render
from django.urls import path, reverse

from apps.accounts.admin import secure_admin_site
from apps.knowledge.admin_forms import (
    KnowledgeDocumentAdminUploadForm,
    KnowledgeDocumentVersionAdminUploadForm,
)
from apps.knowledge.models import (
    DocumentChunk,
    KnowledgeDocument,
    KnowledgeDocumentVersion,
)
from apps.knowledge.serial.serializers import (
    KnowledgeDocumentUploadSerializer,
    KnowledgeDocumentVersionUploadSerializer,
)
from apps.knowledge.services.ingestion_dispatch import (
    dispatch_document_ingestion,
)
from apps.knowledge.services.upload_service import (
    DocumentUploadError,
    create_knowledge_document,
    create_knowledge_document_version,
)


class ReadOnlyKnowledgeAdmin(admin.ModelAdmin):
    """Inspection-only model access; uploads use dedicated admin views."""

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def has_view_permission(self, request, obj=None):
        return True


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
    search_fields = ("title", "description", "created_by__email")
    ordering = ("-created_at",)
    change_list_template = "admin/knowledge/knowledgedocument/change_list.html"

    def get_urls(self):
        custom_urls = [
            path(
                "upload/",
                self.admin_site.admin_view(self.upload_document_view),
                name="knowledge_knowledgedocument_upload",
            ),
        ]
        return custom_urls + super().get_urls()

    def upload_document_view(self, request):
        opts = self.model._meta
        context = {
            **self.admin_site.each_context(request),
            "opts": opts,
            "title": "Upload knowledge-base document",
            "changelist_url": reverse("secure_admin:knowledge_knowledgedocument_changelist"),
            "form": KnowledgeDocumentAdminUploadForm(
                request.POST or None,
                request.FILES or None,
            ),
        }

        if request.method == "POST":
            form = context["form"]
            if form.is_valid():
                serializer = KnowledgeDocumentUploadSerializer(
                    data={
                        "title": form.cleaned_data["title"],
                        "description": form.cleaned_data["description"],
                        "file": form.cleaned_data["file"],
                    }
                )
                if serializer.is_valid():
                    data = serializer.validated_data
                    try:
                        document, version = create_knowledge_document(
                            title=data["title"],
                            description=data.get("description"),
                            uploaded_file=data["file"],
                            uploaded_by=request.user,
                        )
                    except DocumentUploadError:
                        messages.error(
                            request,
                            "The document could not be uploaded. "
                            "Check the file and try again.",
                        )
                    else:
                        transaction.on_commit(
                            lambda version_id=version.pk:
                                dispatch_document_ingestion(version_id)
                        )
                        messages.success(
                            request,
                            f'"{document.title}" was uploaded. '
                            "Document ingestion has been queued.",
                        )
                        return redirect(
                            reverse(
                                "secure_admin:knowledge_knowledgedocument_changelist"
                            )
                        )
                else:
                    for field, errors in serializer.errors.items():
                        for error in errors:
                            form.add_error(
                                "file" if field == "file" else field,
                                error,
                            )

        context["form"] = form if request.method == "POST" else context["form"]
        return render(
            request,
            "admin/knowledge/upload_form.html",
            context,
        )


@admin.register(KnowledgeDocumentVersion, site=secure_admin_site)
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
    list_filter = ("file_type", "processing_status", "created_at")
    search_fields = ("original_filename", "document__title", "checksum")
    ordering = ("-created_at",)
    change_list_template = (
        "admin/knowledge/knowledgedocumentversion/change_list.html"
    )

    def get_urls(self):
        custom_urls = [
            path(
                "upload-version/",
                self.admin_site.admin_view(self.upload_version_view),
                name="knowledge_knowledgedocumentversion_upload",
            ),
        ]
        return custom_urls + super().get_urls()

    def upload_version_view(self, request):
        opts = self.model._meta
        form = KnowledgeDocumentVersionAdminUploadForm(
            request.POST or None,
            request.FILES or None,
        )
        context = {
            **self.admin_site.each_context(request),
            "opts": opts,
            "title": "Upload a document version",
            "changelist_url": reverse("secure_admin:knowledge_knowledgedocumentversion_changelist"),
            "form": form,
        }

        if request.method == "POST" and form.is_valid():
            serializer = KnowledgeDocumentVersionUploadSerializer(
                data={
                    "description": form.cleaned_data["description"],
                    "file": form.cleaned_data["file"],
                }
            )
            if serializer.is_valid():
                data = serializer.validated_data
                try:
                    document, version = create_knowledge_document_version(
                        document_id=form.cleaned_data["document"].pk,
                        uploaded_file=data["file"],
                        uploaded_by=request.user,
                        description=data.get("description") or None,
                    )
                except DocumentUploadError as exc:
                    form.add_error(None, str(exc))
                else:
                    transaction.on_commit(
                        lambda version_id=version.pk:
                            dispatch_document_ingestion(version_id)
                    )
                    messages.success(
                        request,
                        f'Version {version.version_number} for '
                        f'"{document.title}" was uploaded. '
                        "Document ingestion has been queued.",
                    )
                    return redirect(
                        reverse(
                            "secure_admin:knowledge_knowledgedocumentversion_changelist"
                        )
                    )
            else:
                for field, errors in serializer.errors.items():
                    for error in errors:
                        form.add_error(
                            "file" if field == "file" else field,
                            error,
                        )

        return render(
            request,
            "admin/knowledge/upload_form.html",
            context,
        )


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
    ordering = ("document_version", "chunk_index")
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
