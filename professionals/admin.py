from django.contrib import admin

from .models import Professional, ProfessionalAvailability, ProfessionalDocument, ProfessionalRegion, ProfessionalService, ProfessionalUnavailability

# Register your models here.
admin.sites.register(Professional)
admin.sites.register(ProfessionalRegion)
admin.sites.register(ProfessionalService)

admin.sites.register(ProfessionalAvailability)
admin.sites.register(ProfessionalUnavailability)
admin.sites.register(ProfessionalDocument)