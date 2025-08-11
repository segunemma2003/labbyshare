#!/usr/bin/env python3
"""
Test script for admin professional update data processing
"""

import os
import sys
import django
from datetime import datetime

# Add the project directory to Python path
sys.path.append('/Users/segun/Documents/projects/demi/labbyshare/labmyshare')

# Set up Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'labmyshare.settings')

# Disable Celery import for testing
os.environ['CELERY_DISABLED'] = '1'

try:
    django.setup()
except Exception as e:
    print(f"Warning: Django setup failed: {e}")
    print("Continuing with basic data processing test...")

def test_update_data_processing():
    """Test the update data processing logic"""
    
    # Simulate the multipart form data from your payload
    data = {
        'first_name': 'test',
        'last_name': 'test',
        'email': 'testmain@g.com',
        'phone_number': '+23485495402344',
        'date_of_birth': '2025-08-13',
        'gender': 'F',
        'user_is_active': 'true',  # String boolean
        'bio': 'aretrwewr',
        'experience_years': '0',
        'travel_radius_km': '10',
        'min_booking_notice_hours': '24',
        'commission_rate': '15.00',
        'is_verified': 'true',  # String boolean
        'is_active': 'true',  # String boolean
        'regions[]': '1',
        'services[]': '32',
        'availability[0][region_id]': '1',
        'availability[0][weekday]': '0',
        'availability[0][start_time]': '09:00',
        'availability[0][end_time]': '17:00',
        'availability[0][break_start]': '14:18',
        'availability[0][break_end]': '15:18',
        'availability[0][is_active]': 'true'
    }
    
    print("🔍 Testing update data processing logic...")
    print(f"📝 Input data keys: {list(data.keys())}")
    
    # Test boolean field processing
    print("\n🔧 Testing boolean field processing...")
    boolean_fields = ['user_is_active', 'is_verified', 'is_active']
    for field in boolean_fields:
        if field in data:
            value = data[field]
            if isinstance(value, str):
                result = value.lower() == 'true'
                print(f"✅ {field}: '{value}' -> {result}")
            elif isinstance(value, (list, tuple)) and len(value) == 1:
                result = value[0].lower() == 'true'
                print(f"✅ {field}: {value} -> {result}")
            else:
                print(f"❌ {field}: Unexpected type {type(value)}")
    
    # Test services processing
    print("\n🔧 Testing services processing...")
    services_data = data.get('services[]')
    if services_data:
        if not isinstance(services_data, (list, tuple)):
            services_data = [services_data]
        try:
            service_ids = [int(sid) for sid in services_data if sid]
            print(f"✅ Services IDs: {service_ids}")
        except (ValueError, TypeError) as e:
            print(f"❌ Error processing services: {e}")
    
    # Test regions processing  
    print("\n🌍 Testing regions processing...")
    regions_data = data.get('regions[]')
    if regions_data:
        if not isinstance(regions_data, (list, tuple)):
            regions_data = [regions_data]
        try:
            region_ids = [int(rid) for rid in regions_data if rid]
            print(f"✅ Region IDs: {region_ids}")
        except (ValueError, TypeError) as e:
            print(f"❌ Error processing regions: {e}")
    
    # Test availability processing
    print("\n⏰ Testing availability processing...")
    availability_data = []
    i = 0
    while f'availability[{i}][region_id]' in data:
        try:
            # Get the raw time values
            start_time_str = data.get(f'availability[{i}][start_time]')
            end_time_str = data.get(f'availability[{i}][end_time]')
            break_start_str = data.get(f'availability[{i}][break_start]')
            break_end_str = data.get(f'availability[{i}][break_end]')
            
            # Convert time strings to time objects
            start_time = None
            end_time = None
            break_start = None
            break_end = None
            
            if start_time_str:
                try:
                    start_time = datetime.strptime(start_time_str, '%H:%M:%S').time()
                except ValueError:
                    try:
                        start_time = datetime.strptime(start_time_str, '%H:%M').time()
                    except ValueError:
                        print(f"❌ Invalid start_time format: {start_time_str}")
                        break
            
            if end_time_str:
                try:
                    end_time = datetime.strptime(end_time_str, '%H:%M:%S').time()
                except ValueError:
                    try:
                        end_time = datetime.strptime(end_time_str, '%H:%M').time()
                    except ValueError:
                        print(f"❌ Invalid end_time format: {end_time_str}")
                        break
            
            if break_start_str:
                try:
                    break_start = datetime.strptime(break_start_str, '%H:%M:%S').time()
                except ValueError:
                    try:
                        break_start = datetime.strptime(break_start_str, '%H:%M').time()
                    except ValueError:
                        print(f"⚠️ Invalid break_start format: {break_start_str}, setting to None")
                        break_start = None
            
            if break_end_str:
                try:
                    break_end = datetime.strptime(break_end_str, '%H:%M:%S').time()
                except ValueError:
                    try:
                        break_end = datetime.strptime(break_end_str, '%H:%M').time()
                    except ValueError:
                        print(f"⚠️ Invalid break_end format: {break_end_str}, setting to None")
                        break_end = None
            
            availability_item = {
                'region_id': int(data.get(f'availability[{i}][region_id]')),
                'weekday': int(data.get(f'availability[{i}][weekday]')),
                'start_time': start_time,
                'end_time': end_time,
                'break_start': break_start,
                'break_end': break_end,
                'is_active': data.get(f'availability[{i}][is_active]', 'true').lower() == 'true'
            }
            
            # Validate that required fields are present
            if (availability_item['region_id'] is not None and 
                availability_item['weekday'] is not None and
                availability_item['start_time'] and 
                availability_item['end_time']):
                
                # Validate that end_time is after start_time
                if availability_item['end_time'] <= availability_item['start_time']:
                    print(f"❌ End time must be after start time for availability item {i}")
                    break
                
                availability_data.append(availability_item)
                print(f"✅ Added availability item {i}: {availability_item}")
            else:
                print(f"❌ Missing required fields for availability item {i}")
                print(f"   region_id: {availability_item['region_id']}")
                print(f"   weekday: {availability_item['weekday']}")
                print(f"   start_time: {availability_item['start_time']}")
                print(f"   end_time: {availability_item['end_time']}")
                break
            
        except (ValueError, TypeError) as e:
            print(f"❌ Error processing availability item {i}: {e}")
            break
        
        i += 1
    
    if availability_data:
        print(f"\n✅ Processed {len(availability_data)} availability items")
        for i, item in enumerate(availability_data):
            print(f"   Item {i}: {item}")
    else:
        print("\n❌ No availability data processed")
    
    print("\n🎯 Update data processing test completed!")

if __name__ == "__main__":
    test_update_data_processing() 