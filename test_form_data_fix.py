#!/usr/bin/env python3
"""
Test script to verify form_data fix works
"""
import os
import sys
import django
import requests
import json

# Add the project directory to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'labmyshare.local_settings')
django.setup()

from django.contrib.auth import get_user_model
from rest_framework.authtoken.models import Token

User = get_user_model()

def test_form_data():
    """Test form_data functionality"""
    print("🧪 Testing form_data fix...")
    
    # Get admin token
    admin_user = User.objects.get(email='admin@labmyshare.com')
    token, _ = Token.objects.get_or_create(user=admin_user)
    
    base_url = "http://localhost:8000"
    headers = {
        'Authorization': f'Token {token.key}'
    }
    
    # Test 1: Basic update without availability
    print("\n📝 Test 1: Basic update without availability")
    data = {
        'bio': 'Test bio from form_data',
        'experience_years': 8
    }
    
    try:
        response = requests.put(
            f"{base_url}/api/v1/admin/professionals/1/",
            headers=headers,
            data=data
        )
        print(f"Status: {response.status_code}")
        if response.status_code == 200:
            print("✅ Basic update works")
        else:
            print(f"❌ Basic update failed: {response.text}")
    except Exception as e:
        print(f"❌ Connection error: {e}")
    
    # Test 2: Update with availability
    print("\n📝 Test 2: Update with availability")
    data = {
        'bio': 'Test bio with availability',
        'availability[0][region_id]': '1',
        'availability[0][weekday]': '2',
        'availability[0][start_time]': '10:00',
        'availability[0][end_time]': '18:00',
        'availability[0][is_active]': 'true'
    }
    
    try:
        response = requests.put(
            f"{base_url}/api/v1/admin/professionals/1/",
            headers=headers,
            data=data
        )
        print(f"Status: {response.status_code}")
        if response.status_code == 200:
            print("✅ Availability update works")
            result = response.json()
            print(f"Updated bio: {result.get('bio')}")
        else:
            print(f"❌ Availability update failed: {response.text}")
    except Exception as e:
        print(f"❌ Connection error: {e}")
    
    # Test 3: JSON update (should work)
    print("\n📝 Test 3: JSON update (control test)")
    data = {
        'bio': 'Test bio from JSON',
        'availability': [
            {
                'region_id': 1,
                'weekday': 2,
                'start_time': '10:00',
                'end_time': '18:00',
                'is_active': True
            }
        ]
    }
    
    try:
        response = requests.put(
            f"{base_url}/api/v1/admin/professionals/1/",
            headers=headers,
            json=data
        )
        print(f"Status: {response.status_code}")
        if response.status_code == 200:
            print("✅ JSON update works")
        else:
            print(f"❌ JSON update failed: {response.text}")
    except Exception as e:
        print(f"❌ Connection error: {e}")

if __name__ == "__main__":
    test_form_data() 