#!/usr/bin/env python3
"""
Detailed test API on live server with form_data
"""
import requests
import json
import time

def test_server_detailed():
    """Test with detailed debugging on live server"""
    print("🔍 Detailed testing API on live server...")
    
    # Server details
    base_url = "https://backend.beautyspabyshea.co.uk/api/v1"
    token = "ac4447ad45db9a025cd0272db850d862678220ed"
    
    # Test 1: GET existing professional to see current state
    print("\n📋 Test 1: GET existing professional")
    try:
        response = requests.get(f"{base_url}/admin/professionals/1/", headers={'Authorization': f'Token {token}'})
        print(f"Status: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"Professional ID: {data.get('id')}")
            print(f"Bio: {data.get('bio')}")
            print(f"Regions count: {len(data.get('regions', []))}")
            print(f"Services count: {len(data.get('services', []))}")
            print(f"Availability count: {len(data.get('availability', []))}")
            print(f"Regions: {data.get('regions')}")
            print(f"Services: {data.get('services')}")
            print(f"Availability: {data.get('availability')}")
        else:
            print(f"Error: {response.text}")
    except Exception as e:
        print(f"Error: {e}")
    
    # Test 2: UPDATE existing professional with availability
    print("\n📝 Test 2: UPDATE existing professional with availability")
    update_data = {
        'bio': 'Updated via detailed server test',
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
            f"{base_url}/admin/professionals/1/",
            data=update_data,
            headers={'Authorization': f'Token {token}'}
        )
        print(f"Status: {response.status_code}")
        print(f"Response: {response.text}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Updated professional successfully")
            print(f"New bio: {data.get('bio')}")
            availability = data.get('availability', [])
            print(f"Availability count: {len(availability)}")
            print(f"Availability: {availability}")
        else:
            print(f"❌ Update failed")
    except Exception as e:
        print(f"Error: {e}")
    
    # Test 3: UPDATE with regions and services
    print("\n📝 Test 3: UPDATE with regions and services")
    update_data = {
        'bio': 'Updated with regions and services',
        'regions': [1],
        'services': [1]
    }
    
    try:
        response = requests.put(
            f"{base_url}/admin/professionals/1/",
            data=update_data,
            headers={'Authorization': f'Token {token}'}
        )
        print(f"Status: {response.status_code}")
        print(f"Response: {response.text}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Updated regions and services successfully")
            regions = data.get('regions', [])
            services = data.get('services', [])
            print(f"Regions count: {len(regions)}")
            print(f"Services count: {len(services)}")
            print(f"Regions: {regions}")
            print(f"Services: {services}")
        else:
            print(f"❌ Update failed")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_server_detailed() 