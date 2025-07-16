from django.contrib import admin
from .models import Booking, BookingAddOn, Review, BookingReschedule, BookingMessage, BookingStatusHistory

class BookingAdmin(admin.ModelAdmin):
    list_display = ('booking_id', 'customer', 'professional', 'service', 'scheduled_date', 'status', 'payment_status', 'total_amount')
    search_fields = ('booking_id', 'customer__email', 'professional__user__email', 'service__name')
    list_filter = ('status', 'payment_status', 'scheduled_date', 'service')
    date_hierarchy = 'scheduled_date'
    fieldsets = (
        (None, {
            'fields': ('booking_id', 'customer', 'professional', 'service', 'region', 'scheduled_date', 'scheduled_time', 'status', 'payment_status')
        }),
        ('Amounts', {
            'fields': ('base_amount', 'addon_amount', 'discount_amount', 'tax_amount', 'total_amount', 'deposit_amount', 'deposit_percentage')
        }),
        ('Details', {
            'fields': ('address_line1', 'address_line2', 'city', 'postal_code', 'location_notes', 'customer_notes', 'professional_notes')
        }),
    )
    readonly_fields = ('booking_id',)

class ReviewAdmin(admin.ModelAdmin):
    list_display = ('id', 'booking', 'customer', 'professional', 'overall_rating', 'created_at')
    search_fields = ('booking__booking_id', 'customer__email', 'professional__user__email')
    list_filter = ('overall_rating', 'created_at')

class BookingRescheduleAdmin(admin.ModelAdmin):
    list_display = ('id', 'booking', 'requested_by', 'requested_date', 'requested_time', 'status', 'created_at')
    search_fields = ('booking__booking_id', 'requested_by__email')
    list_filter = ('status', 'created_at')

class BookingMessageAdmin(admin.ModelAdmin):
    list_display = ('id', 'booking', 'sender', 'message', 'is_read', 'created_at')
    search_fields = ('booking__booking_id', 'sender__email', 'message')
    list_filter = ('is_read', 'created_at')

class BookingStatusHistoryAdmin(admin.ModelAdmin):
    list_display = ('id', 'booking', 'previous_status', 'new_status', 'changed_by')
    search_fields = ('booking__booking_id', 'changed_by__email')
    list_filter = ('previous_status', 'new_status')

admin.site.register(Booking, BookingAdmin)
admin.site.register(BookingAddOn)
admin.site.register(Review, ReviewAdmin)
admin.site.register(BookingReschedule, BookingRescheduleAdmin)
admin.site.register(BookingMessage, BookingMessageAdmin)
admin.site.register(BookingStatusHistory, BookingStatusHistoryAdmin)