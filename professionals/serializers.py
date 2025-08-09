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


class ProfessionalAvailabilityDataSerializer(serializers.Serializer):
    """
    Serializer for professional availability data in update operations
    """
    region_id = serializers.IntegerField()
    weekday = serializers.IntegerField(min_value=0, max_value=6)  # 0=Monday, 6=Sunday
    start_time = serializers.TimeField()
    end_time = serializers.TimeField()
    break_start = serializers.TimeField(required=False, allow_null=True)
    break_end = serializers.TimeField(required=False, allow_null=True)
    is_active = serializers.BooleanField(default=True)
    
    def validate(self, attrs):
        # Validate that end_time is after start_time
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


class ProfessionalUpdateSerializer(serializers.ModelSerializer):
    """
    Professional profile update serializer - allows patching all fields
    """
    # User fields that can be updated
    first_name = serializers.CharField(source='user.first_name', required=False)
    last_name = serializers.CharField(source='user.last_name', required=False)
    phone_number = serializers.CharField(source='user.phone_number', required=False)
    date_of_birth = serializers.DateField(source='user.date_of_birth', required=False)
    gender = serializers.CharField(source='user.gender', required=False)
    profile_picture = serializers.ImageField(source='user.profile_picture', required=False)
    
    # Professional fields
    regions = serializers.PrimaryKeyRelatedField(
        queryset=Region.objects.filter(is_active=True),
        many=True,
        required=False
    )
    services = serializers.PrimaryKeyRelatedField(
        queryset=Service.objects.filter(is_active=True),
        many=True,
        required=False
    )
    
    # Professional status fields
    is_verified = serializers.BooleanField(required=False)
    is_active = serializers.BooleanField(required=False)
    
    # Availability data
    availability = ProfessionalAvailabilityDataSerializer(many=True, required=False)
    
    class Meta:
        model = Professional
        fields = [
            # User fields
            'first_name', 'last_name', 'phone_number', 'date_of_birth', 'gender', 'profile_picture',
            # Professional fields
            'bio', 'experience_years', 'travel_radius_km', 
            'min_booking_notice_hours', 'cancellation_policy',
            'regions', 'services', 'availability',
            # Status fields
            'is_verified', 'is_active'
        ]
    
    def update(self, instance, validated_data):
        # Handle user fields
        user_data = {}
        if 'user' in validated_data:
            user_data = validated_data.pop('user')
            user = instance.user
            for field, value in user_data.items():
                setattr(user, field, value)
            user.save()
        
        # Handle regions and services
        regions = validated_data.pop('regions', None)
        services = validated_data.pop('services', None)
        availability_data = validated_data.pop('availability', None)
        
        # Update professional fields
        for field, value in validated_data.items():
            setattr(instance, field, value)
        
        # Update regions if provided
        if regions is not None:
            instance.regions.set(regions)
        
        # Update services if provided
        if services is not None:
            # Clear existing services and create new ones
            from .models import ProfessionalService
            instance.professionalservice_set.all().delete()
            for region in instance.regions.all():
                for service in services:
                    ProfessionalService.objects.create(
                        professional=instance,
                        service=service,
                        region=region
                    )
        
        # Update availability if provided
        if availability_data is not None:
            # Clear existing availability for this professional
            from .models import ProfessionalAvailability
            from regions.models import Region
            instance.availability_schedule.all().delete()
            
            # Create new availability entries
            for availability_item in availability_data:
                try:
                    region_id = availability_item.get('region_id')
                    if region_id:
                        region = Region.objects.get(id=region_id)
                        ProfessionalAvailability.objects.create(
                            professional=instance,
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
        
        instance.save()
        return instance


class ProfessionalAdminDetailSerializer(serializers.ModelSerializer):
    """
    Comprehensive professional information for admin API
    """
    # User fields
    first_name = serializers.CharField(source='user.first_name', read_only=True)
    last_name = serializers.CharField(source='user.last_name', read_only=True)
    email = serializers.EmailField(source='user.email', read_only=True)
    phone_number = serializers.CharField(source='user.phone_number', read_only=True)
    user_is_active = serializers.BooleanField(source='user.is_active', read_only=True)
    date_joined = serializers.DateTimeField(source='user.date_joined', read_only=True)
    last_login = serializers.DateTimeField(source='user.last_login', read_only=True)
    date_of_birth = serializers.DateField(source='user.date_of_birth', read_only=True)
    gender = serializers.CharField(source='user.gender', read_only=True)
    profile_picture = serializers.ImageField(source='user.profile_picture', read_only=True)
    
    # Professional stats
    total_bookings = serializers.SerializerMethodField()
    total_earnings = serializers.SerializerMethodField()
    regions_served = serializers.SerializerMethodField()
    services_offered = serializers.SerializerMethodField()
    availability_by_region = serializers.SerializerMethodField()
    documents = serializers.SerializerMethodField()
    verification_documents = serializers.SerializerMethodField()
    profile_completion_status = serializers.SerializerMethodField()
    
    class Meta:
        model = Professional
        fields = [
            # Basic info
            'id', 'first_name', 'last_name', 'email', 'phone_number', 
            'user_is_active', 'date_joined', 'last_login', 'date_of_birth', 'gender',
            'profile_picture',
            
            # Professional details
            'bio', 'experience_years', 'rating', 'total_reviews',
            'is_verified', 'is_active', 'travel_radius_km', 
            'min_booking_notice_hours', 'cancellation_policy',
            'commission_rate', 'profile_completed', 'verified_at',
            
            # Stats and relationships
            'total_bookings', 'total_earnings', 'regions_served',
            'services_offered', 'availability_by_region', 'documents',
            'verification_documents', 'profile_completion_status',
            
            # Timestamps
            'created_at', 'updated_at'
        ]
    
    def get_total_bookings(self, obj):
        try:
            from bookings.models import Booking
            return Booking.objects.filter(professional=obj).count()
        except Exception:
            return 0
    
    def get_total_earnings(self, obj):
        try:
            from bookings.models import Booking
            completed_bookings = Booking.objects.filter(
                professional=obj, 
                status='completed'
            )
            return float(sum(booking.total_amount for booking in completed_bookings))
        except Exception:
            return 0.0
    
    def get_regions_served(self, obj):
        try:
            return [{
                'id': r.id, 
                'name': r.name, 
                'code': r.code,
                'is_primary': obj.professionalregion_set.filter(region=r).first().is_primary if obj.professionalregion_set.filter(region=r).exists() else False
            } for r in obj.regions.all()]
        except Exception:
            return []
    
    def get_services_offered(self, obj):
        try:
            services_data = []
            for ps in obj.professionalservice_set.select_related('service', 'service__category').all():
                services_data.append({
                    'id': ps.service.id,
                    'name': ps.service.name,
                    'category': ps.service.category.name,
                    'region_id': ps.region.id,
                    'region_name': ps.region.name,
                    'custom_price': float(ps.custom_price) if ps.custom_price else None,
                    'effective_price': float(ps.get_price()),
                    'is_active': ps.is_active,
                    'preparation_time_minutes': ps.preparation_time_minutes,
                    'cleanup_time_minutes': ps.cleanup_time_minutes
                })
            return services_data
        except Exception:
            return []
    
    def get_availability_by_region(self, obj):
        """Get availability grouped by region"""
        try:
            availability_data = {}
            
            for availability in obj.availability_schedule.filter(is_active=True).select_related('region'):
                try:
                    region_id = availability.region.id
                    region_name = availability.region.name
                    
                    if region_id not in availability_data:
                        availability_data[region_id] = {
                            'region_id': region_id,
                            'region_name': region_name,
                            'schedule': []
                        }
                    
                    availability_data[region_id]['schedule'].append({
                        'id': availability.id,
                        'weekday': availability.weekday,
                        'weekday_name': availability.get_weekday_display(),
                        'start_time': availability.start_time.strftime('%H:%M') if availability.start_time else None,
                        'end_time': availability.end_time.strftime('%H:%M') if availability.end_time else None,
                        'break_start': availability.break_start.strftime('%H:%M') if availability.break_start else None,
                        'break_end': availability.break_end.strftime('%H:%M') if availability.break_end else None,
                        'is_active': availability.is_active
                    })
                except Exception:
                    continue
            
            return list(availability_data.values())
        except Exception:
            return []
    
    def get_documents(self, obj):
        """Get all professional documents"""
        try:
            return [{
                'id': doc.id,
                'document_type': doc.document_type,
                'document_type_display': doc.get_document_type_display(),
                'description': doc.description,
                'is_verified': doc.is_verified,
                'verified_by': doc.verified_by.get_full_name() if doc.verified_by else None,
                'verified_at': doc.verified_at,
                'verification_notes': doc.verification_notes,
                'created_at': doc.created_at
            } for doc in obj.documents.all()]
        except Exception:
            return []
    
    def get_verification_documents(self, obj):
        """Get verification documents list"""
        try:
            return obj.verification_documents
        except Exception:
            return []
    
    def get_profile_completion_status(self, obj):
        """Get profile completion status"""
        try:
            return {
                'bio_completed': bool(obj.bio),
                'experience_added': obj.experience_years > 0,
                'regions_added': obj.regions.exists(),
                'services_added': obj.services.exists(),
                'availability_set': obj.availability_schedule.exists(),
                'documents_uploaded': obj.documents.exists(),
                'is_verified': obj.is_verified,
                'completion_percentage': self._calculate_completion_percentage(obj)
            }
        except Exception:
            return {}
    
    def _calculate_completion_percentage(self, obj):
        """Calculate profile completion percentage"""
        try:
            total_fields = 6
            completed_fields = 0
            
            if obj.bio:
                completed_fields += 1
            if obj.experience_years > 0:
                completed_fields += 1
            if obj.regions.exists():
                completed_fields += 1
            if obj.services.exists():
                completed_fields += 1
            if obj.availability_schedule.exists():
                completed_fields += 1
            if obj.documents.exists():
                completed_fields += 1
            
            return round((completed_fields / total_fields) * 100, 1)
        except Exception:
            return 0.0