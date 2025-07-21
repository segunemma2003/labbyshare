from django.contrib import admin
from .models import Professional, ProfessionalAvailability, ProfessionalUnavailability, ProfessionalRegion, ProfessionalService, ProfessionalDocument

class ProfessionalAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'is_verified', 'is_active', 'rating', 'total_reviews', 'created_at')
    search_fields = ('user__email', 'user__first_name', 'user__last_name')
    list_filter = ('user__current_region', 'is_verified', 'is_active', 'created_at')
    date_hierarchy = 'created_at'

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        if hasattr(request.user, 'current_region') and request.user.current_region:
            return qs.filter(user__current_region=request.user.current_region)
        return qs.none()

class ProfessionalAvailabilityAdmin(admin.ModelAdmin):
    list_display = ('id', 'professional', 'region', 'weekday', 'start_time', 'end_time', 'is_active')
    search_fields = ('professional__user__email', 'region__name')
    list_filter = ('region', 'weekday', 'is_active')

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        if hasattr(request.user, 'current_region') and request.user.current_region:
            return qs.filter(region=request.user.current_region)
        return qs.none()

class ProfessionalUnavailabilityAdmin(admin.ModelAdmin):
    list_display = ('id', 'professional', 'region', 'date', 'start_time', 'end_time', 'reason', 'is_recurring')
    search_fields = ('professional__user__email', 'region__name', 'reason')
    list_filter = ('region', 'date', 'is_recurring')

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        if hasattr(request.user, 'current_region') and request.user.current_region:
            return qs.filter(region=request.user.current_region)
        return qs.none()

class ProfessionalRegionAdmin(admin.ModelAdmin):
    list_display = ('id', 'professional', 'region', 'is_primary', 'travel_fee', 'created_at')
    search_fields = ('professional__user__email', 'region__name')
    list_filter = ('region', 'is_primary', 'created_at')

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        if hasattr(request.user, 'current_region') and request.user.current_region:
            return qs.filter(region=request.user.current_region)
        return qs.none()

class ProfessionalServiceAdmin(admin.ModelAdmin):
    list_display = ('id', 'professional', 'service', 'region', 'custom_price', 'is_active', 'created_at')
    search_fields = ('professional__user__email', 'service__name', 'region__name')
    list_filter = ('region', 'is_active', 'service', 'created_at')

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        if hasattr(request.user, 'current_region') and request.user.current_region:
            return qs.filter(region=request.user.current_region)
        return qs.none()

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