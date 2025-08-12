#!/usr/bin/env python3
"""
Check ProfessionalService relationship
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

def check_professional_service():
    """Check ProfessionalService relationship"""
    print("🔍 Checking ProfessionalService relationship...")
    
    # Get objects
    professional = Professional.objects.first()
    service = Service.objects.first()
    region = Region.objects.first()
    
    print(f"Professional: {professional.user.get_full_name()}")
    print(f"Service: {service.name}")
    print(f"Region: {region.name}")
    
    # Check ProfessionalService
    try:
        ps = ProfessionalService.objects.get(
            professional=professional,
            service=service,
            region=region
        )
        print(f"✅ ProfessionalService exists: {ps}")
    except ProfessionalService.DoesNotExist:
        print("❌ ProfessionalService does not exist")
    
    # Check professional.services
    services = professional.services.all()
    print(f"Professional services: {[s.name for s in services]}")
    
    # Check professional.regions
    regions = professional.regions.all()
    print(f"Professional regions: {[r.name for r in regions]}")
    
    # Check all ProfessionalService objects
    all_ps = ProfessionalService.objects.all()
    print(f"All ProfessionalService objects: {list(all_ps)}")

if __name__ == "__main__":
    check_professional_service() 