from django.core.management.base import BaseCommand
from django.utils import timezone
from faker import Faker
import random
from decimal import Decimal
from datetime import timedelta

from apps.accounts.models import User
from apps.regions.models import Region
from apps.services.models import Category, Service
from apps.professionals.models import Professional, ProfessionalAvailability
from apps.bookings.models import Booking


class Command(BaseCommand):
    help = 'Generate test data for development and testing'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--users',
            type=int,
            default=100,
            help='Number of users to create',
        )
        parser.add_argument(
            '--professionals',
            type=int,
            default=20,
            help='Number of professionals to create',
        )
        parser.add_argument(
            '--bookings',
            type=int,
            default=200,
            help='Number of bookings to create',
        )
    
    def handle(self, *args, **options):
        fake = Faker()
        
        regions = list(Region.objects.all())
        if not regions:
            self.stdout.write(self.style.ERROR('No regions found. Run create_initial_data first.'))
            return
        
        # Create users
        self.stdout.write(f'Creating {options["users"]} users...')
        users = []
        for i in range(options['users']):
            user = User.objects.create_user(
                username=fake.user_name() + str(i),
                email=fake.email(),
                password='testpass123',
                first_name=fake.first_name(),
                last_name=fake.last_name(),
                current_region=random.choice(regions),
                user_type='customer',
                phone_number=fake.phone_number()[:15],
                date_of_birth=fake.date_of_birth(minimum_age=18, maximum_age=80),
                gender=random.choice(['M', 'F', 'O']),
                is_verified=True
            )
            users.append(user)
        
        # Create professionals
        self.stdout.write(f'Creating {options["professionals"]} professionals...')
        professionals = []
        categories = list(Category.objects.all())
        
        for i in range(options['professionals']):
            user = User.objects.create_user(
                username=fake.user_name() + '_pro' + str(i),
                email=fake.email(),
                password='testpass123',
                first_name=fake.first_name(),
                last_name=fake.last_name(),
                current_region=random.choice(regions),
                user_type='professional',
                phone_number=fake.phone_number()[:15],
                is_verified=True
            )
            
            professional = Professional.objects.create(
                user=user,
                bio=fake.text(max_nb_chars=500),
                experience_years=random.randint(1, 20),
                rating=Decimal(str(round(random.uniform(3.5, 5.0), 2))),
                total_reviews=random.randint(10, 100),
                is_verified=True,
                is_active=True
            )
            
            # Add to random regions
            selected_regions = random.sample(regions, random.randint(1, len(regions)))
            professional.regions.set(selected_regions)
            
            # Add services
            for region in selected_regions:
                region_categories = categories if categories else []
                selected_categories = random.sample(
                    region_categories, 
                    min(random.randint(1, 3), len(region_categories))
                )
                
                for category in selected_categories:
                    services = list(category.services.filter(is_active=True))
                    if services:
                        selected_services = random.sample(
                            services,
                            min(random.randint(1, 3), len(services))
                        )
                        professional.services.set(selected_services)
            
            # Create availability
            for region in selected_regions:
                for day in range(5):  # Monday to Friday
                    ProfessionalAvailability.objects.create(
                        professional=professional,
                        region=region,
                        weekday=day,
                        start_time='09:00:00',
                        end_time='17:00:00'
                    )
            
            professionals.append(professional)
        
        # Create bookings
        self.stdout.write(f'Creating {options["bookings"]} bookings...')
        services = list(Service.objects.all())
        
        for i in range(options['bookings']):
            customer = random.choice(users)
            professional = random.choice(professionals)
            service = random.choice(services)
            
            # Random date in the past or future
            scheduled_date = fake.date_between(
                start_date='-30d',
                end_date='+30d'
            )
            
            status_choices = ['pending', 'confirmed', 'completed', 'cancelled']
            booking_status = random.choice(status_choices)
            
            booking = Booking.objects.create(
                customer=customer,
                professional=professional,
                service=service,
                region=customer.current_region,
                scheduled_date=scheduled_date,
                scheduled_time=fake.time(),
                duration_minutes=service.duration_minutes,
                base_amount=service.base_price,
                total_amount=service.base_price * Decimal(str(random.uniform(1.0, 1.5))),
                status=booking_status,
                booking_for_self=random.choice([True, False]),
                customer_notes=fake.text(max_nb_chars=200) if random.choice([True, False]) else ''
            )
            
            if booking_status == 'confirmed':
                booking.confirmed_at = timezone.now()
                booking.save()
            elif booking_status == 'completed':
                booking.confirmed_at = timezone.now() - timedelta(days=1)
                booking.completed_at = timezone.now()
                booking.save()
        
        self.stdout.write(
            self.style.SUCCESS(
                f'Successfully created {options["users"]} users, '
                f'{options["professionals"]} professionals, and '
                f'{options["bookings"]} bookings!'
            )
        )