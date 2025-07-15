from django.contrib import admin

from .models import Professional, ProfessionalAvailability, ProfessionalDocument, ProfessionalRegion, ProfessionalService, ProfessionalUnavailability

# Register your models here.
admin.site.register(Professional)
admin.site.register(ProfessionalRegion)
admin.site.register(ProfessionalService)

admin.site.register(ProfessionalAvailability)
admin.site.register(ProfessionalUnavailability)
admin.site.register(ProfessionalDocument)