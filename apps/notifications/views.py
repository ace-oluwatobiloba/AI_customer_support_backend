"""Authenticated API endpoints for the current user's notifications."""

from django.db.models import F
from django.shortcuts import get_object_or_404
from django.utils import timezone

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.notifications.models import Notification
from apps.notifications.pagination import NotificationPagination
from apps.notifications.serializers import NotificationSerializer
from apps.support.permissions import IsActiveAccount


class NotificationListView(APIView):
    """List notifications belonging exclusively to the authenticated user."""

    permission_classes = [IsAuthenticated, IsActiveAccount]

    def get(self, request):
        queryset = Notification.objects.filter(
            user=request.user
        ).order_by("-created_at", "-id")

        paginator = NotificationPagination()
        page = paginator.paginate_queryset(queryset, request, view=self)
        serializer = NotificationSerializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)


class NotificationDetailView(APIView):
    """Retrieve one notification owned by the authenticated user."""

    permission_classes = [IsAuthenticated, IsActiveAccount]

    def get(self, request, notification_id):
        notification = get_object_or_404(
            Notification,
            pk=notification_id,
            user=request.user,
        )
        return Response(NotificationSerializer(notification).data)


class NotificationUnreadCountView(APIView):
    """Return the number of unread notifications for the current user."""

    permission_classes = [IsAuthenticated, IsActiveAccount]

    def get(self, request):
        unread_count = Notification.objects.filter(
            user=request.user,
            read_at__isnull=True,
        ).count()
        return Response({"unread_count": unread_count})


class NotificationMarkReadView(APIView):
    """Mark one owned notification as read; repeated calls are harmless."""

    permission_classes = [IsAuthenticated, IsActiveAccount]

    def post(self, request, notification_id):
        notification = get_object_or_404(
            Notification,
            pk=notification_id,
            user=request.user,
        )

        if notification.read_at is None:
            notification.read_at = timezone.now()
            notification.save(update_fields=["read_at"])

        return Response(
            NotificationSerializer(notification).data,
            status=status.HTTP_200_OK,
        )


class NotificationMarkAllReadView(APIView):
    """Mark all unread notifications belonging to the current user as read."""

    permission_classes = [IsAuthenticated, IsActiveAccount]

    def post(self, request):
        now = timezone.now()
        updated_count = Notification.objects.filter(
            user=request.user,
            read_at__isnull=True,
        ).update(read_at=now)

        return Response(
            {
                "detail": "Unread notifications marked as read.",
                "updated_count": updated_count,
            },
            status=status.HTTP_200_OK,
        )
