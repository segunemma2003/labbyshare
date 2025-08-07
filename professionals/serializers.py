from services.models import Service
from regions.models import Region
from rest_framework import serializers
from django.utils import timezone
from datetime import datetime, timedelta
from decimal import Decimal

from .models import (
    Professional, ProfessionalAvailability, ProfessionalUnavailability,
    ProfessionalService, ProfessionalDocument
)
from accounts.serializers import UserSerializer
from regions.serializers import RegionSerializer
from services.serializers import ServiceSerializer


class ProfessionalServiceSerializer(serializers.ModelSerializer):
    """
    Professional service with custom pricing
    """
    service = ServiceSerializer(read_only=True)
    effective_price = serializers.SerializerMethodField()
    
    class Meta:
        model = ProfessionalService
        fields = [
            'id', 'service', 'custom_price', 'effective_price',
            'preparation_time_minutes', 'cleanup_time_minutes', 'is_active'
        ]
    
    def get_effective_price(self, obj):
        return float(obj.get_price())


class ProfessionalAvailabilitySerializer(serializers.ModelSerializer):
    """
    Professional availability schedule
    """
    weekday_name = serializers.CharField(source='get_weekday_display', read_only=True)
    
    class Meta:
        model = ProfessionalAvailability
        fields = [
            'id', 'weekday', 'weekday_name', 'start_time', 'end_time',
            'break_start', 'break_end', 'is_active'
        ]


class ProfessionalListSerializer(serializers.ModelSerializer):
    """
    Professional list serializer for search results
    """
    user = UserSerializer(read_only=True)
    services_count = serializers.SerializerMethodField()
    regions_served = serializers.SerializerMethodField()
    
    class Meta:
        model = Professional
        fields = [
            'id', 'user', 'bio', 'experience_years', 'rating', 'total_reviews',
            'is_verified', 'services_count', 'regions_served', 'travel_radius_km'
        ]
    
    def get_services_count(self, obj):
        return obj.services.filter(professionalservice__is_active=True).count()
    
    def get_regions_served(self, obj):
        regions = obj.regions.all()
        return RegionSerializer(regions, many=True).data


class ProfessionalDetailSerializer(serializers.ModelSerializer):
    """
    Detailed professional profile
    """
    user = UserSerializer(read_only=True)
    services = serializers.SerializerMethodField()
    availability = serializers.SerializerMethodField()
    regions_served = RegionSerializer(source='regions', many=True, read_only=True)
    reviews_summary = serializers.SerializerMethodField()
    
    class Meta:
        model = Professional
        fields = [
            'id', 'user', 'bio', 'experience_years', 'rating', 'total_reviews',
            'is_verified', 'travel_radius_km', 'min_booking_notice_hours',
            'cancellation_policy', 'services', 'availability', 'regions_served',
            'reviews_summary', 'profile_completed', 'created_at'
        ]
    
    def get_services(self, obj):
        region = self.context.get('region')
        if region:
            professional_services = obj.professionalservice_set.filter(
                region=region, 
                is_active=True
            ).select_related('service')
            return ProfessionalServiceSerializer(professional_services, many=True).data
        return []
    
    def get_availability(self, obj):
        region = self.context.get('region')
        if region:
            availability = obj.availability_schedule.filter(
                region=region, 
                is_active=True
            ).order_by('weekday', 'start_time')
            return ProfessionalAvailabilitySerializer(availability, many=True).data
        return []
    
    def get_reviews_summary(self, obj):
        from bookings.models import Review
        reviews = Review.objects.filter(
            professional=obj, 
            is_published=True
        )
        
        if reviews.exists():
            ratings = reviews.values_list('overall_rating', flat=True)
            return {
                'average_rating': float(obj.rating),
                'total_reviews': obj.total_reviews,
                'rating_distribution': {
                    '5': reviews.filter(overall_rating=5).count(),
                    '4': reviews.filter(overall_rating=4).count(),
                    '3': reviews.filter(overall_rating=3).count(),
                    '2': reviews.filter(overall_rating=2).count(),
                    '1': reviews.filter(overall_rating=1).count(),
                }
            }
        return {
            'average_rating': 0,
            'total_reviews': 0,
            'rating_distribution': {'5': 0, '4': 0, '3': 0, '2': 0, '1': 0}
        }


