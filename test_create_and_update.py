#!/usr/bin/env python3
"""
Comprehensive test for CREATE and UPDATE operations with form_data
"""
import os
import sys
import django
import time

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'labmyshare.local_settings')
django.setup()

from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework.authtoken.models import Token

User = get_user_model()

def test_create_and_update():
    """Test both CREATE and UPDATE operations with form_data"""
    print("🧪 Testing CREATE and UPDATE operations with form_data...")
    
    # Get admin user and token
    admin_user = User.objects.get(email='admin@labmyshare.com')
    token, _ = Token.objects.get_or_create(user=admin_user)
    
    # Create API client
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f'Token {token.key}')
    
    # Use timestamp for unique emails
    timestamp = int(time.time())
    
    # Test 1: CREATE professional with form_data (basic fields)
    print("\n📝 Test 1: CREATE professional with form_data (basic fields)")
    create_data = {
        'first_name': 'John',
        'last_name': 'Doe',
        'email': f'john.doe.{timestamp}@test.com',
        'password': 'testpassword123',
        'bio': 'New professional created via form_data',
        'experience_years': 8,
        'is_verified': True,
        'is_active': True,
        'travel_radius_km': 15,
        'min_booking_notice_hours': 48,
        'regions': [1],  # List for CREATE
        'services': [1]  # List for CREATE
    }
    
    response = client.post('/api/v1/admin/professionals/', create_data, format='multipart')
    print(f"Status: {response.status_code}")
    if response.status_code == 201:
        print("✅ CREATE professional (basic) works")
        result = response.json()
        professional_id = result.get('id')
        print(f"Created professional ID: {professional_id}")
    else:
        print(f"❌ CREATE failed: {response.content}")
        return
    
    # Test 2: CREATE professional with form_data (including availability)
    print("\n📝 Test 2: CREATE professional with form_data (including availability)")
    create_data_with_availability = {
        'first_name': 'Jane',
        'last_name': 'Smith',
        'email': f'jane.smith.{timestamp}@test.com',
        'password': 'testpassword123',
        'bio': 'New professional with availability via form_data',
        'experience_years': 12,
        'is_verified': True,
        'is_active': True,
        'travel_radius_km': 20,
        'min_booking_notice_hours': 24,
        'regions': [1],  # List for CREATE
        'services': [1],  # List for CREATE
        'availability[0][region_id]': '1',
        'availability[0][weekday]': '1',
        'availability[0][start_time]': '09:00',
        'availability[0][end_time]': '17:00',
        'availability[0][is_active]': 'true',
        'availability[1][region_id]': '1',
        'availability[1][weekday]': '2',
        'availability[1][start_time]': '10:00',
        'availability[1][end_time]': '18:00',
        'availability[1][is_active]': 'true'
    }
    
    response = client.post('/api/v1/admin/professionals/', create_data_with_availability, format='multipart')
    print(f"Status: {response.status_code}")
    if response.status_code == 201:
        print("✅ CREATE professional (with availability) works")
        result = response.json()
        professional_id_2 = result.get('id')
        print(f"Created professional ID: {professional_id_2}")
    else:
        print(f"❌ CREATE with availability failed: {response.content}")
    
    # Test 3: UPDATE professional with form_data (basic fields)
    print("\n📝 Test 3: UPDATE professional with form_data (basic fields)")
    update_data = {
        'bio': 'Updated bio via form_data',
        'experience_years': 10,
        'travel_radius_km': 25
    }
    
    response = client.put(f'/api/v1/admin/professionals/{professional_id}/', update_data, format='multipart')
    print(f"Status: {response.status_code}")
    if response.status_code == 200:
        print("✅ UPDATE professional (basic) works")
        result = response.json()
        print(f"Updated bio: {result.get('bio')}")
        print(f"Updated experience: {result.get('experience_years')}")
    else:
        print(f"❌ UPDATE failed: {response.content}")
    
    # Test 4: UPDATE professional with form_data (including availability)
    print("\n📝 Test 4: UPDATE professional with form_data (including availability)")
    update_data_with_availability = {
        'bio': 'Updated bio with availability via form_data',
        'experience_years': 15,
        'availability[0][region_id]': '1',
        'availability[0][weekday]': '3',
        'availability[0][start_time]': '11:00',
        'availability[0][end_time]': '19:00',
        'availability[0][is_active]': 'true',
        'availability[1][region_id]': '1',
        'availability[1][weekday]': '4',
        'availability[1][start_time]': '12:00',
        'availability[1][end_time]': '20:00',
        'availability[1][is_active]': 'true'
    }
    
    response = client.put(f'/api/v1/admin/professionals/{professional_id}/', update_data_with_availability, format='multipart')
    print(f"Status: {response.status_code}")
    if response.status_code == 200:
        print("✅ UPDATE professional (with availability) works")
        result = response.json()
        print(f"Updated bio: {result.get('bio')}")
        if 'availability_by_region' in result:
            print(f"Availability regions: {len(result['availability_by_region'])}")
    else:
        print(f"❌ UPDATE with availability failed: {response.content}")
    
    # Test 5: UPDATE regions and services with form_data
    print("\n📝 Test 5: UPDATE regions and services with form_data")
    update_regions_services = {
        'bio': 'Updated with regions and services',
        'regions': [1],  # List for UPDATE
        'services': [1]  # List for UPDATE
    }
    
    response = client.put(f'/api/v1/admin/professionals/{professional_id}/', update_regions_services, format='multipart')
    print(f"Status: {response.status_code}")
    if response.status_code == 200:
        print("✅ UPDATE regions and services works")
        result = response.json()
        print(f"Updated bio: {result.get('bio')}")
    else:
        print(f"❌ UPDATE regions and services failed: {response.content}")
    
    print("\n🎉 All CREATE and UPDATE tests completed!")

if __name__ == "__main__":
    test_create_and_update() 