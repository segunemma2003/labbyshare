# apps/services/models.py
from django.db import models
from django.core.cache import cache
from django.conf import settings
from decimal import Decimal


class CategoryManager(models.Manager):
    """
    Custom manager for categories with region-based caching
    """
    def get_categories_by_region(self, region):
        """Get categories for a specific region with caching"""
        cache_key = settings.CACHE_KEYS['CATEGORIES'].format(region.id)
        categories = cache.get(cache_key)
        
        if categories is None:
            categories = list(
                self.filter(region=region, is_active=True)
                .order_by('sort_order', 'name')
                .values('id', 'name', 'description', 'icon', 'sort_order', 'is_featured')
            )
            cache.set(cache_key, categories, settings.CACHE_TIMEOUTS['CATEGORIES'])
        
        return categories


class Category(models.Model):
    """
    Service categories - region specific (Hair, Beauty, Wellness, etc.)
    """
    name = models.CharField(max_length=200, db_index=True)
    description = models.TextField(blank=True)
    icon = models.ImageField(upload_to='category_icons/', blank=True, null=True)
    
    # Regional relationship
    region = models.ForeignKey(
        'regions.Region', 
        on_delete=models.CASCADE, 
        db_index=True,
        related_name='categories'
    )
    
    # Display and status
    is_active = models.BooleanField(default=True, db_index=True)
    is_featured = models.BooleanField(default=False, db_index=True)
    sort_order = models.IntegerField(default=0, db_index=True)
    
    # SEO and metadata
    slug = models.SlugField(max_length=250, blank=True)
    meta_description = models.TextField(blank=True, max_length=160)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    objects = CategoryManager()
    
    class Meta:
        unique_together = ['name', 'region']
        indexes = [
            models.Index(fields=['region', 'is_active', 'sort_order']),
            models.Index(fields=['region', 'name']),
            models.Index(fields=['slug', 'region']),
        ]
        verbose_name_plural = "Categories"
        ordering = ['sort_order', 'name']
    
    def __str__(self):
        region_code = self.region.code if self.region else "No Region"
        return f"{self.name} - {region_code}"
    
    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        # Clear cache when category is updated
        cache_key = settings.CACHE_KEYS['CATEGORIES'].format(self.region.id)
        cache.delete(cache_key)
        # Clear featured categories cache
        featured_cache_key = f"featured_categories_{self.region.id}"
        cache.delete(featured_cache_key)


class ServiceManager(models.Manager):
    """
    Custom manager for services with region and category filtering
    """
    def get_services_by_region_category(self, region, category_id=None):
        """Get services for region/category with caching"""
        cache_key = settings.CACHE_KEYS['SERVICES'].format(region.id, category_id or 'all')
        services = cache.get(cache_key)
        
        if services is None:
            queryset = self.filter(category__region=region, is_active=True)
            if category_id:
                queryset = queryset.filter(category_id=category_id)
            
            services = list(
                queryset.select_related('category')
                .order_by('sort_order', 'name')
                .values(
                    'id', 'name', 'description', 'base_price', 
                    'duration_minutes', 'category__name', 'sort_order'
                )
            )
            cache.set(cache_key, services, settings.CACHE_TIMEOUTS['SERVICES'])
        
        return services