class ProfessionalRegistrationSerializer(serializers.ModelSerializer):
    """
    Professional registration/profile setup
    """
    regions = serializers.PrimaryKeyRelatedField(
        queryset=Region.objects.none(),  # Temporary empty queryset
        many=True
    )
    services = serializers.PrimaryKeyRelatedField(
        queryset=Service.objects.none(),  # Temporary empty queryset - FIXED
        many=True
    )
    
    # Availability data
    availability = serializers.ListField(
        child=serializers.DictField(),
        required=False,
        help_text="List of availability objects with region_id, weekday, start_time, end_time, etc."
    )
    
    class Meta:
        model = Professional
        fields = [
            'bio', 'experience_years', 'travel_radius_km',
            'min_booking_notice_hours', 'cancellation_policy',
            'regions', 'services', 'availability'
        ]
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from regions.models import Region
        from services.models import Service
        
        self.fields['regions'].queryset = Region.objects.filter(is_active=True)
        self.fields['services'].queryset = Service.objects.filter(is_active=True)
    
    def validate_availability(self, value):
        """Validate availability data"""
        if not value:
            return value
        
        for item in value:
            # Check required fields
            required_fields = ['region_id', 'weekday', 'start_time', 'end_time']
            for field in required_fields:
                if field not in item:
                    raise serializers.ValidationError(f"Missing required field: {field}")
            
            # Validate weekday
            weekday = item.get('weekday')
            if not isinstance(weekday, int) or weekday < 0 or weekday > 6:
                raise serializers.ValidationError("Weekday must be an integer between 0 and 6")
            
            # Validate times
            try:
                start_time = item.get('start_time')
                end_time = item.get('end_time')
                
                if start_time >= end_time:
                    raise serializers.ValidationError("End time must be after start time")
                
                # Validate break times if provided
                break_start = item.get('break_start')
                break_end = item.get('break_end')
                
                if break_start and break_end:
                    if break_start >= break_end:
                        raise serializers.ValidationError("Break end time must be after break start time")
                    
                    if not (start_time <= break_start <= break_end <= end_time):
                        raise serializers.ValidationError("Break times must be within working hours")
                        
            except (TypeError, AttributeError):
                raise serializers.ValidationError("Invalid time format")
        
        return value
    
    def create(self, validated_data):
        regions = validated_data.pop('regions')
        services = validated_data.pop('services')
        availability_data = validated_data.pop('availability', [])
        user = self.context['request'].user
        
        # Create professional profile
        professional = Professional.objects.create(
            user=user,
            **validated_data
        )
        
        # Set regions and services
        professional.regions.set(regions)
        
        # Create ProfessionalService entries for each region-service combination
        for region in regions:
            for service in services:
                ProfessionalService.objects.create(
                    professional=professional,
                    service=service,
                    region=region
                )
        
        # Create availability entries
        for availability_item in availability_data:
            try:
                region_id = availability_item.get('region_id')
                if region_id:
                    region = Region.objects.get(id=region_id)
                    ProfessionalAvailability.objects.create(
                        professional=professional,
                        region=region,
                        weekday=availability_item.get('weekday', 0),
                        start_time=availability_item.get('start_time'),
                        end_time=availability_item.get('end_time'),
                        break_start=availability_item.get('break_start'),
                        break_end=availability_item.get('break_end'),
                        is_active=availability_item.get('is_active', True)
                    )
            except (Region.DoesNotExist, KeyError, ValueError):
                # Skip invalid availability data
                continue
        
        return professional


class AvailabilityCreateSerializer(serializers.ModelSerializer):
    """
    Create/update professional availability
    """
    class Meta:
        model = ProfessionalAvailability
        fields = [
            'weekday', 'start_time', 'end_time', 'break_start', 'break_end'
        ]
    
    def validate(self, attrs):
        """Validate time ranges"""
        start_time = attrs['start_time']
        end_time = attrs['end_time']
        break_start = attrs.get('break_start')
        break_end = attrs.get('break_end')
        
        if start_time >= end_time:
            raise serializers.ValidationError("End time must be after start time")
        
        if break_start and break_end:
            if break_start >= break_end:
                raise serializers.ValidationError("Break end time must be after break start time")
            
            if not (start_time <= break_start <= break_end <= end_time):
                raise serializers.ValidationError("Break times must be within working hours")
        
        return attrs
    
    def create(self, validated_data):
        professional = self.context['professional']
        region = self.context['region']
        
        return ProfessionalAvailability.objects.create(
            professional=professional,
            region=region,
            **validated_data
        )


class UnavailabilitySerializer(serializers.ModelSerializer):
    """
    Professional unavailability dates
    """
    class Meta:
        model = ProfessionalUnavailability
        fields = [
            'id', 'date', 'start_time', 'end_time', 'reason', 'is_recurring'
        ]
    
    def validate_date(self, value):
        """Validate date is not in the past"""
        if value < timezone.now().date():
            raise serializers.ValidationError("Cannot set unavailability for past dates")
        return value
    
    def create(self, validated_data):
        professional = self.context['professional']
        region = self.context['region']
        
        return ProfessionalUnavailability.objects.create(
            professional=professional,
            region=region,
            **validated_data
        )


class ProfessionalDocumentSerializer(serializers.ModelSerializer):
    """
    Professional verification documents
    """
    class Meta:
        model = ProfessionalDocument
        fields = [
            'id', 'document_type', 'document_file', 'description',
            'is_verified', 'verification_notes', 'created_at'
        ]
        read_only_fields = ['is_verified', 'verification_notes']


class AvailabilitySlotSerializer(serializers.Serializer):
    """
    Available time slots for booking
    """
    date = serializers.DateField()
    start_time = serializers.TimeField()
    end_time = serializers.TimeField()
    is_available = serializers.BooleanField()
    price = serializers.DecimalField(max_digits=10, decimal_places=2)


class ProfessionalSearchSerializer(serializers.Serializer):
    """
    Professional search parameters
    """
    service_id = serializers.IntegerField(required=False)
    region_code = serializers.CharField(max_length=10, required=False)
    date = serializers.DateField(required=False)
    time = serializers.TimeField(required=False)
    min_rating = serializers.DecimalField(
        max_digits=3, 
        decimal_places=2, 
        required=False,
        min_value=0,
        max_value=5
    )
    max_price = serializers.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        required=False
    )
    verified_only = serializers.BooleanField(default=True)