#!/usr/bin/env python3
"""
Test Admin Addon APIs
Tests all CRUD operations for admin addon management
"""

import os
import sys
import django
from decimal import Decimal

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

def test_admin_addon_apis():
    """Test all admin addon API endpoints"""
    print("🧪 Testing Admin Addon APIs...")
    print("=" * 50)
    
    # Setup
    client = APIClient()
    
    # Create admin user
    admin_user = User.objects.create_user(
        username='admin@test.com',
        email='admin@test.com',
        password='adminpass123',
        first_name='Admin',
        last_name='User',
        user_type='admin',
        is_staff=True,
        is_superuser=True
    )
    
    # Create test data
    region = Region.objects.create(
        name='Test Region',
        code='TEST',
        is_active=True
    )
    
    category = Category.objects.create(
        name='Test Category',
        description='Test category for addons',
        region=region,
        is_active=True
    )
    
    # Authenticate as admin
    client.force_authenticate(user=admin_user)
    
    test_results = []
    
    # Test 1: List Addons
    print("\n1️⃣ Testing List Addons API...")
    try:
        response = client.get('/api/v1/admin/addons/')
        if response.status_code == 200:
            print(f"✅ List Addons: SUCCESS (Status: {response.status_code})")
            print(f"   Found {len(response.data)} addons")
            test_results.append(("List Addons", True, response.status_code))
        else:
            print(f"❌ List Addons: FAILED (Status: {response.status_code})")
            print(f"   Response: {response.data}")
            test_results.append(("List Addons", False, response.status_code))
    except Exception as e:
        print(f"❌ List Addons: ERROR - {str(e)}")
        test_results.append(("List Addons", False, f"Error: {str(e)}"))
    
    # Test 2: Create Addon
    print("\n2️⃣ Testing Create Addon API...")
    try:
        addon_data = {
            'name': 'Test Addon',
            'description': 'A test addon for API testing',
            'categories': [category.id],
            'region': region.id,
            'price': '25.00',
            'duration_minutes': 30,
            'is_active': True,
            'max_quantity': 5
        }
        
        response = client.post('/api/v1/admin/addons/', addon_data, format='json')
        if response.status_code == 201:
            print(f"✅ Create Addon: SUCCESS (Status: {response.status_code})")
            print(f"   Created addon ID: {response.data['id']}")
            print(f"   Name: {response.data['name']}")
            print(f"   Price: {response.data['price']}")
            addon_id = response.data['id']
            test_results.append(("Create Addon", True, response.status_code))
        else:
            print(f"❌ Create Addon: FAILED (Status: {response.status_code})")
            print(f"   Response: {response.data}")
            test_results.append(("Create Addon", False, response.status_code))
            addon_id = None
    except Exception as e:
        print(f"❌ Create Addon: ERROR - {str(e)}")
        test_results.append(("Create Addon", False, f"Error: {str(e)}"))
        addon_id = None
    
    # Test 3: Get Addon Detail
    if addon_id:
        print(f"\n3️⃣ Testing Get Addon Detail API (ID: {addon_id})...")
        try:
            response = client.get(f'/api/v1/admin/addons/{addon_id}/')
            if response.status_code == 200:
                print(f"✅ Get Addon Detail: SUCCESS (Status: {response.status_code})")
                print(f"   Name: {response.data['name']}")
                print(f"   Price: {response.data['price']}")
                print(f"   Region: {response.data['region_name']}")
                print(f"   Categories: {response.data['categories_names']}")
                test_results.append(("Get Addon Detail", True, response.status_code))
            else:
                print(f"❌ Get Addon Detail: FAILED (Status: {response.status_code})")
                print(f"   Response: {response.data}")
                test_results.append(("Get Addon Detail", False, response.status_code))
        except Exception as e:
            print(f"❌ Get Addon Detail: ERROR - {str(e)}")
            test_results.append(("Get Addon Detail", False, f"Error: {str(e)}"))
    
    # Test 4: Update Addon
    if addon_id:
        print(f"\n4️⃣ Testing Update Addon API (ID: {addon_id})...")
        try:
            update_data = {
                'name': 'Updated Test Addon',
                'description': 'Updated description for the test addon',
                'categories': [category.id],
                'region': region.id,
                'price': '35.00',
                'duration_minutes': 45,
                'is_active': True,
                'max_quantity': 10
            }
            
            response = client.put(f'/api/v1/admin/addons/{addon_id}/', update_data, format='json')
            if response.status_code == 200:
                print(f"✅ Update Addon: SUCCESS (Status: {response.status_code})")
                print(f"   Updated name: {response.data['name']}")
                print(f"   Updated price: {response.data['price']}")
                print(f"   Updated duration: {response.data['duration_minutes']} minutes")
                test_results.append(("Update Addon", True, response.status_code))
            else:
                print(f"❌ Update Addon: FAILED (Status: {response.status_code})")
                print(f"   Response: {response.data}")
                test_results.append(("Update Addon", False, response.status_code))
        except Exception as e:
            print(f"❌ Update Addon: ERROR - {str(e)}")
            test_results.append(("Update Addon", False, f"Error: {str(e)}"))
    
    # Test 5: Partial Update Addon
    if addon_id:
        print(f"\n5️⃣ Testing Partial Update Addon API (ID: {addon_id})...")
        try:
            partial_data = {
                'price': '40.00',
                'max_quantity': 15
            }
            
            response = client.patch(f'/api/v1/admin/addons/{addon_id}/', partial_data, format='json')
            if response.status_code == 200:
                print(f"✅ Partial Update Addon: SUCCESS (Status: {response.status_code})")
                print(f"   Updated price: {response.data['price']}")
                print(f"   Updated max_quantity: {response.data['max_quantity']}")
                test_results.append(("Partial Update Addon", True, response.status_code))
            else:
                print(f"❌ Partial Update Addon: FAILED (Status: {response.status_code})")
                print(f"   Response: {response.data}")
                test_results.append(("Partial Update Addon", False, response.status_code))
        except Exception as e:
            print(f"❌ Partial Update Addon: ERROR - {str(e)}")
            test_results.append(("Partial Update Addon", False, f"Error: {str(e)}"))
    
    # Test 6: Delete Addon
    if addon_id:
        print(f"\n6️⃣ Testing Delete Addon API (ID: {addon_id})...")
        try:
            response = client.delete(f'/api/v1/admin/addons/{addon_id}/')
            if response.status_code == 204:
                print(f"✅ Delete Addon: SUCCESS (Status: {response.status_code})")
                print(f"   Addon deleted successfully")
                test_results.append(("Delete Addon", True, response.status_code))
            else:
                print(f"❌ Delete Addon: FAILED (Status: {response.status_code})")
                print(f"   Response: {response.data}")
                test_results.append(("Delete Addon", False, response.status_code))
        except Exception as e:
            print(f"❌ Delete Addon: ERROR - {str(e)}")
            test_results.append(("Delete Addon", False, f"Error: {str(e)}"))
    
    # Test 7: Create Addon with Form Data
    print("\n7️⃣ Testing Create Addon with Form Data...")
    try:
        addon_form_data = {
            'name': 'Form Data Addon',
            'description': 'Addon created with form data',
            'categories': [category.id],
            'region': region.id,
            'price': '50.00',
            'duration_minutes': 60,
            'is_active': True,
            'max_quantity': 3
        }
        
        response = client.post('/api/v1/admin/addons/', addon_form_data, format='multipart')
        if response.status_code == 201:
            print(f"✅ Create Addon (Form Data): SUCCESS (Status: {response.status_code})")
            print(f"   Created addon ID: {response.data['id']}")
            print(f"   Name: {response.data['name']}")
            test_results.append(("Create Addon (Form Data)", True, response.status_code))
            
            # Clean up
            form_addon_id = response.data['id']
            client.delete(f'/api/v1/admin/addons/{form_addon_id}/')
        else:
            print(f"❌ Create Addon (Form Data): FAILED (Status: {response.status_code})")
            print(f"   Response: {response.data}")
            test_results.append(("Create Addon (Form Data)", False, response.status_code))
    except Exception as e:
        print(f"❌ Create Addon (Form Data): ERROR - {str(e)}")
        test_results.append(("Create Addon (Form Data)", False, f"Error: {str(e)}"))
    
    # Test 8: Filter and Search Addons
    print("\n8️⃣ Testing Filter and Search Addons...")
    try:
        # Test filtering by region
        response = client.get(f'/api/v1/admin/addons/?region={region.id}')
        if response.status_code == 200:
            print(f"✅ Filter by Region: SUCCESS (Status: {response.status_code})")
            print(f"   Found {len(response.data)} addons in region")
            test_results.append(("Filter by Region", True, response.status_code))
        else:
            print(f"❌ Filter by Region: FAILED (Status: {response.status_code})")
            test_results.append(("Filter by Region", False, response.status_code))
        
        # Test filtering by active status
        response = client.get('/api/v1/admin/addons/?is_active=true')
        if response.status_code == 200:
            print(f"✅ Filter by Active Status: SUCCESS (Status: {response.status_code})")
            print(f"   Found {len(response.data)} active addons")
            test_results.append(("Filter by Active Status", True, response.status_code))
        else:
            print(f"❌ Filter by Active Status: FAILED (Status: {response.status_code})")
            test_results.append(("Filter by Active Status", False, response.status_code))
            
    except Exception as e:
        print(f"❌ Filter and Search: ERROR - {str(e)}")
        test_results.append(("Filter and Search", False, f"Error: {str(e)}"))
    
    # Summary
    print("\n" + "=" * 50)
    print("📊 ADMIN ADDON API TEST RESULTS")
    print("=" * 50)
    
    passed = 0
    total = len(test_results)
    
    for test_name, success, status_code in test_results:
        status_icon = "✅" if success else "❌"
        print(f"{status_icon} {test_name}: {'PASS' if success else 'FAIL'} ({status_code})")
        if success:
            passed += 1
    
    print(f"\n🎯 Overall Result: {passed}/{total} tests passed ({passed/total*100:.1f}%)")
    
    if passed == total:
        print("🎉 All Admin Addon APIs are working correctly!")
        print("✅ Ready for production use")
    else:
        print("⚠️  Some tests failed. Please review the errors above.")
    
    # Cleanup
    try:
        admin_user.delete()
        region.delete()
        category.delete()
    except:
        pass
    
    return passed == total

if __name__ == '__main__':
    success = test_admin_addon_apis()
    sys.exit(0 if success else 1) 