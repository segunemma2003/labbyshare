from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone
from decimal import Decimal
import uuid


class ProfessionalManager(models.Manager):
    """
    Custom manager for professionals with region-based queries
    """
    def get_active_professionals(self, region=None, service=None):
        """Get active verified professionals"""
        queryset = self.filter(is_active=True, is_verified=True)
        
        if region:
            queryset = queryset.filter(regions=region)
        
        if service:
            queryset = queryset.filter(services=service)
        
        return queryset.select_related('user').prefetch_related('regions', 'services')
    
    def get_top_rated(self, region=None, limit=10):
        """Get top rated professionals"""
        queryset = self.get_active_professionals(region)
        return queryset.filter(rating__gte=4.0).order_by('-rating', '-total_reviews')[:limit]


class Professional(models.Model):
    """
    Professional service provider model
    """
    user = models.OneToOneField(
        'accounts.User', 
        on_delete=models.CASCADE, 
        related_name='professional_profile'
    )
    
    # Professional info
    bio = models.TextField(blank=True)
    experience_years = models.IntegerField(
        default=0,
        validators=[MinValueValidator(0), MaxValueValidator(50)]
    )
    
    # Rating and reviews
    rating = models.DecimalField(
        max_digits=3, 
        decimal_places=2, 
        default=0.00,
        validators=[MinValueValidator(0), MaxValueValidator(5)]
    )
    total_reviews = models.IntegerField(default=0)
    
    # Verification and status
    is_verified = models.BooleanField(default=False, db_index=True)
    is_active = models.BooleanField(default=True, db_index=True)
    verification_documents = models.JSONField(default=list, blank=True)
    
    # Service areas and specializations
    regions = models.ManyToManyField(
        'regions.Region', 
        related_name='professionals',
        through='ProfessionalRegion'
    )
    services = models.ManyToManyField(
        'services.Service', 
        related_name='professionals',
        through='ProfessionalService'
    )
    
    # Business settings
    travel_radius_km = models.IntegerField(default=10)
    min_booking_notice_hours = models.IntegerField(default=24)
    cancellation_policy = models.TextField(blank=True)
    
    # Financial
    commission_rate = models.DecimalField(
        max_digits=5, 
        decimal_places=2, 
        default=15.00
    )  # Platform commission %
    
    # Profile completion
    profile_completed = models.BooleanField(default=False)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    verified_at = models.DateTimeField(null=True, blank=True)
    
    objects = ProfessionalManager()
    
    class Meta:
        indexes = [
            models.Index(fields=['is_active', 'is_verified', 'rating']),
            models.Index(fields=['rating', 'total_reviews']),
            models.Index(fields=['created_at']),
        ]
    
    def __str__(self):
        return f"{self.user.get_full_name()} - Professional"
    
    def update_rating(self):
        """Update professional rating based on reviews"""
        from bookings.models import Review
        reviews = Review.objects.filter(
            professional=self, 
            is_published=True
        )
        
        if reviews.exists():
            avg_rating = reviews.aggregate(avg=models.Avg('overall_rating'))['avg']
            self.rating = round(avg_rating, 2)
            self.total_reviews = reviews.count()
        else:
            self.rating = 0.00
            self.total_reviews = 0
        
        self.save(update_fields=['rating', 'total_reviews'])
    
    def get_availability_for_date(self, date, region):
        """Get availability slots for specific date"""
        weekday = date.weekday()
        return self.availability_schedule.filter(
            region=region,
            weekday=weekday,
            is_active=True
        )
    
    def is_available(self, date, time, duration_minutes, region):
        """Check if professional is available for booking"""
        # Check general availability
        availability = self.get_availability_for_date(date, region)
        if not availability.exists():
            return False
        
        # Check specific time slot
        end_time = (timezone.datetime.combine(date, time) + 
                   timezone.timedelta(minutes=duration_minutes)).time()
        
        valid_slots = availability.filter(
            start_time__lte=time,
            end_time__gte=end_time
        )
        
        if not valid_slots.exists():
            return False

        # Check for unavailability
        unavailabilities = self.unavailable_dates.filter(
            region=region,
            date=date
        )
        for unavail in unavailabilities:
            # If start_time and end_time are null, unavailable all day
            if unavail.start_time is None and unavail.end_time is None:
                return False
            # If only one is null, treat as all day
            if unavail.start_time is None or unavail.end_time is None:
                return False
            # Check for overlap with unavailable time
            if (time < unavail.end_time and end_time > unavail.start_time):
                return False
        
        # Check for existing bookings
        from bookings.models import Booking
        existing_bookings = Booking.objects.filter(
            professional=self,
            scheduled_date=date,
            status__in=['confirmed', 'in_progress']
        )
        
        for booking in existing_bookings:
            booking_start = booking.scheduled_time
            booking_end = (timezone.datetime.combine(date, booking_start) + 
                          timezone.timedelta(minutes=booking.duration_minutes)).time()
            
            # Check for overlap
            if (time < booking_end and end_time > booking_start):
                return False
        
        return True


