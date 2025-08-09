from django.urls import path
from . import views

app_name = 'professionals'

urlpatterns = [
    # Professional listings and search
    path('', views.ProfessionalListView.as_view(), name='professional_list'),
    path('search/', views.search_professionals, name='professional_search'),
    path('top-rated/', views.top_rated_professionals, name='top_rated'),
    path('<int:id>/', views.ProfessionalDetailView.as_view(), name='professional_detail'),
    
    # Professional registration and profile
    path('register/', views.ProfessionalRegistrationView.as_view(), name='professional_register'),
    path('profile/', views.ProfessionalProfileView.as_view(), name='professional_profile'),
    path('dashboard/', views.professional_dashboard, name='professional_dashboard'),
    
    # Availability management
    path('availability/', views.AvailabilityManagementView.as_view(), name='availability_list'),
    path('availability/<int:pk>/', views.AvailabilityUpdateView.as_view(), name='availability_detail'),
    path('unavailability/', views.UnavailabilityView.as_view(), name='unavailability_list'),
    
    # Booking availability
    path('available-slots/', views.get_available_slots, name='available_slots'),
    
    # Document upload
    path('documents/', views.DocumentUploadView.as_view(), name='document_upload'),
    
    # Test endpoint for debugging
    path('test-upload/', views.test_file_upload, name='test_file_upload'),
    
    # Admin views
    path('admin/<int:id>/', views.AdminProfessionalDetailView.as_view(), name='admin_professional_detail'),
]