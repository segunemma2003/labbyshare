#!/usr/bin/env python3
"""
Comprehensive test for CREATE and UPDATE booking operations with form_data
"""
import os
import sys
import django
import time
from datetime import datetime, timedelta

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'labmyshare.local_settings')
django.setup()

from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework.authtoken.models import Token
from accounts.models import User

def test_booking_create_and_update():
    """Test both CREATE and UPDATE booking operations with form_data"""
    print("🧪 Testing CREATE and UPDATE booking operations with form_data...")
    
    # Get admin user and token
    admin_user = User.objects.get(email='admin@labmyshare.com')
    token, _ = Token.objects.get_or_create(user=admin_user)
    
    # Create API client
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f'Token {token.key}')
    
    # Get test data
    from regions.models import Region
    from services.models import Category, Service, AddOn
    from professionals.models import Professional
    
    # Get or create test data
    region = Region.objects.first()
    if not region:
        print("❌ No region found. Please run setup_local_db.py first.")
        return
    
    category = Category.objects.first()
    if not category:
        print("❌ No category found. Please run setup_local_db.py first.")
        return
    
    service = Service.objects.first()
    if not service:
        print("❌ No service found. Please run setup_local_db.py first.")
        return
    
    addon = AddOn.objects.first()
    if not addon:
        print("❌ No addon found. Please run setup_local_db.py first.")
        return
    
    professional = Professional.objects.first()
    if not professional:
        print("❌ No professional found. Please run setup_local_db.py first.")
        return
    
    customer = User.objects.filter(user_type='customer').first()
    if not customer:
        # Create a test customer
        customer = User.objects.create_user(
            email=f'customer{int(time.time())}@test.com',
            username=f'test_customer_{int(time.time())}',
            password='password123',
            first_name='Test',
            last_name='Customer',
            user_type='customer'
        )
        print(f"✅ Created test customer: {customer.email}")
    
    timestamp = int(time.time())
    tomorrow = datetime.now().date() + timedelta(days=1)
    
    # Test 1: CREATE booking with form_data (basic fields)
    print("\n📝 Test 1: CREATE booking with form_data (basic fields)")
    create_data = {
        'customer': customer.id,
        'professional': professional.id,
        'service': service.id,
        'region': region.id,
        'booking_for_self': True,
        'scheduled_date': tomorrow.strftime('%Y-%m-%d'),
        'scheduled_time': '14:00',
        'duration_minutes': 60,
        'base_amount': 100.00,
        'addon_amount': 0.00,
        'discount_amount': 0.00,
        'tax_amount': 20.00,
        'total_amount': 120.00,
        'deposit_required': True,
        'deposit_percentage': 20.00,
        'address_line1': '123 Test Street',
        'city': 'Test City',
        'postal_code': '12345',
        'customer_notes': 'Test booking created via form_data'
    }
    
    response = client.post('/api/v1/admin/bookings/', create_data, format='multipart')
    print(f"Status: {response.status_code}")
    if response.status_code == 201:
        data = response.json()
        booking_id = data.get('booking_id')
        print(f"✅ Created booking with ID: {booking_id}")
        print(f"Customer: {data.get('customer_name')}")
        print(f"Service: {data.get('service_name')}")
        print(f"Total Amount: {data.get('total_amount')}")
    else:
        print(f"❌ Create failed: {response.text}")
        return
    
    # Test 2: CREATE booking with form_data (including addons)
    print("\n📝 Test 2: CREATE booking with form_data (including addons)")
    create_data_with_addons = {
        'customer': customer.id,
        'professional': professional.id,
        'service': service.id,
        'region': region.id,
        'booking_for_self': False,
        'recipient_name': 'John Doe',
        'recipient_phone': '+1234567890',
        'recipient_email': 'john@test.com',
        'scheduled_date': (tomorrow + timedelta(days=1)).strftime('%Y-%m-%d'),
        'scheduled_time': '15:00',
        'duration_minutes': 90,
        'base_amount': 150.00,
        'addon_amount': 25.00,
        'discount_amount': 10.00,
        'tax_amount': 33.00,
        'total_amount': 198.00,
        'deposit_required': True,
        'deposit_percentage': 25.00,
        'address_line1': '456 Addon Street',
        'city': 'Addon City',
        'postal_code': '67890',
        'customer_notes': 'Test booking with addons via form_data',
        'selected_addons': [addon.id]  # Send as list of IDs
    }
    
    response = client.post('/api/v1/admin/bookings/', create_data_with_addons, format='multipart')
    print(f"Status: {response.status_code}")
    if response.status_code == 201:
        data = response.json()
        booking_id_with_addons = data.get('booking_id')
        print(f"✅ Created booking with addons: {booking_id_with_addons}")
        print(f"Total Amount: {data.get('total_amount')}")
        addons = data.get('selected_addons', [])
        print(f"Addons count: {len(addons)}")
    else:
        print(f"❌ Create with addons failed: {response.text}")
        return
    
    # Test 3: UPDATE booking (basic fields)
    print(f"\n📝 Test 3: UPDATE booking {booking_id} (basic fields)")
    update_data = {
        'status': 'confirmed',
        'payment_status': 'deposit_paid',
        'professional_notes': 'Updated via server API test',
        'admin_notes': 'Admin notes added'
    }
    
    response = client.put(f'/api/v1/admin/bookings/{booking_id}/', update_data, format='multipart')
    print(f"Status: {response.status_code}")
    if response.status_code == 200:
        data = response.json()
        print(f"✅ Updated booking successfully")
        print(f"New status: {data.get('status')}")
        print(f"New payment status: {data.get('payment_status')}")
        print(f"Professional notes: {data.get('professional_notes')}")
    else:
        print(f"❌ Update failed: {response.text}")
    
    # Test 4: UPDATE booking (with addons)
    print(f"\n📝 Test 4: UPDATE booking {booking_id} (with addons)")
    update_data_with_addons = {
        'status': 'in_progress',
        'addon_amount': 50.00,
        'total_amount': 170.00,
        'selected_addons': [addon.id]
    }
    
    response = client.put(f'/api/v1/admin/bookings/{booking_id}/', update_data_with_addons, format='multipart')
    print(f"Status: {response.status_code}")
    if response.status_code == 200:
        data = response.json()
        print(f"✅ Updated booking with addons successfully")
        print(f"New status: {data.get('status')}")
        print(f"New addon amount: {data.get('addon_amount')}")
        print(f"New total amount: {data.get('total_amount')}")
        addons = data.get('selected_addons', [])
        print(f"Addons count: {len(addons)}")
    else:
        print(f"❌ Update with addons failed: {response.text}")
    
    # Test 5: UPDATE booking (address and scheduling)
    print(f"\n📝 Test 5: UPDATE booking {booking_id} (address and scheduling)")
    new_date = (tomorrow + timedelta(days=2)).strftime('%Y-%m-%d')
    update_address_scheduling = {
        'scheduled_date': new_date,
        'scheduled_time': '16:00',
        'address_line1': '789 Updated Street',
        'address_line2': 'Apt 4B',
        'city': 'Updated City',
        'postal_code': '11111',
        'location_notes': 'Updated location notes'
    }
    
    response = client.put(f'/api/v1/admin/bookings/{booking_id}/', update_address_scheduling, format='multipart')
    print(f"Status: {response.status_code}")
    if response.status_code == 200:
        data = response.json()
        print(f"✅ Updated address and scheduling successfully")
        print(f"New date: {data.get('scheduled_date')}")
        print(f"New time: {data.get('scheduled_time')}")
        print(f"New address: {data.get('address_line1')}")
        print(f"New city: {data.get('city')}")
    else:
        print(f"❌ Update address/scheduling failed: {response.text}")
    
    print("\n🎉 Booking API testing completed!")

if __name__ == "__main__":
    test_booking_create_and_update() 