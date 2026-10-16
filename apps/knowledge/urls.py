"""
URL routes for the knowledge-base API.
"""

from django.urls import path

from apps.knowledge.views import (
    KnowledgeDocumentUploadView,
    KnowledgeDocumentVersionUploadView,
)


app_name = "knowledge"


urlpatterns = [
    # POST: create a new document and its first version.
    path(
        "documents/",
        KnowledgeDocumentUploadView.as_view(),
        name="document-upload",
    ),

    # POST: add a version to a specific existing document.
    path(
        "documents/<uuid:document_id>/versions/",
        KnowledgeDocumentVersionUploadView.as_view(),
        name="document-version-upload",
    ),
]