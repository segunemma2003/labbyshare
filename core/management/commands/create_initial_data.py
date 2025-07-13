"""
Management command to create initial system data
"""
from django.core.management.base import BaseCommand
from django.utils import timezone
from regions.models import Region, RegionalSettings
from services.models import Category
from accounts.models import User
from professionals.models import Professional


class Command(BaseCommand):
    help = 'Create initial system data for LabMyShare'
    
    def handle(self, *args, **options):
        self.stdout.write('Creating initial system data...')
        
        # Create regions
        self.create_regions()
        
        # Create categories
        self.create_categories()
        
        # Create admin user
        self.create_admin_user()
        
        self.stdout.write(
            self.style.SUCCESS('Successfully created initial system data!')
        )
    
    def create_regions(self):
        """Create initial regions"""
        regions_data = [
            {
                'code': 'UK',
                'name': 'United Kingdom',
                'currency': 'GBP',
                'currency_symbol': '£',
                'timezone': 'Europe/London',
                'country_code': 'GB',
                'default_tax_rate': 20.00,
                'support_email': 'support-uk@labmyshare.com',
                'support_phone': '+44 20 7946 0958'
            },
            {
                'code': 'UAE',
                'name': 'United Arab Emirates',
                'currency': 'AED',
                'currency_symbol': 'د.إ',
                'timezone': 'Asia/Dubai',
                'country_code': 'AE',
                'default_tax_rate': 5.00,
                'support_email': 'support-uae@labmyshare.com',
                'support_phone': '+971 4 123 4567'
            }
        ]
        
        for region_data in regions_data:
            region, created = Region.objects.get_or_create(
                code=region_data['code'],
                defaults=region_data
            )
            if created:
                self.stdout.write(f'Created region: {region.name}')
                
                # Create regional settings
                self.create_regional_settings(region)
            else:
                self.stdout.write(f'Region already exists: {region.name}')
    
    def create_regional_settings(self, region):
        """Create regional settings"""
        settings_data = [
            {
                'key': 'booking_cancellation_hours',
                'value': '24',
                'value_type': 'integer',
                'description': 'Minimum hours before appointment to allow cancellation'
            },
            {
                'key': 'default_deposit_percentage',
                'value': '20.00',
                'value_type': 'float',
                'description': 'Default deposit percentage for bookings'
            },
            {
                'key': 'max_booking_days_ahead',
                'value': '90',
                'value_type': 'integer',
                'description': 'Maximum days ahead customers can book'
            },
            {
                'key': 'professional_commission_rate',
                'value': '15.00',
                'value_type': 'float',
                'description': 'Default commission rate for professionals'
            }
        ]
        
        for setting_data in settings_data:
            RegionalSettings.objects.get_or_create(
                region=region,
                key=setting_data['key'],
                defaults=setting_data
            )
    
    def create_categories(self):
        """Create initial service categories"""
        categories_data = [
            {
                'name': 'Hair Services',
                'description': 'Professional hair cutting, styling, coloring, and treatments'
            },
            {
                'name': 'Beauty Services',
                'description': 'Makeup, skincare, facial treatments, and beauty consultations'
            },
            {
                'name': 'Nail Services',
                'description': 'Manicures, pedicures, nail art, and nail treatments'
            },
            {
                'name': 'Massage & Wellness',
                'description': 'Therapeutic massage, aromatherapy, and wellness treatments'
            },
            {
                'name': 'Personal Training',
                'description': 'Fitness coaching, workout sessions, and health consultations'
            },
            {
                'name': 'Home Services',
                'description': 'Cleaning, maintenance, and household assistance services'
            }
        ]
        
        regions = Region.objects.all()
        
        for region in regions:
            for i, category_data in enumerate(categories_data):
                category, created = Category.objects.get_or_create(
                    name=category_data['name'],
                    region=region,
                    defaults={
                        'description': category_data['description'],
                        'sort_order': i + 1,
                        'is_active': True
                    }
                )
                if created:
                    self.stdout.write(f'Created category: {category.name} for {region.name}')
    
    def create_admin_user(self):
        """Create admin user if it doesn't exist"""
        admin_email = 'admin@labmyshare.com'
        
        if not User.objects.filter(email=admin_email).exists():
            admin_user = User.objects.create_user(
                username='admin',
                email=admin_email,
                password='admin123',
                first_name='System',
                last_name='Administrator',
                user_type='super_admin',
                is_verified=True,
                is_staff=True,
                is_superuser=True
            )
            
            # Set current region to UK by default
            uk_region = Region.objects.filter(code='UK').first()
            if uk_region:
                admin_user.current_region = uk_region
                admin_user.save()
            
            self.stdout.write(
                self.style.SUCCESS(f'Created admin user: {admin_email} / admin123')
            )
        else:
            self.stdout.write('Admin user already exists')
