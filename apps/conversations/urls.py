
from django.urls import path

from apps.conversations.views import (
    ConversationDetailView,
    ConversationListCreateView,
    ConversationMessagesView,
    StaffConversationListView,
    ConversationTakeoverView,
    HumanConversationReplyView,
)

urlpatterns = [
    path(
        "agent/",
        StaffConversationListView.as_view(),
        name="staff-conversation-list",
    ),
    path(
        "<uuid:conversation_id>/takeover/",
        ConversationTakeoverView.as_view(),
        name="conversation-takeover",
    ),
    path(
        "<uuid:conversation_id>/agent-replies/",
        HumanConversationReplyView.as_view(),
        name="conversation-human-reply",
    ),
    path(
        "",
        ConversationListCreateView.as_view(),
        name="conversation-list-create",
    ),
    path(
        "<uuid:conversation_id>/",
        ConversationDetailView.as_view(),
        name="conversation-detail",
    ),
    path(
        "<uuid:conversation_id>/messages/",
        ConversationMessagesView.as_view(),
        name="conversation-messages",
    ),
]
