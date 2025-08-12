#!/usr/bin/env python3
"""
Test Professional Creation with FormData
Tests the exact FormData format provided by the user
"""

import os
import sys
import django
from decimal import Decimal
import time

# Setup Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'labmyshare.local_settings')
django.setup()

from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework import status
from services.models import AddOn, Category
from regions.models import Region
from accounts.models import User

User = get_user_model()

def test_professional_formdata():
    """Test professional creation with exact FormData format"""
    print("🧪 Testing Professional Creation with FormData...")
    print("=" * 60)
    
    # Setup
    client = APIClient()
    
    # Create admin user with unique timestamp
    timestamp = int(time.time())
    admin_email = f'admin_formdata_{timestamp}@test.com'
    admin_user = User.objects.create_user(
        username=admin_email,
        email=admin_email,
        password='adminpass123',
        first_name='Admin',
        last_name='User',
        user_type='admin',
        is_staff=True,
        is_superuser=True
    )
    
    # Use existing data or create if needed
    region = Region.objects.first()
    if not region:
        region = Region.objects.create(
            name='Test Region FormData',
            code='TESTFD',
            is_active=True
        )
    
    category = Category.objects.first()
    if not category:
        category = Category.objects.create(
            name='Test Category',
            description='Test category description',
            region=region,
            is_active=True
        )
    
    # Use existing services or create if needed
    service1 = AddOn.objects.first()
    if not service1:
        service1 = AddOn.objects.create(
            name='Service 1',
            description='Test service 1',
            price=Decimal('50.00'),
            duration_minutes=60,
            region=region,
            is_active=True
        )
        service1.categories.add(category)
    
    service2 = AddOn.objects.filter(name='Service 2').first()
    if not service2:
        service2 = AddOn.objects.create(
            name='Service 2',
            description='Test service 2',
            price=Decimal('75.00'),
            duration_minutes=90,
            region=region,
            is_active=True
        )
        service2.categories.add(category)
    
    # Authenticate as admin
    client.force_authenticate(user=admin_user)
    
    # Test 1: Create professional with exact FormData format
    print("\n📝 Test 1: Create Professional with FormData")
    print("-" * 40)
    
    # Create FormData equivalent using APIClient
    form_data = {
        'first_name': 'Bamidele',
        'last_name': 'Emmanuel',
        'email': 'segunemma2203@gmail.com',
        'password': 'Fluidangle@2020',
        'phone_number': '+2349036444724',
        'date_of_birth': '2025-08-07',
        'gender': 'F',
        'bio': 'sadfgfb',
        'regions': 1,
        'services': 27,
        'services': 59,
        'services': 14,
        'services': 45,
        'services': 1,
        'availability[0][region_id]': 1,
        'availability[0][weekday]': 0,
        'availability[0][start_time]': '09:00',
        'availability[0][end_time]': '17:00',
        'availability[0][break_start]': '13:11',
        'availability[0][break_end]': '14:12',
        'availability[0][is_active]': 'true',
        'is_verified': 'true',
        'is_active': 'true'
    }
    
    print(f"📤 Sending FormData with {len(form_data)} fields")
    print(f"📤 Services: {[form_data[key] for key in form_data.keys() if key == 'services']}")
    print(f"📤 Availability: {[key for key in form_data.keys() if key.startswith('availability')]}")
    
    response = client.post(
        '/api/v1/admin/professionals/',
        data=form_data,
        format='multipart'
    )
    
    print(f"📥 Response Status: {response.status_code}")
    print(f"📥 Response Data: {response.data}")
    
    if response.status_code == 201:
        print("✅ Professional created successfully!")
        professional_id = response.data['id']
        
        # Test 2: Get the created professional
        print(f"\n📝 Test 2: Get Professional {professional_id}")
        print("-" * 40)
        
        get_response = client.get(f'/api/v1/admin/professionals/{professional_id}/')
        print(f"📥 Get Response Status: {get_response.status_code}")
        
        if get_response.status_code == 200:
            print("✅ Professional retrieved successfully!")
            professional_data = get_response.data
            print(f"📥 Name: {professional_data.get('user', {}).get('first_name')} {professional_data.get('user', {}).get('last_name')}")
            print(f"📥 Email: {professional_data.get('user', {}).get('email')}")
            print(f"📥 Regions: {len(professional_data.get('regions', []))}")
            print(f"📥 Services: {len(professional_data.get('services', []))}")
            print(f"📥 Availability: {len(professional_data.get('availability', []))}")
        else:
            print(f"❌ Failed to get professional: {get_response.data}")
    else:
        print(f"❌ Failed to create professional: {response.data}")
    
    # Cleanup
    print(f"\n🧹 Cleaning up test data...")
    User.objects.filter(email='segunemma2203@gmail.com').delete()
    User.objects.filter(email=admin_email).delete()
    Region.objects.filter(code='TESTFD').delete()
    Category.objects.filter(name='Test Category').delete()
    
    print("✅ Test completed!")

if __name__ == '__main__':
    test_professional_formdata() 