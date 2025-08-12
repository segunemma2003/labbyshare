#!/usr/bin/env python3
"""
Fix ProfessionalService relationship
"""
import os
import sys
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'labmyshare.local_settings')
django.setup()

from professionals.models import Professional, ProfessionalService
from services.models import Service
from regions.models import Region

def fix_professional_service():
    """Fix ProfessionalService relationship"""
    print("🔧 Fixing ProfessionalService relationship...")
    
    # Get objects
    professional = Professional.objects.first()
    service = Service.objects.first()
    region = Region.objects.first()
    
    print(f"Professional: {professional.user.get_full_name()}")
    print(f"Service: {service.name}")
    print(f"Region: {region.name}")
    
    # Delete existing ProfessionalService objects for this professional
    ProfessionalService.objects.filter(professional=professional).delete()
    print("🗑️ Deleted existing ProfessionalService objects")
    
    # Create new ProfessionalService
    ps = ProfessionalService.objects.create(
        professional=professional,
        service=service,
        region=region,
        custom_price=50.00,
        is_active=True
    )
    print(f"✅ Created ProfessionalService: {ps}")
    
    # Verify the relationship
    services = professional.services.all()
    print(f"Professional services: {[s.name for s in services]}")
    
    regions = professional.regions.all()
    print(f"Professional regions: {[r.name for r in regions]}")
    
    # Test the validation query
    try:
        test_ps = ProfessionalService.objects.get(
            professional=professional,
            service=service,
            region=region
        )
        print(f"✅ Validation query works: {test_ps}")
    except ProfessionalService.DoesNotExist:
        print("❌ Validation query still fails")

if __name__ == "__main__":
    fix_professional_service() 