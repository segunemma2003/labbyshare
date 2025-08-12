#!/usr/bin/env python3
"""
Comprehensive test for all admin APIs
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

User = get_user_model()

def test_all_admin_apis():
    """Test all admin APIs comprehensively"""
    print("🧪 Testing ALL Admin APIs comprehensively...")
    
    # Get admin user and token
    admin_user = User.objects.get(email='admin@labmyshare.com')
    token, _ = Token.objects.get_or_create(user=admin_user)
    
    # Create API client
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f'Token {token.key}')
    
    # Get test data
    region = Region.objects.first()
    category = Category.objects.first()
    service = Service.objects.first()
    addon = AddOn.objects.first()
    professional = Professional.objects.first()
    customer = User.objects.filter(user_type='customer').first()
    
    print(f"📊 Test data loaded:")
    print(f"   - Region: {region.name}")
    print(f"   - Category: {category.name}")
    print(f"   - Service: {service.name}")
    print(f"   - Addon: {addon.name}")
    print(f"   - Professional: {professional.user.get_full_name()}")
    print(f"   - Customer: {customer.get_full_name()}")
    
    # Test 1: Professional APIs
    print("\n" + "="*50)
    print("📋 Test 1: Professional APIs")
    print("="*50)
    
    # Test 1.1: List professionals
    print("\n📝 Test 1.1: List professionals")
    response = client.get('/api/v1/admin/professionals/')
    print(f"Status: {response.status_code}")
    if response.status_code == 200:
        data = response.json()
        print(f"✅ Found {len(data.get('results', []))} professionals")
    else:
        print(f"❌ Failed: {response.content.decode()}")
    
    # Test 1.2: Get professional detail
    print("\n📝 Test 1.2: Get professional detail")
    response = client.get(f'/api/v1/admin/professionals/{professional.id}/')
    print(f"Status: {response.status_code}")
    if response.status_code == 200:
        data = response.json()
        print(f"✅ Professional: {data.get('user', {}).get('first_name')} {data.get('user', {}).get('last_name')}")
    else:
        print(f"❌ Failed: {response.content.decode()}")
    
    # Test 1.3: Create professional
    print("\n📝 Test 1.3: Create professional")
    create_data = {
        'user': {
            'email': f'pro_{int(time.time())}@test.com',
            'first_name': 'Test',
            'last_name': 'Professional',
            'phone_number': '+1234567890',
            'user_type': 'professional'
        },
        'bio': 'Test professional created via admin API',
        'experience_years': 5,
        'regions': [region.id],
        'services': [service.id]
    }
    response = client.post('/api/v1/admin/professionals/', create_data, format='json')
    print(f"Status: {response.status_code}")
    if response.status_code == 201:
        data = response.json()
        print(f"✅ Created professional: {data.get('user', {}).get('email')}")
        new_professional_id = data.get('id')
    else:
        print(f"❌ Failed: {response.content.decode()}")
        new_professional_id = None
    
    # Test 1.4: Update professional
    if new_professional_id:
        print("\n📝 Test 1.4: Update professional")
        update_data = {
            'bio': 'Updated bio via admin API',
            'experience_years': 7
        }
        response = client.put(f'/api/v1/admin/professionals/{new_professional_id}/', update_data, format='json')
        print(f"Status: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Updated professional: {data.get('bio')}")
        else:
            print(f"❌ Failed: {response.content.decode()}")
    
    # Test 2: Booking APIs
    print("\n" + "="*50)
    print("📋 Test 2: Booking APIs")
    print("="*50)
    
    # Test 2.1: List bookings
    print("\n📝 Test 2.1: List bookings")
    response = client.get('/api/v1/admin/bookings/')
    print(f"Status: {response.status_code}")
    if response.status_code == 200:
        data = response.json()
        print(f"✅ Found {len(data.get('results', []))} bookings")
    else:
        print(f"❌ Failed: {response.content.decode()}")
    
    # Test 2.2: Create booking (without addons for now)
    print("\n📝 Test 2.2: Create booking")
    tomorrow = datetime.now().date() + timedelta(days=1)
    create_booking_data = {
        'customer': customer.id,
        'professional': professional.id,
        'service': service.id,
        'region': region.id,
        'booking_for_self': True,
        'scheduled_date': tomorrow.strftime('%Y-%m-%d'),
        'scheduled_time': '15:00',
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
        'customer_notes': 'Test booking created via admin API'
    }
    response = client.post('/api/v1/admin/bookings/', create_booking_data, format='multipart')
    print(f"Status: {response.status_code}")
    if response.status_code == 201:
        data = response.json()
        print(f"✅ Created booking: {data.get('booking_id')}")
        new_booking_id = data.get('id')
    else:
        print(f"❌ Failed: {response.content.decode()}")
        new_booking_id = None
    
    # Test 2.3: Get booking detail
    if new_booking_id:
        print("\n📝 Test 2.3: Get booking detail")
        response = client.get(f'/api/v1/admin/bookings/{new_booking_id}/')
        print(f"Status: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Booking: {data.get('booking_id')} - {data.get('status')}")
        else:
            print(f"❌ Failed: {response.content.decode()}")
    
    # Test 2.4: Update booking
    if new_booking_id:
        print("\n📝 Test 2.4: Update booking")
        update_booking_data = {
            'status': 'confirmed',
            'admin_notes': 'Updated via admin API'
        }
        response = client.put(f'/api/v1/admin/bookings/{new_booking_id}/', update_booking_data, format='multipart')
        print(f"Status: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Updated booking: {data.get('status')}")
        else:
            print(f"❌ Failed: {response.content.decode()}")
    
    # Test 3: Service APIs
    print("\n" + "="*50)
    print("📋 Test 3: Service APIs")
    print("="*50)
    
    # Test 3.1: List services
    print("\n📝 Test 3.1: List services")
    response = client.get('/api/v1/services/')
    print(f"Status: {response.status_code}")
    if response.status_code == 200:
        data = response.json()
        print(f"✅ Found {len(data.get('results', []))} services")
    else:
        print(f"❌ Failed: {response.content.decode()}")
    
    # Test 3.2: Get service detail
    print("\n📝 Test 3.2: Get service detail")
    response = client.get(f'/api/v1/services/{service.id}/')
    print(f"Status: {response.status_code}")
    if response.status_code == 200:
        data = response.json()
        print(f"✅ Service: {data.get('name')} - {data.get('base_price')}")
    else:
        print(f"❌ Failed: {response.content.decode()}")
    
    # Test 4: Region APIs
    print("\n" + "="*50)
    print("📋 Test 4: Region APIs")
    print("="*50)
    
    # Test 4.1: List regions
    print("\n📝 Test 4.1: List regions")
    response = client.get('/api/v1/regions/')
    print(f"Status: {response.status_code}")
    if response.status_code == 200:
        data = response.json()
        print(f"✅ Found {len(data.get('results', []))} regions")
    else:
        print(f"❌ Failed: {response.content.decode()}")
    
    # Test 4.2: Get region detail
    print("\n📝 Test 4.2: Get region detail")
    response = client.get(f'/api/v1/regions/{region.code}/')
    print(f"Status: {response.status_code}")
    if response.status_code == 200:
        data = response.json()
        print(f"✅ Region: {data.get('name')} - {data.get('currency')}")
    else:
        print(f"❌ Failed: {response.content.decode()}")
    
    # Test 5: User APIs
    print("\n" + "="*50)
    print("📋 Test 5: User APIs")
    print("="*50)
    
    # Test 5.1: List users
    print("\n📝 Test 5.1: List users")
    response = client.get('/api/v1/admin/users/')
    print(f"Status: {response.status_code}")
    if response.status_code == 200:
        data = response.json()
        print(f"✅ Found {len(data.get('results', []))} users")
    else:
        print(f"❌ Failed: {response.content.decode()}")
    
    # Test 5.2: Get user detail
    print("\n📝 Test 5.2: Get user detail")
    response = client.get(f'/api/v1/admin/users/{customer.id}/')
    print(f"Status: {response.status_code}")
    if response.status_code == 200:
        data = response.json()
        print(f"✅ User: {data.get('first_name')} {data.get('last_name')} - {data.get('user_type')}")
    else:
        print(f"❌ Failed: {response.content.decode()}")
    
    print("\n" + "="*50)
    print("🎉 All Admin API Tests Completed!")
    print("="*50)

if __name__ == "__main__":
    # Import models
    from regions.models import Region
    from services.models import Service, Category, AddOn
    from professionals.models import Professional
    
    test_all_admin_apis() 