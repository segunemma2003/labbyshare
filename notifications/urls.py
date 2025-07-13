from django.urls import path
from . import views

app_name = 'notifications'

urlpatterns = [
    # Notifications
    path('', views.NotificationListView.as_view(), name='notification_list'),
    path('unread-count/', views.unread_count, name='unread_count'),
    path('mark-read/', views.mark_notification_read, name='mark_read'),
    path('mark-all-read/', views.mark_all_notifications_read, name='mark_all_read'),
    
    # Preferences
    path('preferences/', views.NotificationPreferencesView.as_view(), name='notification_preferences'),
    
    # Push devices
    path('devices/', views.PushDeviceView.as_view(), name='push_device'),
]