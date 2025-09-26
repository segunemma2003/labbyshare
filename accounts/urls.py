from django.urls import path
from . import views

app_name = 'accounts'

urlpatterns = [
    # Authentication endpoints
    path('register/', views.register, name='register'),
    path('login/', views.login, name='login'),
    path('logout/', views.logout, name='logout'),
    path('social-auth/', views.social_auth, name='social_auth'),
    
    # Email verification endpoints
    path('verify-email/', views.verify_email, name='verify_email'),
    path('resend-otp/', views.resend_otp, name='resend_otp'),
    
    # Password management
    path('forgot-password/', views.forgot_password, name='forgot_password'),
    path('verify-reset-otp/', views.verify_reset_otp, name='verify_reset_otp'),
    path('reset-password/', views.reset_password, name='reset_password'),
    path('test-email/', views.test_email, name='test_email'),  # Debug endpoint
    
    # Region management
    path('switch-region/', views.switch_region, name='switch_region'),
    
    # Profile management
    path('profile/update/', views.ProfileUpdateView.as_view(), name='profile_update'),
    path('profile/image/', views.ProfileImageUpdateView.as_view(), name='profile_image_update'),
]