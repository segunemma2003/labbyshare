# apps/regions/models.py
from django.db import models
from django.core.cache import cache
from django.conf import settings
from decimal import Decimal


class RegionManager(models.Manager):
    """
    Custom manager with caching for regions
    """
    def get_active_regions(self):
        """Get all active regions with caching"""
        cache_key = settings.CACHE_KEYS['REGIONS']
        regions_data = cache.get(cache_key)
        
        if regions_data is None:
            # Get the actual model objects, don't cache them
            regions = list(self.filter(is_active=True).order_by('name'))
            return regions
        
        # If we have cached data, we need to reconstruct objects from cache
        # But it's better to just return fresh objects for this method
        return list(self.filter(is_active=True).order_by('name'))
    
    def get_region_by_code(self, code):
        """Get region by code - don't cache model objects"""
        try:
            return self.get(code=code, is_active=True)
        except self.model.DoesNotExist:
            return None


class Region(models.Model):
    """
    Region model for multi-location support (UK, UAE, etc.)
    """
    code = models.CharField(max_length=10, unique=True, db_index=True)  # UK, UAE
    name = models.CharField(max_length=100)
    currency = models.CharField(max_length=10, default='USD')
    currency_symbol = models.CharField(max_length=5, default='$')
    timezone = models.CharField(max_length=50, default='UTC')
    country_code = models.CharField(max_length=2, db_index=True)  # GB, AE
    
    # Operational settings
    is_active = models.BooleanField(default=True, db_index=True)
    default_tax_rate = models.DecimalField(max_digits=5, decimal_places=4, default=Decimal('0.0000'))
    
    # Business hours (default for the region)
    business_start_time = models.TimeField(default='09:00:00')
    business_end_time = models.TimeField(default='18:00:00')
    
    # Contact and support
    support_email = models.EmailField(blank=True)
    support_phone = models.CharField(max_length=20, blank=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    objects = RegionManager()
    
    class Meta:
        indexes = [
            models.Index(fields=['code', 'is_active']),
            models.Index(fields=['country_code', 'is_active']),
        ]
        ordering = ['name']
    
    def __str__(self):
        return f"{self.name} ({self.code})"
    
    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        # Clear cache when region is updated
        cache.delete(settings.CACHE_KEYS['REGIONS'])
        # Clear individual region cache too
        cache.delete(f"region:code:{self.code}")


class RegionalSettings(models.Model):
    """
    Regional configuration settings
    """
    region = models.ForeignKey(Region, on_delete=models.CASCADE, related_name='settings')
    key = models.CharField(max_length=100)
    value = models.TextField()
    value_type = models.CharField(
        max_length=20,
        choices=[
            ('string', 'String'),
            ('integer', 'Integer'),
            ('float', 'Float'),
            ('boolean', 'Boolean'),
            ('json', 'JSON'),
        ],
        default='string'
    )
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ['region', 'key']
        indexes = [
            models.Index(fields=['region', 'key']),
        ]
    
    def get_value(self):
        """Convert value based on type"""
        if self.value_type == 'integer':
            return int(self.value)
        elif self.value_type == 'float':
            return float(self.value)
        elif self.value_type == 'boolean':
            return self.value.lower() in ['true', '1', 'yes']
        elif self.value_type == 'json':
            import json
            return json.loads(self.value)
        return self.value
    
    def __str__(self):
        return f"{self.region.code} - {self.key}"