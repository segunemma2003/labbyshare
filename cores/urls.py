from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

urlpatterns = [
    # Authentication
    path('auth/register/', views.register, name='register'),
    path('auth/social-auth/', views.social_auth, name='social_auth'),
    path('auth/login/', views.login, name='login'),
    path('auth/forgot-password/', views.forgot_password, name='forgot_password'),
    path('auth/reset-password/', views.verify_otp_and_reset_password, name='reset_password'),
    
    # Profile
    path('profile/update/', views.ProfileUpdateView.as_view(), name='profile_update'),
    path('regions/', views.RegionListView.as_view(), name='regions'),
    path('regions/switch/', views.switch_region, name='switch_region'),
    
    # Services
    path('categories/', views.CategoryListView.as_view(), name='categories'),
    path('services/', views.ServiceListView.as_view(), name='services'),
    path('professionals/', views.ProfessionalListView.as_view(), name='professionals'),
    
    # Bookings
    path('bookings/', views.BookingListView.as_view(), name='booking_list'),
    path('bookings/create/', views.BookingCreateView.as_view(), name='booking_create'),
]
