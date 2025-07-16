from django.contrib import admin
from .models import Professional, ProfessionalAvailability, ProfessionalUnavailability, ProfessionalRegion, ProfessionalService, ProfessionalDocument

class ProfessionalAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'is_verified', 'is_active', 'rating', 'total_reviews', 'created_at')
    search_fields = ('user__email', 'user__first_name', 'user__last_name')
    list_filter = ('is_verified', 'is_active', 'created_at')
    date_hierarchy = 'created_at'

class ProfessionalAvailabilityAdmin(admin.ModelAdmin):
    list_display = ('id', 'professional', 'region', 'weekday', 'start_time', 'end_time', 'is_active')
    search_fields = ('professional__user__email', 'region__name')
    list_filter = ('weekday', 'region', 'is_active')

class ProfessionalUnavailabilityAdmin(admin.ModelAdmin):
    list_display = ('id', 'professional', 'region', 'date', 'start_time', 'end_time', 'reason', 'is_recurring')
    search_fields = ('professional__user__email', 'region__name', 'reason')
    list_filter = ('date', 'region', 'is_recurring')

class ProfessionalRegionAdmin(admin.ModelAdmin):
    list_display = ('id', 'professional', 'region', 'is_primary', 'travel_fee', 'created_at')
    search_fields = ('professional__user__email', 'region__name')
    list_filter = ('is_primary', 'region', 'created_at')

class ProfessionalServiceAdmin(admin.ModelAdmin):
    list_display = ('id', 'professional', 'service', 'region', 'custom_price', 'is_active', 'created_at')
    search_fields = ('professional__user__email', 'service__name', 'region__name')
    list_filter = ('is_active', 'region', 'service', 'created_at')

class ProfessionalDocumentAdmin(admin.ModelAdmin):
    list_display = ('id', 'professional', 'document_type', 'is_verified', 'created_at')
    search_fields = ('professional__user__email', 'document_type')
    list_filter = ('is_verified', 'document_type', 'created_at')

admin.site.register(Professional, ProfessionalAdmin)
admin.site.register(ProfessionalAvailability, ProfessionalAvailabilityAdmin)
admin.site.register(ProfessionalUnavailability, ProfessionalUnavailabilityAdmin)
admin.site.register(ProfessionalRegion, ProfessionalRegionAdmin)
admin.site.register(ProfessionalService, ProfessionalServiceAdmin)
admin.site.register(ProfessionalDocument, ProfessionalDocumentAdmin)