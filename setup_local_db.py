#!/usr/bin/env python3
"""
Setup local SQLite database with test data for debugging
"""
import os
import sys
import django
from django.core.management import execute_from_command_line

# Add the project directory to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def setup_local_database():
    """Setup local SQLite database with test data"""
    print("🔧 Setting up local SQLite database for debugging...")
    
    # Set Django settings to use local settings
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'labmyshare.local_settings')
    
    # Setup Django
    django.setup()
    
    # Create logs directory
    from pathlib import Path
    logs_dir = Path(__file__).resolve().parent / 'logs'
    logs_dir.mkdir(exist_ok=True)
    
    print("📁 Created logs directory")
    
    # Run migrations
    print("🔄 Running migrations...")
    execute_from_command_line(['manage.py', 'makemigrations'])
    execute_from_command_line(['manage.py', 'migrate'])
    
    # Create superuser if it doesn't exist
    print("👤 Creating superuser...")
    try:
        from django.contrib.auth import get_user_model
        User = get_user_model()
        
        if not User.objects.filter(is_superuser=True).exists():
            User.objects.create_superuser(
                username='admin',
                email='admin@labmyshare.com',
                password='admin123'
            )
            print("✅ Created superuser: admin@labmyshare.com / admin123")
        else:
            print("✅ Superuser already exists")
    except Exception as e:
        print(f"⚠️ Could not create superuser: {e}")
    
    # Create test data
    print("📊 Creating test data...")
    try:
        from regions.models import Region
        from services.models import Service, Category, AddOn
        from accounts.models import User
        from professionals.models import Professional
        
        # Create regions
        if not Region.objects.exists():
            uk_region = Region.objects.create(
                name="United Kingdom",
                code="UK",
                is_active=True
            )
            print(f"✅ Created region: {uk_region.name}")
        
        # Create categories and services
        if not Category.objects.exists():
            category = Category.objects.create(
                name="Test Category",
                description="Test category for debugging",
                region=Region.objects.first()
            )
            print(f"✅ Created category: {category.name}")
        
        if not Service.objects.exists():
            service = Service.objects.create(
                name="Test Service",
                description="A test service for debugging",
                category=Category.objects.first(),
                base_price=100.00,
                duration_minutes=60,
                is_active=True
            )
            print(f"✅ Created service: {service.name}")
        
        # Create addons
        if not AddOn.objects.exists():
            addon = AddOn.objects.create(
                name="Test Addon",
                description="A test addon for debugging",
                region=Region.objects.first(),
                price=25.00,
                duration_minutes=15,
                is_active=True
            )
            print(f"✅ Created addon: {addon.name}")
        
        # Create test professional
        if not Professional.objects.exists():
            user = User.objects.create_user(
                username='test_professional',
                email='professional@test.com',
                password='test123',
                first_name='Test',
                last_name='Professional',
                user_type='professional'
            )
            
            professional = Professional.objects.create(
                user=user,
                bio="Test professional for debugging",
                experience_years=5,
                is_verified=True,
                is_active=True,
                travel_radius_km=10,
                min_booking_notice_hours=24
            )
            
            # Add regions and services
            professional.regions.add(Region.objects.first())
            professional.services.add(Service.objects.first())
            from professionals.models import ProfessionalService
            ProfessionalService.objects.create(
                professional=professional,
                service=Service.objects.first(),
                region=Region.objects.first(),
                custom_price=50.00,
                is_active=True
            )
            
            print(f"✅ Created professional: {professional.user.email}")
        
        # Ensure ProfessionalService exists for existing professional
        if Professional.objects.exists() and Service.objects.exists() and Region.objects.exists():
            from professionals.models import ProfessionalService
            if not ProfessionalService.objects.exists():
                professional = Professional.objects.first()
                service = Service.objects.first()
                region = Region.objects.first()
                
                # Add services and regions to professional
                professional.services.add(service)
                professional.regions.add(region)
                
                ProfessionalService.objects.create(
                    professional=professional,
                    service=service,
                    region=region,
                    custom_price=50.00,
                    is_active=True
                )
                print(f"✅ Created ProfessionalService for {professional.user.email}")
        
        print("✅ Test data created successfully!")
        
    except Exception as e:
        print(f"⚠️ Could not create test data: {e}")
        import traceback
        traceback.print_exc()
    
    print("\n🎉 Local database setup complete!")
    print("📁 Database: db.sqlite3")
    print("📁 Logs: logs/debug.log")
    print("🔗 Run server: python manage.py runserver --settings=labmyshare.local_settings")
    print("👤 Admin: admin@labmyshare.com / admin123")
    print("👨‍💼 Professional: professional@test.com / test123")

if __name__ == "__main__":
    setup_local_database() 