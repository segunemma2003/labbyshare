#!/usr/bin/env python3
"""
Quick test of API functionality
"""
import os
import sys
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'labmyshare.local_settings')
django.setup()

from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework.authtoken.models import Token

User = get_user_model()

def quick_test():
    """Quick test of API functionality"""
    print("🧪 Quick API Test...")
    
    # Get admin user and token
    admin_user = User.objects.get(email='admin@labmyshare.com')
    token, _ = Token.objects.get_or_create(user=admin_user)
    
    # Create API client
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f'Token {token.key}')
    
    # Test 1: GET professionals list
    print("\n📝 Test 1: GET professionals list")
    response = client.get('/api/v1/admin/professionals/')
    print(f"Status: {response.status_code}")
    if response.status_code == 200:
        print("✅ GET professionals list works")
        data = response.json()
        print(f"Found {len(data)} professionals")
    else:
        print(f"❌ GET failed: {response.content}")
    
    # Test 2: PUT update professional (form_data)
    print("\n📝 Test 2: PUT update professional (form_data)")
    data = {
        'bio': 'Updated bio via form_data test',
        'experience_years': 15
    }
    response = client.put('/api/v1/admin/professionals/1/', data, format='multipart')
    print(f"Status: {response.status_code}")
    if response.status_code == 200:
        print("✅ PUT update (form_data) works")
        result = response.json()
        print(f"Updated bio: {result.get('bio')}")
    else:
        print(f"❌ PUT failed: {response.content}")
    
    # Test 3: PUT update with availability (form_data)
    print("\n📝 Test 3: PUT update with availability (form_data)")
    data = {
        'bio': 'Updated bio with availability test',
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
    else:
        print(f"❌ PUT failed: {response.content}")
    
    print("\n🎉 Quick test completed!")

if __name__ == "__main__":
    quick_test() 