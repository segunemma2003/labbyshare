#!/usr/bin/env python3
"""
Get admin token for testing
"""
import os
import sys
import django

# Add the project directory to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'labmyshare.local_settings')
django.setup()

from django.contrib.auth import get_user_model
from rest_framework.authtoken.models import Token

User = get_user_model()

# Get or create admin user
admin_user, created = User.objects.get_or_create(
    email='admin@labmyshare.com',
    defaults={
        'username': 'admin',
        'is_superuser': True,
        'is_staff': True,
        'is_active': True,
    }
)

if created:
    admin_user.set_password('admin123')
    admin_user.save()
    print("✅ Created admin user")

# Get or create token
token, created = Token.objects.get_or_create(user=admin_user)

print(f"🔑 Admin Token: {token.key}")
print(f"👤 Admin User: {admin_user.email}")
print(f"🔗 Test URL: http://localhost:8000/api/v1/admin/professionals/1/")
print(f"📋 Use this token in Authorization header: Token {token.key}") 