#!/usr/bin/env python3
"""
Test script to debug professional registration process
"""
import os
import sys
import django
import logging
from datetime import time

# Add the project directory to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'labmyshare.settings')
django.setup()

from accounts.models import User
from professionals.models import Professional, ProfessionalService, ProfessionalAvailability
from regions.models import Region
from services.models import Service, Category
from professionals.serializers import ProfessionalRegistrationSerializer
from rest_framework.test import APIRequestFactory

def test_professional_registration():
    """Test the professional registration process"""
    
    print("🧪 Testing Professional Registration Process")
    print("=" * 60)
    
    # Setup logging
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)
    
    try:
        # Get test data
        regions = Region.objects.filter(is_active=True)[:2]
        categories = Category.objects.filter(is_active=True)[:2]
        services = Service.objects.filter(category__in=categories, is_active=True)[:3]
        
        if not regions.exists():
            print("❌ No active regions found")
            return
        
        if not services.exists():
            print("❌ No active services found")
            return
        
        print(f"✅ Found {regions.count()} regions and {services.count()} services")
        
        # Create a test user
        test_email = f"test_professional_{int(time.time())}@example.com"
        user = User.objects.create_user(
            username=test_email,
            email=test_email,
            first_name="Test",
            last_name="Professional",
            password="testpass123"
        )
        
        print(f"✅ Created test user: {user.email}")
        
        # Prepare registration data
        registration_data = {
            'bio': 'Test professional bio',
            'experience_years': 5,
            'travel_radius_km': 15,
            'min_booking_notice_hours': 24,
            'cancellation_policy': '24 hours notice required',
            'regions': [regions[0].id, regions[1].id],
            'services': [services[0].id, services[1].id],
            'availability': [
                {
                    'region_id': regions[0].id,
                    'weekday': 0,  # Monday
                    'start_time': '09:00:00',
                    'end_time': '17:00:00',
                    'break_start': '12:00:00',
                    'break_end': '13:00:00',
                    'is_active': True
                },
                {
                    'region_id': regions[1].id,
                    'weekday': 1,  # Tuesday
                    'start_time': '10:00:00',
                    'end_time': '18:00:00',
                    'is_active': True
                }
            ]
        }
        
        print("📋 Registration data prepared:")
        print(f"   - Regions: {[r.name for r in regions]}")
        print(f"   - Services: {[s.name for s in services]}")
        print(f"   - Availability entries: {len(registration_data['availability'])}")
        
        # Create API request context
        factory = APIRequestFactory()
        request = factory.post('/test/')
        request.user = user
        
        # Test serializer
        serializer = ProfessionalRegistrationSerializer(
            data=registration_data,
            context={'request': request}
        )
        
        if serializer.is_valid():
            print("✅ Serializer validation passed")
            
            # Create professional
            professional = serializer.save()
            print(f"✅ Professional created with ID: {professional.id}")
            
            # Verify what was saved
            print("\n🔍 Verifying saved data:")
            
            # Check regions
            saved_regions = professional.regions.all()
            print(f"   - Regions saved: {saved_regions.count()}")
            for region in saved_regions:
                print(f"     * {region.name} ({region.code})")
            
            # Check services
            saved_services = professional.services.all()
            print(f"   - Services saved: {saved_services.count()}")
            for service in saved_services:
                print(f"     * {service.name}")
            
            # Check ProfessionalService entries
            professional_services = ProfessionalService.objects.filter(professional=professional)
            print(f"   - ProfessionalService entries: {professional_services.count()}")
            for ps in professional_services:
                print(f"     * {ps.service.name} in {ps.region.name} (Price: {ps.get_price()})")
            
            # Check availability
            availability_entries = ProfessionalAvailability.objects.filter(professional=professional)
            print(f"   - Availability entries: {availability_entries.count()}")
            for avail in availability_entries:
                weekday_name = dict(ProfessionalAvailability.WEEKDAY_CHOICES)[avail.weekday]
                print(f"     * {weekday_name} in {avail.region.name}: {avail.start_time}-{avail.end_time}")
            
            # Cleanup
            professional.delete()
            user.delete()
            print("\n🧹 Test data cleaned up")
            
        else:
            print("❌ Serializer validation failed:")
            for field, errors in serializer.errors.items():
                print(f"   - {field}: {errors}")
    
    except Exception as e:
        print(f"❌ Test failed with error: {str(e)}")
        import traceback
        print(f"Traceback: {traceback.format_exc()}")

if __name__ == "__main__":
    test_professional_registration() 
