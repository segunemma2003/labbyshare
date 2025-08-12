#!/usr/bin/env python3
"""
Debug script to see how addon data is being processed
"""
import os
import sys
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'labmyshare.local_settings')
django.setup()

from rest_framework.test import APIClient
from accounts.models import User
from rest_framework.authtoken.models import Token

def debug_addon_data():
    """Debug how addon data is being processed"""
    print("🔍 Debugging addon data processing...")
    
    # Get admin user and token
    admin_user = User.objects.get(email='admin@labmyshare.com')
    token, _ = Token.objects.get_or_create(user=admin_user)
    
    # Create API client
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f'Token {token.key}')
    
    # Test data with addons
    test_data = {
        'customer': 16,
        'professional': 1,
        'service': 1,
        'region': 1,
        'booking_for_self': True,
        'scheduled_date': '2025-08-14',
        'scheduled_time': '15:00',
        'duration_minutes': 60,
        'base_amount': 100.00,
        'addon_amount': 25.00,
        'discount_amount': 0.00,
        'tax_amount': 25.00,
        'total_amount': 150.00,
        'deposit_required': True,
        'deposit_percentage': 20.00,
        'address_line1': '123 Test Street',
        'city': 'Test City',
        'postal_code': '12345',
        'customer_notes': 'Debug test with addons',
        'selected_addons': [1]
    }
    
    print(f"📤 Sending data: {test_data}")
    
    # Send request
    response = client.post('/api/v1/admin/bookings/', test_data, format='multipart')
    
    print(f"📥 Response status: {response.status_code}")
    if response.status_code != 201:
        print(f"📥 Response content: {response.content.decode()}")
    else:
        print("✅ Success!")

if __name__ == "__main__":
    debug_addon_data() 