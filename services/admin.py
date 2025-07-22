from django.contrib import admin

from .models import AddOn, Category, RegionalPricing, Service, ServiceImage, ServiceReview

class ServiceAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'category', 'get_region', 'is_active')
    search_fields = ('name', 'category__name', 'category__region__name')
    list_filter = ('category', 'is_active')

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        if hasattr(request.user, 'current_region') and request.user.current_region:
            return qs.filter(category__region=request.user.current_region)
        return qs.none()

    def get_region(self, obj):
        return obj.category.region.name if obj.category and obj.category.region else None
    get_region.short_description = 'Region'

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
    list_display = ('id', 'name', 'region', 'price', 'is_active', 'get_categories')
    search_fields = ('name', 'region__name')
    list_filter = ('region', 'is_active')
    filter_horizontal = ('categories',)

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        if hasattr(request.user, 'current_region') and request.user.current_region:
            return qs.filter(region=request.user.current_region)
        return qs.none()

    def get_categories(self, obj):
        return ", ".join([c.name for c in obj.categories.all()])

    get_categories.short_description = 'Categories'

class ServiceImageAdmin(admin.ModelAdmin):
    list_display = ('id', 'service', 'get_region', 'image')
    search_fields = ('service__name', 'service__category__region__name')
    list_filter = ()

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        if hasattr(request.user, 'current_region') and request.user.current_region:
            return qs.filter(service__category__region=request.user.current_region)
        return qs.none()

    def get_region(self, obj):
        return obj.service.category.region.name if obj.service and obj.service.category and obj.service.category.region else None
    get_region.short_description = 'Region'

# Register your models here.
admin.site.register(Category)
admin.site.register(Service, ServiceAdmin)
admin.site.register(RegionalPricing, RegionalPricingAdmin)
admin.site.register(AddOn, AddOnAdmin)
admin.site.register(ServiceImage, ServiceImageAdmin)
admin.site.register(ServiceReview)