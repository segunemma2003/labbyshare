from django.contrib import admin

from .models import AddOn, Category, RegionalPricing, Service, ServiceImage, ServiceReview

class ServiceAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'category', 'region', 'price', 'is_active')
    search_fields = ('name', 'category__name', 'region__name')
    list_filter = ('region', 'category', 'is_active')

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        if hasattr(request.user, 'current_region') and request.user.current_region:
            return qs.filter(region=request.user.current_region)
        return qs.none()

class RegionalPricingAdmin(admin.ModelAdmin):
    list_display = ('id', 'service', 'region', 'price')
    search_fields = ('service__name', 'region__name')
    list_filter = ('region',)

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        if hasattr(request.user, 'current_region') and request.user.current_region:
            return qs.filter(region=request.user.current_region)
        return qs.none()

class AddOnAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'region', 'price')
    search_fields = ('name', 'region__name')
    list_filter = ('region',)

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        if hasattr(request.user, 'current_region') and request.user.current_region:
            return qs.filter(region=request.user.current_region)
        return qs.none()

class ServiceImageAdmin(admin.ModelAdmin):
    list_display = ('id', 'service', 'region', 'image')
    search_fields = ('service__name', 'region__name')
    list_filter = ('region',)

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        if hasattr(request.user, 'current_region') and request.user.current_region:
            return qs.filter(region=request.user.current_region)
        return qs.none()

# Register your models here.
admin.site.register(Category)
admin.site.register(Service, ServiceAdmin)
admin.site.register(RegionalPricing, RegionalPricingAdmin)
admin.site.register(AddOn, AddOnAdmin)
admin.site.register(ServiceImage, ServiceImageAdmin)
admin.site.register(ServiceReview)