class Service(models.Model):
    """
    Individual services with regional pricing
    """
    name = models.CharField(max_length=200, db_index=True)
    description = models.TextField()
    category = models.ForeignKey(
        Category, 
        on_delete=models.CASCADE, 
        related_name='services',
        db_index=True
    )
    
    # Base pricing (can be overridden by regional pricing)
    base_price = models.DecimalField(max_digits=10, decimal_places=2, db_index=True)
    duration_minutes = models.IntegerField(db_index=True)  # Service duration
    
    # Service details
    preparation_time = models.IntegerField(default=0)  # Minutes before service
    cleanup_time = models.IntegerField(default=0)      # Minutes after service
    
    # Display and status
    is_active = models.BooleanField(default=True, db_index=True)
    sort_order = models.IntegerField(default=0, db_index=True)
    is_featured = models.BooleanField(default=False, db_index=True)
    
    # Media
    image = models.ImageField(upload_to='service_images/', blank=True, null=True)
    
    # SEO
    slug = models.SlugField(max_length=250, blank=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    objects = ServiceManager()
    
    class Meta:
        unique_together = ['name', 'category']
        indexes = [
            models.Index(fields=['category', 'is_active', 'sort_order']),
            models.Index(fields=['category', 'is_featured']),
            models.Index(fields=['base_price', 'category']),
            models.Index(fields=['duration_minutes']),
            models.Index(fields=['slug', 'category']),
        ]
        ordering = ['sort_order', 'name']
    
    def __str__(self):
        region_code = self.category.region.code if self.category and self.category.region else "No Region"
        return f"{self.name} - {self.category.name} - {region_code}"
    
    def get_regional_price(self, region):
        """Get price for specific region"""
        try:
            regional_pricing = self.regional_pricing.get(region=region)
            return regional_pricing.price
        except RegionalPricing.DoesNotExist:
            return self.base_price
    
    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        # Clear cache when service is updated
        region_id = self.category.region.id
        cache.delete(settings.CACHE_KEYS['SERVICES'].format(region_id, 'all'))
        cache.delete(settings.CACHE_KEYS['SERVICES'].format(region_id, self.category.id))


class RegionalPricing(models.Model):
    """
    Region-specific pricing for services
    """
    service = models.ForeignKey(
        Service, 
        on_delete=models.CASCADE, 
        related_name='regional_pricing'
    )
    region = models.ForeignKey('regions.Region', on_delete=models.CASCADE)
    price = models.DecimalField(max_digits=10, decimal_places=2, db_index=True)
    is_active = models.BooleanField(default=True, db_index=True)
    
    # Promotional pricing
    promotional_price = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        blank=True, 
        null=True
    )
    promotion_start = models.DateTimeField(blank=True, null=True)
    promotion_end = models.DateTimeField(blank=True, null=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ['service', 'region']
        indexes = [
            models.Index(fields=['region', 'is_active']),
            models.Index(fields=['service', 'region']),
            models.Index(fields=['promotion_start', 'promotion_end']),
        ]
    
    def get_current_price(self):
        """Get current price considering promotions"""
        from django.utils import timezone
        now = timezone.now()
        
        if (self.promotional_price and 
            self.promotion_start and self.promotion_end and
            self.promotion_start <= now <= self.promotion_end):
            return self.promotional_price
        
        return self.price
    
    def __str__(self):
        region_code = self.region.code if self.region else "No Region"
        return f"{self.service.name} - {region_code}: {self.price}"


class AddOn(models.Model):
    """
    Service add-ons (regional, can be linked to multiple categories or none)
    """
    name = models.CharField(max_length=200, db_index=True)
    description = models.TextField(blank=True)
    categories = models.ManyToManyField(
        Category,
        related_name='addons',
        blank=True
    )
    region = models.ForeignKey(
        'regions.Region',
        on_delete=models.CASCADE,
        db_index=True,
        related_name='addons',
        null=True,
        blank=True
    )
    price = models.DecimalField(max_digits=10, decimal_places=2, db_index=True)
    duration_minutes = models.IntegerField(default=0)  # Additional time
    is_active = models.BooleanField(default=True, db_index=True)
    max_quantity = models.IntegerField(default=1)  # Max quantity per booking
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=['region', 'is_active']),
            models.Index(fields=['price']),
        ]
        ordering = ['name']

    def __str__(self):
        region_code = self.region.code if self.region else "No Region"
        return f"{self.name} - {region_code}"


class ServiceImage(models.Model):
    """
    Multiple images for services
    """
    service = models.ForeignKey(
        Service, 
        on_delete=models.CASCADE, 
        related_name='images'
    )
    image = models.ImageField(upload_to='service_images/')
    alt_text = models.CharField(max_length=200, blank=True)
    is_primary = models.BooleanField(default=False)
    sort_order = models.IntegerField(default=0)
    
    class Meta:
        indexes = [
            models.Index(fields=['service', 'is_primary']),
            models.Index(fields=['service', 'sort_order']),
        ]
        ordering = ['sort_order']
    
    def __str__(self):
        service_name = self.service.name if self.service else "No Service"
        return f"Image for {service_name}"


class ServiceReview(models.Model):
    """
    Reviews and ratings for services
    """
    service = models.ForeignKey(
        Service, 
        on_delete=models.CASCADE, 
        related_name='service_reviews'  # Changed from 'reviews' to 'service_reviews'
    )
    user = models.ForeignKey(
        'accounts.User', 
        on_delete=models.CASCADE,
        related_name='service_reviews'  # Also change this to avoid conflicts
    )
    rating = models.IntegerField(
        choices=[(i, i) for i in range(1, 6)],
        db_index=True
    )  # 1-5 stars
    comment = models.TextField(blank=True)
    
    # Review status
    is_verified = models.BooleanField(default=False)
    is_published = models.BooleanField(default=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ['service', 'user']
        indexes = [
            models.Index(fields=['service', 'rating']),
            models.Index(fields=['service', 'is_published', 'created_at']),
            models.Index(fields=['user', 'created_at']),
        ]
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.user.get_full_name()} - {self.service.name} ({self.rating}★)"
