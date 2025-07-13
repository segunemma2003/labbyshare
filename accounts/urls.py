from django.urls import path
from . import views

app_name = 'accounts'

urlpatterns = [
    # Authentication endpoints
    path('register/', views.register, name='register'),
    path('login/', views.login, name='login'),
    path('logout/', views.logout, name='logout'),
    path('social-auth/', views.social_auth, name='social_auth'),
    
    # Password management
    path('forgot-password/', views.forgot_password, name='forgot_password'),
    path('reset-password/', views.reset_password, name='reset_password'),
    
    # Profile management
    path('profile/update/', views.ProfileUpdateView.as_view(), name='profile_update'),
    path('switch-region/', views.switch_region, name='switch_region'),
]