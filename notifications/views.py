from rest_framework import generics, status, permissions
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from django_filters.rest_framework import DjangoFilterBackend
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi

from .models import Notification, NotificationPreference, PushNotificationDevice
from .serializers import (
    NotificationSerializer, NotificationPreferenceSerializer, PushDeviceSerializer
)


class NotificationListView(generics.ListAPIView):
    """
    List user notifications
    """
    serializer_class = NotificationSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['notification_type', 'is_read']
    
    def get_queryset(self):
        return Notification.objects.get_user_notifications(self.request.user)
    
    @swagger_auto_schema(
        operation_description="Get user notifications",
        manual_parameters=[
            openapi.Parameter(
                'unread_only', openapi.IN_QUERY,
                description="Show only unread notifications",
                type=openapi.TYPE_BOOLEAN
            ),
        ],
        responses={200: NotificationSerializer(many=True)}
    )
    def get(self, request, *args, **kwargs):
        unread_only = request.GET.get('unread_only', 'false').lower() == 'true'
        
        if unread_only:
            self.queryset = Notification.objects.get_user_notifications(
                request.user, 
                unread_only=True
            )
        
        return super().get(request, *args, **kwargs)


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
@swagger_auto_schema(
    operation_description="Mark notification as read",
    request_body=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        properties={
            'notification_id': openapi.Schema(type=openapi.TYPE_STRING),
        },
        required=['notification_id']
    ),
    responses={200: 'Notification marked as read'}
)
def mark_notification_read(request):
    """
    Mark specific notification as read
    """
    notification_id = request.data.get('notification_id')
    
    if not notification_id:
        return Response(
            {'error': 'notification_id is required'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    try:
        notification = Notification.objects.get(
            notification_id=notification_id,
            user=request.user
        )
        notification.mark_as_read()
        
        return Response({'message': 'Notification marked as read'})
        
    except Notification.DoesNotExist:
        return Response(
            {'error': 'Notification not found'},
            status=status.HTTP_404_NOT_FOUND
        )


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
@swagger_auto_schema(
    operation_description="Mark all notifications as read",
    responses={200: 'All notifications marked as read'}
)
def mark_all_notifications_read(request):
    """
    Mark all user notifications as read
    """
    count = Notification.objects.mark_all_read(request.user)
    
    return Response({
        'message': f'{count} notifications marked as read'
    })


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
@swagger_auto_schema(
    operation_description="Get unread notification count",
    responses={200: openapi.Response('Unread count', schema=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        properties={'unread_count': openapi.Schema(type=openapi.TYPE_INTEGER)}
    ))}
)
def unread_count(request):
    """
    Get count of unread notifications
    """
    count = Notification.objects.get_user_notifications(
        request.user,
        unread_only=True
    ).count()
    
    return Response({'unread_count': count})


class NotificationPreferencesView(generics.RetrieveUpdateAPIView):
    """
    Get and update notification preferences
    """
    serializer_class = NotificationPreferenceSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_object(self):
        preferences, created = NotificationPreference.objects.get_or_create(
            user=self.request.user
        )
        return preferences


class PushDeviceView(generics.CreateAPIView, generics.DestroyAPIView):
    """
    Register/unregister push notification device
    """
    serializer_class = PushDeviceSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        return PushNotificationDevice.objects.filter(user=self.request.user)
    
    @swagger_auto_schema(
        operation_description="Register push notification device",
        request_body=PushDeviceSerializer,
        responses={201: PushDeviceSerializer()}
    )
    def post(self, request, *args, **kwargs):
        return super().post(request, *args, **kwargs)
    
    def get_object(self):
        device_token = self.request.data.get('device_token')
        return get_object_or_404(
            PushNotificationDevice,
            device_token=device_token,
            user=self.request.user
        )