class ProfessionalRegion(models.Model):
    """
    Through model for professional-region relationship
    """
    professional = models.ForeignKey(Professional, on_delete=models.CASCADE)
    region = models.ForeignKey('regions.Region', on_delete=models.CASCADE)
    is_primary = models.BooleanField(default=False)
    travel_fee = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        default=0.00
    )
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ['professional', 'region']


class ProfessionalService(models.Model):
    """
    Through model for professional-service relationship with custom pricing
    """
    professional = models.ForeignKey(Professional, on_delete=models.CASCADE)
    service = models.ForeignKey('services.Service', on_delete=models.CASCADE)
    region = models.ForeignKey('regions.Region', on_delete=models.CASCADE)
    
    # Custom pricing
    custom_price = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        null=True, 
        blank=True
    )
    is_active = models.BooleanField(default=True)
    
    # Service-specific settings
    preparation_time_minutes = models.IntegerField(default=0)
    cleanup_time_minutes = models.IntegerField(default=0)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ['professional', 'service', 'region']
        indexes = [
            models.Index(fields=['professional', 'region', 'is_active']),
        ]
    
    def get_price(self):
        """Get effective price for this service"""
        if self.custom_price:
            return self.custom_price
        
        # Get regional pricing or base price
        return self.service.get_regional_price(self.region)


class ProfessionalAvailability(models.Model):
    """
    Professional availability schedule
    """
    WEEKDAY_CHOICES = [
        (0, 'Monday'), (1, 'Tuesday'), (2, 'Wednesday'),
        (3, 'Thursday'), (4, 'Friday'), (5, 'Saturday'), (6, 'Sunday')
    ]
    
    professional = models.ForeignKey(
        Professional, 
        on_delete=models.CASCADE, 
        related_name='availability_schedule'
    )
    region = models.ForeignKey('regions.Region', on_delete=models.CASCADE)
    
    weekday = models.IntegerField(choices=WEEKDAY_CHOICES, db_index=True)
    start_time = models.TimeField()
    end_time = models.TimeField()
    
    is_active = models.BooleanField(default=True)
    
    # Break times
    break_start = models.TimeField(null=True, blank=True)
    break_end = models.TimeField(null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ['professional', 'region', 'weekday', 'start_time']
        indexes = [
            models.Index(fields=['professional', 'region', 'weekday', 'is_active']),
        ]
    
    def __str__(self):
        weekday_name = dict(self.WEEKDAY_CHOICES)[self.weekday]
        return f"{self.professional.user.get_full_name()} - {weekday_name} {self.start_time}-{self.end_time}"


class ProfessionalUnavailability(models.Model):
    """
    Specific dates when professional is unavailable
    """
    professional = models.ForeignKey(
        Professional, 
        on_delete=models.CASCADE, 
        related_name='unavailable_dates'
    )
    region = models.ForeignKey('regions.Region', on_delete=models.CASCADE)
    
    date = models.DateField(db_index=True)
    start_time = models.TimeField(null=True, blank=True)  # Null = all day
    end_time = models.TimeField(null=True, blank=True)
    
    reason = models.CharField(max_length=200, blank=True)
    is_recurring = models.BooleanField(default=False)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ['professional', 'region', 'date', 'start_time']
        indexes = [
            models.Index(fields=['professional', 'date']),
            models.Index(fields=['date', 'is_recurring']),
        ]


class ProfessionalDocument(models.Model):
    """
    Professional verification documents
    """
    DOCUMENT_TYPES = [
        ('id', 'ID/Passport'),
        ('certificate', 'Professional Certificate'),
        ('license', 'License'),
        ('insurance', 'Insurance Certificate'),
        ('portfolio', 'Portfolio/Work Sample')
    ]
    
    professional = models.ForeignKey(
        Professional, 
        on_delete=models.CASCADE, 
        related_name='documents'
    )
    
    document_type = models.CharField(max_length=20, choices=DOCUMENT_TYPES)
    document_file = models.FileField(upload_to='professional_documents/')
    description = models.CharField(max_length=200, blank=True)
    
    # Verification status
    is_verified = models.BooleanField(default=False)
    verified_by = models.ForeignKey(
        'accounts.User', 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True
    )
    verified_at = models.DateTimeField(null=True, blank=True)
    verification_notes = models.TextField(blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        indexes = [
            models.Index(fields=['professional', 'document_type']),
            models.Index(fields=['is_verified']),
        ]
    
    def __str__(self):
        return f"{self.professional.user.get_full_name()} - {self.get_document_type_display()}"