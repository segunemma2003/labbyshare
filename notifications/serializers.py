from rest_framework import serializers
from .models import Notification, NotificationPreference, PushNotificationDevice


class NotificationSerializer(serializers.ModelSerializer):
    """
    Notification serializer
    """
    time_ago = serializers.SerializerMethodField()
    
    class Meta:
        model = Notification
        fields = [
            'notification_id', 'notification_type', 'title', 'message',
            'action_url', 'is_read', 'time_ago', 'created_at'
        ]
    
    def get_time_ago(self, obj):
        """Get human-readable time difference"""
        from django.utils.timesince import timesince
        return timesince(obj.created_at)


class NotificationPreferenceSerializer(serializers.ModelSerializer):
    """
    Notification preferences serializer
    """
    class Meta:
        model = NotificationPreference
        fields = [
            'booking_updates_push', 'payment_updates_push', 'reminders_push', 'promotions_push',
            'booking_updates_email', 'payment_updates_email', 'reminders_email', 'promotions_email',
            'booking_updates_sms', 'reminders_sms'
        ]


class PushDeviceSerializer(serializers.ModelSerializer):
    """
    Push notification device serializer
    """
    class Meta:
        model = PushNotificationDevice
        fields = ['device_token', 'platform', 'app_version', 'device_info']
    
    def create(self, validated_data):
        user = self.context['request'].user
        device_token = validated_data['device_token']
        
        # Update existing device or create new one
        device, created = PushNotificationDevice.objects.update_or_create(
            device_token=device_token,
            defaults={
                'user': user,
                'platform': validated_data['platform'],
                'app_version': validated_data.get('app_version', ''),
                'device_info': validated_data.get('device_info', {}),
                'is_active': True
            }
        )
        
        return device
