from django.contrib import admin

from .models import Region, RegionalSettings

# Register your models here.
admin.sites.register(Region)
admin.sites.register(RegionalSettings)