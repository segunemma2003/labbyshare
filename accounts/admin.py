from django.contrib import admin
from .models import User, OTPVerification

# Register models explicitly
admin.site.register(User)
admin.site.register(OTPVerification)
