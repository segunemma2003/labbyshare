#!/usr/bin/env python3
"""
Direct test of API functionality without running server
"""
import os
import sys
import django

# Add the project directory to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'labmyshare.local_settings')
django.setup()

from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework.authtoken.models import Token

from regions.models import Region
from services.models import Service, Category
from professionals.models import Professional, ProfessionalService

User = get_user_model()

def test_api_functionality():
    """Test API functionality directly"""
    print("🧪 Testing API functionality directly...")
    
    # Get admin user and token
    admin_user = User.objects.get(email='admin@labmyshare.com')
    token, _ = Token.objects.get_or_create(user=admin_user)
    
    # Create API client
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f'Token {token.key}')
    
    # Test 1: GET professionals list
    print("\n📝 Test 1: GET professionals list")
    try:
        response = client.get('/api/v1/admin/professionals/')
        print(f"Status: {response.status_code}")
        if response.status_code == 200:
            print("✅ GET professionals list works")
            data = response.json()
            print(f"Found {len(data)} professionals")
        else:
            print(f"❌ GET failed: {response.content}")
    except Exception as e:
        print(f"❌ Error: {e}")
    
    # Test 2: GET specific professional
    print("\n📝 Test 2: GET specific professional")
    try:
        response = client.get('/api/v1/admin/professionals/1/')
        print(f"Status: {response.status_code}")
        if response.status_code == 200:
            print("✅ GET specific professional works")
            data = response.json()
            print(f"Professional: {data.get('first_name')} {data.get('last_name')}")
        else:
            print(f"❌ GET failed: {response.content}")
    except Exception as e:
        print(f"❌ Error: {e}")
    
    # Test 3: PUT update professional (JSON)
    print("\n📝 Test 3: PUT update professional (JSON)")
    try:
        data = {
            'bio': 'Updated bio via JSON',
            'experience_years': 10
        }
        response = client.put('/api/v1/admin/professionals/1/', data, format='json')
        print(f"Status: {response.status_code}")
        if response.status_code == 200:
            print("✅ PUT update (JSON) works")
            result = response.json()
            print(f"Updated bio: {result.get('bio')}")
        else:
            print(f"❌ PUT failed: {response.content}")
    except Exception as e:
        print(f"❌ Error: {e}")
    
    # Test 4: PUT update professional (form_data)
    print("\n📝 Test 4: PUT update professional (form_data)")
    try:
        data = {
            'bio': 'Updated bio via form_data',
            'experience_years': 12
        }
        response = client.put('/api/v1/admin/professionals/1/', data, format='multipart')
        print(f"Status: {response.status_code}")
        if response.status_code == 200:
            print("✅ PUT update (form_data) works")
            result = response.json()
            print(f"Updated bio: {result.get('bio')}")
        else:
            print(f"❌ PUT failed: {response.content}")
    except Exception as e:
        print(f"❌ Error: {e}")
    
    # Test 5: PUT update with availability (form_data)
    print("\n📝 Test 5: PUT update with availability (form_data)")
    try:
        data = {
            'bio': 'Updated bio with availability',
            'availability[0][region_id]': '1',
            'availability[0][weekday]': '2',
            'availability[0][start_time]': '10:00',
            'availability[0][end_time]': '18:00',
            'availability[0][is_active]': 'true'
        }
        response = client.put('/api/v1/admin/professionals/1/', data, format='multipart')
        print(f"Status: {response.status_code}")
        if response.status_code == 200:
            print("✅ PUT update with availability (form_data) works")
            result = response.json()
            print(f"Updated bio: {result.get('bio')}")
            if 'availability_by_region' in result:
                print(f"Availability: {len(result['availability_by_region'])} regions")
        else:
            print(f"❌ PUT failed: {response.content}")
    except Exception as e:
        print(f"❌ Error: {e}")
    
    # Test 6: POST create new professional
    print("\n📝 Test 6: POST create new professional")
    try:
        data = {
            'first_name': 'Test',
            'last_name': 'Professional',
            'email': 'test2@example.com',
            'password': 'test123',
            'bio': 'New professional via API',
            'experience_years': 5,
            'is_verified': True,
            'is_active': True,
            'travel_radius_km': 10,
            'min_booking_notice_hours': 24,
            'regions': [1],
            'services': [1]
        }
        response = client.post('/api/v1/admin/professionals/', data, format='json')
        print(f"Status: {response.status_code}")
        if response.status_code == 201:
            print("✅ POST create professional works")
            result = response.json()
            print(f"Created professional ID: {result.get('id')}")
        else:
            print(f"❌ POST failed: {response.content}")
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    test_api_functionality() 