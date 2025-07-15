from django.contrib import admin

from .models import AddOn, Category, RegionalPricing, Service, ServiceImage, ServiceReview

# Register your models here.
admin.sites.register(Category)
admin.sites.register(Service)
admin.sites.register(RegionalPricing)
admin.sites.register(AddOn)
admin.sites.register(ServiceImage)
admin.sites.register(ServiceReview)