"""Forms used by the secure Django Admin knowledge-base upload views."""

from django import forms

from apps.knowledge.models import KnowledgeDocument


class KnowledgeDocumentAdminUploadForm(forms.Form):
    title = forms.CharField(max_length=255)
    description = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={"rows": 3}),
    )
    file = forms.FileField(
        help_text="Accepted formats: PDF, DOCX or TXT. Maximum size: 10 MiB."
    )


class KnowledgeDocumentVersionAdminUploadForm(forms.Form):
    document = forms.ModelChoiceField(
        queryset=KnowledgeDocument.objects.none(),
        help_text="Choose the active knowledge-base document to update.",
    )
    description = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={"rows": 3}),
        help_text="Leave blank to keep the existing description unchanged.",
    )
    file = forms.FileField(
        help_text="Accepted formats: PDF, DOCX or TXT. Maximum size: 10 MiB."
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["document"].queryset = KnowledgeDocument.objects.filter(
            status=KnowledgeDocument.Status.ACTIVE
        ).order_by("title")
