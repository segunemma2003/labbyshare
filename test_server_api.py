#!/usr/bin/env python3
"""
Test API on live server with form_data
"""
import requests
import json
import time

def test_server_api():
    """Test CREATE and UPDATE operations on live server"""
    print("🌐 Testing API on live server...")
    
    # Server details
    base_url = "https://backend.beautyspabyshea.co.uk/api/v1"
    token = "ac4447ad45db9a025cd0272db850d862678220ed"
    
    headers = {
        'Authorization': f'Token {token}',
        'Content-Type': 'multipart/form-data'
    }
    
    # Test 1: GET professionals list
    print("\n📋 Test 1: GET professionals list")
    try:
        response = requests.get(f"{base_url}/admin/professionals/", headers={'Authorization': f'Token {token}'})
        print(f"Status: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"Found {len(data.get('results', []))} professionals")
        else:
            print(f"Error: {response.text}")
    except Exception as e:
        print(f"Error: {e}")
    
    # Test 2: CREATE professional with form_data (basic fields)
    print("\n📝 Test 2: CREATE professional with form_data (basic fields)")
    timestamp = int(time.time())
    create_data = {
        'first_name': f'ServerTest{timestamp}',
        'last_name': 'User',
        'email': f'servertest{timestamp}@test.com',
        'password': 'testpassword123',
        'bio': 'Professional created via server API test',
        'experience_years': 5,
        'is_verified': True,
        'is_active': True,
        'travel_radius_km': 10,
        'min_booking_notice_hours': 24,
        'regions': [1],
        'services': [1]
    }
    
    try:
        response = requests.post(
            f"{base_url}/admin/professionals/",
            data=create_data,
            headers={'Authorization': f'Token {token}'}
        )
        print(f"Status: {response.status_code}")
        if response.status_code == 201:
            data = response.json()
            professional_id = data.get('id')
            print(f"✅ Created professional with ID: {professional_id}")
            print(f"Name: {data.get('user', {}).get('first_name')} {data.get('user', {}).get('last_name')}")
        else:
            print(f"Error: {response.text}")
            return
    except Exception as e:
        print(f"Error: {e}")
        return
    
    # Test 3: UPDATE professional (basic fields)
    print(f"\n📝 Test 3: UPDATE professional {professional_id} (basic fields)")
    update_data = {
        'bio': 'Updated bio via server API test',
        'experience_years': 7,
        'travel_radius_km': 15
    }
    
    try:
        response = requests.put(
            f"{base_url}/admin/professionals/{professional_id}/",
            data=update_data,
            headers={'Authorization': f'Token {token}'}
        )
        print(f"Status: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Updated professional successfully")
            print(f"New bio: {data.get('bio')}")
            print(f"New experience: {data.get('experience_years')} years")
        else:
            print(f"Error: {response.text}")
    except Exception as e:
        print(f"Error: {e}")
    
    # Test 4: UPDATE professional (with availability)
    print(f"\n📝 Test 4: UPDATE professional {professional_id} (with availability)")
    update_data_with_availability = {
        'bio': 'Updated with availability via server API test',
        'availability[0][region_id]': '1',
        'availability[0][weekday]': '1',
        'availability[0][start_time]': '09:00',
        'availability[0][end_time]': '17:00',
        'availability[0][break_start]': '12:00',
        'availability[0][break_end]': '13:00',
        'availability[0][is_active]': 'true'
    }
    
    try:
        response = requests.put(
            f"{base_url}/admin/professionals/{professional_id}/",
            data=update_data_with_availability,
            headers={'Authorization': f'Token {token}'}
        )
        print(f"Status: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Updated professional with availability successfully")
            print(f"New bio: {data.get('bio')}")
            availability = data.get('availability', [])
            print(f"Availability count: {len(availability)}")
            if availability:
                print(f"First availability: {availability[0]}")
        else:
            print(f"Error: {response.text}")
    except Exception as e:
        print(f"Error: {e}")
    
    # Test 5: UPDATE regions and services
    print(f"\n📝 Test 5: UPDATE professional {professional_id} (regions and services)")
    update_regions_services = {
        'regions': [1],
        'services': [1]
    }
    
    try:
        response = requests.put(
            f"{base_url}/admin/professionals/{professional_id}/",
            data=update_regions_services,
            headers={'Authorization': f'Token {token}'}
        )
        print(f"Status: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Updated regions and services successfully")
            regions = data.get('regions', [])
            services = data.get('services', [])
            print(f"Regions count: {len(regions)}")
            print(f"Services count: {len(services)}")
        else:
            print(f"Error: {response.text}")
    except Exception as e:
        print(f"Error: {e}")
    
    print("\n🎉 Server API testing completed!")

if __name__ == "__main__":
    test_server_api() 