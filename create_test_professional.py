#!/usr/bin/env python3
"""
Create test professional for debugging
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
from regions.models import Region
from services.models import Service, Category
from professionals.models import Professional, ProfessionalService

User = get_user_model()

# Get or create region
region, created = Region.objects.get_or_create(
    name="United Kingdom",
    defaults={
        'code': 'UK',
        'is_active': True
    }
)

# Get or create category
category, created = Category.objects.get_or_create(
    name="Test Category",
    defaults={
        'description': 'Test category for debugging',
        'region': region,
        'is_active': True
    }
)

# Get or create service
service, created = Service.objects.get_or_create(
    name="Test Service",
    defaults={
        'description': 'Test service for debugging',
        'category': category,
        'base_price': 50.00,
        'duration_minutes': 60,
        'is_active': True
    }
)

# Create test professional user
professional_user, created = User.objects.get_or_create(
    email='professional@test.com',
    defaults={
        'username': 'test_professional',
        'first_name': 'Test',
        'last_name': 'Professional',
        'user_type': 'professional',
        'is_active': True
    }
)

if created:
    professional_user.set_password('test123')
    professional_user.save()
    print("✅ Created professional user")

# Create professional
professional, created = Professional.objects.get_or_create(
    user=professional_user,
    defaults={
        'bio': 'Test professional for debugging',
        'experience_years': 5,
        'is_verified': True,
        'is_active': True,
        'travel_radius_km': 10,
        'min_booking_notice_hours': 24
    }
)

if created:
    # Add regions and services
    professional.regions.add(region)
    
    # Create professional service
    ProfessionalService.objects.create(
        professional=professional,
        service=service,
        region=region,
        custom_price=50.00,
        is_active=True
    )
    
    print("✅ Created professional")

print(f"👨‍💼 Professional ID: {professional.id}")
print(f"👤 Professional User: {professional.user.email}")
print(f"🌍 Region: {region.name}")
print(f"🔧 Service: {service.name}")
print(f"🔗 Test URL: http://localhost:8000/api/v1/admin/professionals/{professional.id}/") 