"""
Test script to debug professional registration process
"""
import os
import sys
import django
import logging
from datetime import time

# Add the project directory to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'labmyshare.settings')
django.setup()

from accounts.models import User
from professionals.models import Professional, ProfessionalService, ProfessionalAvailability
from regions.models import Region
from services.models import Service, Category
from professionals.serializers import ProfessionalRegistrationSerializer
from rest_framework.test import APIRequestFactory

def test_professional_registration():
    """Test the professional registration process"""
    
    print("🧪 Testing Professional Registration Process")
    print("=" * 60)
    
    # Setup logging
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)
    
    try:
        # Get test data
        regions = Region.objects.filter(is_active=True)[:2]
        categories = Category.objects.filter(is_active=True)[:2]
        services = Service.objects.filter(category__in=categories, is_active=True)[:3]
        
        if not regions.exists():
            print("❌ No active regions found")
            return
        
        if not services.exists():
            print("❌ No active services found")
            return
        
        print(f"✅ Found {regions.count()} regions and {services.count()} services")
        
        # Create a test user
        test_email = f"test_professional_{int(time.time())}@example.com"
        user = User.objects.create_user(
            username=test_email,
            email=test_email,
            first_name="Test",
            last_name="Professional",
            password="testpass123"
        )
        
        print(f"✅ Created test user: {user.email}")
        
        # Prepare registration data
        registration_data = {
            'bio': 'Test professional bio',
            'experience_years': 5,
            'travel_radius_km': 15,
            'min_booking_notice_hours': 24,
            'cancellation_policy': '24 hours notice required',
            'regions': [regions[0].id, regions[1].id],
            'services': [services[0].id, services[1].id],
            'availability': [
                {
                    'region_id': regions[0].id,
                    'weekday': 0,  # Monday
                    'start_time': '09:00:00',
                    'end_time': '17:00:00',
                    'break_start': '12:00:00',
                    'break_end': '13:00:00',
                    'is_active': True
                },
                {
                    'region_id': regions[1].id,
                    'weekday': 1,  # Tuesday
                    'start_time': '10:00:00',
                    'end_time': '18:00:00',
                    'is_active': True
                }
            ]
        }
        
        print("📋 Registration data prepared:")
        print(f"   - Regions: {[r.name for r in regions]}")
        print(f"   - Services: {[s.name for s in services]}")
        print(f"   - Availability entries: {len(registration_data['availability'])}")
        
        # Create API request context
        factory = APIRequestFactory()
        request = factory.post('/test/')
        request.user = user
        
        # Test serializer
        serializer = ProfessionalRegistrationSerializer(
            data=registration_data,
            context={'request': request}
        )
        
        if serializer.is_valid():
            print("✅ Serializer validation passed")
            
            # Create professional
            professional = serializer.save()
            print(f"✅ Professional created with ID: {professional.id}")
            
            # Verify what was saved
            print("\n🔍 Verifying saved data:")
            
            # Check regions
            saved_regions = professional.regions.all()
            print(f"   - Regions saved: {saved_regions.count()}")
            for region in saved_regions:
                print(f"     * {region.name} ({region.code})")
            
            # Check services
            saved_services = professional.services.all()
            print(f"   - Services saved: {saved_services.count()}")
            for service in saved_services:
                print(f"     * {service.name}")
            
            # Check ProfessionalService entries
            professional_services = ProfessionalService.objects.filter(professional=professional)
            print(f"   - ProfessionalService entries: {professional_services.count()}")
            for ps in professional_services:
                print(f"     * {ps.service.name} in {ps.region.name} (Price: {ps.get_price()})")
            
            # Check availability
            availability_entries = ProfessionalAvailability.objects.filter(professional=professional)
            print(f"   - Availability entries: {availability_entries.count()}")
            for avail in availability_entries:
                weekday_name = dict(ProfessionalAvailability.WEEKDAY_CHOICES)[avail.weekday]
                print(f"     * {weekday_name} in {avail.region.name}: {avail.start_time}-{avail.end_time}")
            
            # Cleanup
            professional.delete()
            user.delete()
            print("\n🧹 Test data cleaned up")
            
        else:
            print("❌ Serializer validation failed:")
            for field, errors in serializer.errors.items():
                print(f"   - {field}: {errors}")
    
    except Exception as e:
        print(f"❌ Test failed with error: {str(e)}")
        import traceback
        print(f"Traceback: {traceback.format_exc()}")

if __name__ == "__main__":
    test_professional_registration() 
 