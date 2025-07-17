from django.contrib import admin
from .models import *

# Register all models in this app
for model in [m for name, m in globals().items() if hasattr(m, '__module__') and m.__module__ == 'accounts.models']:
    try:
        admin.site.register(model)
    except admin.sites.AlreadyRegistered:
        pass
