from django.urls import path
from . import views

app_name = 'bookings'

urlpatterns = [
    # Booking management
    path('', views.BookingListView.as_view(), name='booking_list'),
    path('create/', views.BookingCreateView.as_view(), name='booking_create'),
    path('<uuid:booking_id>/', views.BookingDetailView.as_view(), name='booking_detail'),
    path('<uuid:booking_id>/update/', views.BookingUpdateView.as_view(), name='booking_update'),
    path('<uuid:booking_id>/cancel/', views.cancel_booking, name='booking_cancel'),
    path('<uuid:booking_id>/confirm/', views.confirm_booking, name='booking_confirm'),
    
    # Reschedule
    path('<uuid:booking_id>/reschedule/', views.BookingRescheduleView.as_view(), name='booking_reschedule'),
    
    # Reviews
    path('<uuid:booking_id>/review/', views.ReviewCreateView.as_view(), name='review_create'),
    
    # Messages
    path('<uuid:booking_id>/messages/', views.BookingMessageView.as_view(), name='booking_messages'),
]