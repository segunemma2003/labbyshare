from django.contrib import admin
from .models import Payment, SavedPaymentMethod, PaymentWebhookEvent

class PaymentAdmin(admin.ModelAdmin):
    list_display = ('payment_id', 'booking', 'customer', 'amount', 'currency', 'payment_type', 'status', 'created_at')
    search_fields = ('payment_id', 'booking__booking_id', 'customer__email')
    list_filter = ('status', 'payment_type', 'currency', 'created_at')
    date_hierarchy = 'created_at'

class SavedPaymentMethodAdmin(admin.ModelAdmin):
    list_display = ('id', 'customer', 'stripe_payment_method_id', 'card_brand', 'card_last_four', 'is_default', 'created_at')
    search_fields = ('customer__email', 'stripe_payment_method_id', 'card_last_four')
    list_filter = ('is_default', 'card_brand', 'created_at')

class PaymentWebhookEventAdmin(admin.ModelAdmin):
    list_display = ('id', 'stripe_event_id', 'event_type', 'processed', 'created_at')
    search_fields = ('stripe_event_id', 'event_type')
    list_filter = ('event_type', 'processed', 'created_at')

admin.site.register(Payment, PaymentAdmin)
admin.site.register(SavedPaymentMethod, SavedPaymentMethodAdmin)
admin.site.register(PaymentWebhookEvent, PaymentWebhookEventAdmin)
