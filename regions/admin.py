from django.contrib import admin

from .models import Region, RegionalSettings

# Register your models here.
admin.site.register(Region)
admin.site.register(RegionalSettings)