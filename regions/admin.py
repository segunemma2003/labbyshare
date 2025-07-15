from django.contrib import admin

from regions.models import Region, RegionalSettings

# Register your models here.
admin.sites.register(Region)
admin.sites.register(RegionalSettings)