from django.urls import path
from . import views

app_name = 'payments'

urlpatterns = [
    # Payment management
    path('', views.PaymentListView.as_view(), name='payment_list'),
    path('<uuid:payment_id>/', views.PaymentDetailView.as_view(), name='payment_detail'),
    path('summary/', views.payment_summary, name='payment_summary'),
    
    # Enhanced payment processing
    path('create-intent/', views.create_payment_intent, name='create_payment_intent'),
    path('confirm/', views.confirm_payment, name='confirm_payment'),
    path('remaining/', views.process_remaining_payment, name='process_remaining_payment'),
    path('refund/', views.request_refund, name='request_refund'),
    
    # Booking-specific payment status
    path('booking/<uuid:booking_id>/status/', views.booking_payment_status, name='booking_payment_status'),
    
    # Saved payment methods
    path('methods/', views.SavedPaymentMethodsView.as_view(), name='payment_methods'),
    path('methods/<int:pk>/', views.PaymentMethodDetailView.as_view(), name='payment_method_detail'),
    
    # Stripe webhook
    path('webhook/', views.stripe_webhook, name='stripe_webhook'),
]