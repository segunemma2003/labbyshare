from django.urls import path
from . import views
from .admin_operations import *

app_name = 'admin_panel'

urlpatterns = [
    # ===================== DASHBOARD & ANALYTICS =====================
    path('dashboard/', views.AdminDashboardView.as_view(), name='admin_dashboard'),
    
    # ===================== USER MANAGEMENT =====================
    path('users/', views.AdminUserListView.as_view(), name='admin_users'),
    path('users/<int:pk>/', views.AdminUserDetailView.as_view(), name='admin_user_detail'),
    path('users/reset-password/', reset_user_password, name='reset_user_password'),
    path('users/impersonate/', impersonate_user, name='impersonate_user'),
    
    # ===================== PROFESSIONAL MANAGEMENT =====================
    path('professionals/', views.AdminProfessionalListView.as_view(), name='admin_professionals'),
    path('professionals/<int:pk>/', views.AdminProfessionalDetailView.as_view(), name='admin_professional_detail'),
    path('professionals/verify/', views.verify_professional, name='verify_professional'),
    
    # ===================== CATEGORY MANAGEMENT =====================
    path('categories/', views.AdminCategoryListView.as_view(), name='admin_categories'),
    path('categories/<int:pk>/', views.AdminCategoryDetailView.as_view(), name='admin_category_detail'),
    
    # ===================== SERVICE MANAGEMENT =====================
    path('services/', views.AdminServiceListView.as_view(), name='admin_services'),
    path('services/<int:pk>/', views.AdminServiceDetailView.as_view(), name='admin_service_detail'),
    
    # ===================== REGIONAL PRICING MANAGEMENT =====================
    path('regional-pricing/', views.AdminRegionalPricingListView.as_view(), name='admin_regional_pricing'),
    path('regional-pricing/<int:pk>/', views.AdminRegionalPricingDetailView.as_view(), name='admin_regional_pricing_detail'),
    
    # ===================== ADDON MANAGEMENT =====================
    path('addons/', views.AdminAddOnListView.as_view(), name='admin_addons'),
    path('addons/<int:pk>/', views.AdminAddOnDetailView.as_view(), name='admin_addon_detail'),
    
    # ===================== BOOKING MANAGEMENT =====================
    path('bookings/', views.AdminBookingListView.as_view(), name='admin_bookings'),
    path('bookings/<uuid:booking_id>/', views.AdminBookingDetailView.as_view(), name='admin_booking_detail'),
    path('bookings/update-status/', views.update_booking_status, name='update_booking_status'),
    
    # ===================== PAYMENT MANAGEMENT =====================
    path('payments/', views.AdminPaymentListView.as_view(), name='admin_payments'),
    path('payments/<uuid:payment_id>/', views.AdminPaymentDetailView.as_view(), name='admin_payment_detail'),
    path('payments/update-status/', views.update_payment_status, name='update_payment_status'),
    
    # ===================== REGION MANAGEMENT =====================
    path('regions/', views.AdminRegionListView.as_view(), name='admin_regions'),
    path('regions/<int:pk>/', views.AdminRegionDetailView.as_view(), name='admin_region_detail'),
    path('regional-settings/', views.AdminRegionalSettingsView.as_view(), name='admin_regional_settings'),
    
    # ===================== REVIEW MODERATION =====================
    path('reviews/', views.AdminReviewListView.as_view(), name='admin_reviews'),
    path('reviews/moderate/', views.moderate_review, name='moderate_review'),
    
    # ===================== NOTIFICATION MANAGEMENT =====================
    path('notifications/', views.AdminNotificationListView.as_view(), name='admin_notifications'),
    path('notifications/broadcast/', views.send_broadcast_notification, name='send_broadcast_notification'),
    path('maintenance-notification/', send_maintenance_notification, name='maintenance_notification'),
    
    # ===================== SYSTEM MANAGEMENT =====================
    path('alerts/', views.SystemAlertsView.as_view(), name='system_alerts'),
    path('alerts/resolve/', views.resolve_alert, name='resolve_alert'),
    path('tickets/', views.SupportTicketsView.as_view(), name='support_tickets'),
    path('tickets/assign/', views.assign_ticket, name='assign_ticket'),
    
    # ===================== BULK OPERATIONS =====================
    path('bulk-operations/', views.bulk_operations, name='bulk_operations'),
    
    # ===================== ANALYTICS & REPORTS =====================
    path('analytics/', views.analytics_data, name='analytics_data'),
    path('statistics/users/', get_user_statistics, name='user_statistics'),
    path('statistics/bookings/', get_booking_statistics, name='booking_statistics'),
    path('statistics/revenue/', get_revenue_statistics, name='revenue_statistics'),
    path('export/', export_data, name='export_data'),
]
