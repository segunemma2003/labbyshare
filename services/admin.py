from django.contrib import admin

from .models import AddOn, Category, RegionalPricing, Service, ServiceImage, ServiceReview

# Register your models here.
admin.site.register(Category)
admin.site.register(Service)
admin.site.register(RegionalPricing)
admin.site.register(AddOn)
admin.site.register(ServiceImage)
admin.site.register(ServiceReview)