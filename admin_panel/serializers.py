from rest_framework import serializers
from django.db.models import Q, Count, Avg, Sum
from datetime import datetime, timedelta
from django.utils import timezone
from django.contrib.auth.password_validation import validate_password

from .models import AdminActivity, SystemAlert, SupportTicket, TicketMessage
from accounts.models import User
from professionals.models import Professional, ProfessionalAvailability, ProfessionalService
from bookings.models import Booking, Review, BookingPicture
from payments.models import Payment, SavedPaymentMethod
from services.models import Category, Service, AddOn, RegionalPricing
from regions.models import Region, RegionalSettings
from notifications.models import Notification
from bookings.serializers import (
    BookingAddOnSerializer, ReviewSerializer, BookingRescheduleSerializer, BookingMessageSerializer,
    BookingPictureSerializer, BookingPictureUploadSerializer
)

# ===================== PROFESSIONAL AVAILABILITY SERIALIZER =====================

class ProfessionalAvailabilityDataSerializer(serializers.Serializer):
    """
    Serializer for professional availability data in admin operations - FIXED VERSION
    """
    region_id = serializers.IntegerField()
    weekday = serializers.IntegerField(min_value=0, max_value=6)  # 0=Monday, 6=Sunday
    start_time = serializers.TimeField()  # Changed to TimeField to handle time objects
    end_time = serializers.TimeField()    # Changed to TimeField to handle time objects
    break_start = serializers.TimeField(required=False, allow_null=True)
    break_end = serializers.TimeField(required=False, allow_null=True)
    is_active = serializers.BooleanField(default=True)

    def to_internal_value(self, data):
        """
        Custom to_internal_value to handle time parsing from various formats
        """
        import logging
        from datetime import datetime, time
        
        logger = logging.getLogger(__name__)
        logger.debug(f"ProfessionalAvailabilityDataSerializer.to_internal_value called with: {data}")
        logger.debug(f"Data type: {type(data)}")
        
        # Handle case where data might be a string or other type
        if not isinstance(data, dict):
            logger.error(f"Expected dict, got {type(data)}: {data}")
            raise serializers.ValidationError(f"Expected dictionary data, got {type(data)}")
        
        # Create a copy to avoid modifying original data
        processed_data = data.copy()
        
        def parse_time_field(time_str, field_name):
            """Parse time string and return time object or None"""
            if not time_str:
                return None
                
            if isinstance(time_str, time):
                # Already a time object
                logger.debug(f"  ✅ {field_name} already a time object: {time_str}")
                return time_str
            
            if not isinstance(time_str, str):
                time_str = str(time_str)
            
            time_str = time_str.strip()
            if not time_str:
                return None
            
            logger.debug(f"Parsing {field_name}: '{time_str}' (type: {type(time_str)})")
            
            # Try different time formats
            for fmt in ['%H:%M:%S', '%H:%M', '%I:%M %p', '%I:%M:%S %p']:
                try:
                    parsed_time = datetime.strptime(time_str, fmt).time()
                    logger.debug(f"  ✅ Parsed '{time_str}' using format '{fmt}' -> {parsed_time}")
                    return parsed_time
                except ValueError:
                    continue
            
            # If no format worked, try manual parsing for HH:MM format
            if ':' in time_str:
                try:
                    parts = time_str.split(':')
                    if len(parts) == 2:
                        hours = int(parts[0])
                        minutes = int(parts[1])
                        if 0 <= hours <= 23 and 0 <= minutes <= 59:
                            parsed_time = time(hours, minutes)
                            logger.debug(f"  ✅ Manual parsed '{time_str}' -> {parsed_time}")
                            return parsed_time
                except (ValueError, IndexError):
                    pass
            
            logger.error(f"  ❌ Could not parse {field_name} '{time_str}'")
            raise serializers.ValidationError(
                f"Invalid time format for {field_name}: '{time_str}'. Expected formats: HH:MM, HH:MM:SS"
            )
        
        # Parse time fields
        time_fields = ['start_time', 'end_time', 'break_start', 'break_end']
        for field in time_fields:
            if field in processed_data:
                try:
                    processed_data[field] = parse_time_field(processed_data[field], field)
                except serializers.ValidationError:
                    # Re-raise validation errors
                    raise
                except Exception as e:
                    logger.error(f"Unexpected error parsing {field}: {e}")
                    raise serializers.ValidationError(
                        f"Error parsing {field}: {str(e)}"
                    )
        
        logger.debug(f"Processed data: {processed_data}")
        
        # Call parent to_internal_value with processed data
        return super().to_internal_value(processed_data)

    def validate(self, attrs):
        """Enhanced validation with better error messages"""
        import logging
        logger = logging.getLogger(__name__)
        logger.debug(f"ProfessionalAvailabilityDataSerializer.validate called with: {attrs}")
        
        # Validate that end_time is after start_time
        start_time = attrs.get('start_time')
        end_time = attrs.get('end_time')
        
        if not start_time or not end_time:
            raise serializers.ValidationError("Both start_time and end_time are required")
        
        if end_time <= start_time:
            raise serializers.ValidationError({
                'end_time': f"End time ({end_time}) must be after start time ({start_time})"
            })
        
        # Validate break times if provided
        break_start = attrs.get('break_start')
        break_end = attrs.get('break_end')
        
        if break_start and break_end:
            if break_end <= break_start:
                raise serializers.ValidationError({
                    'break_end': f"Break end time ({break_end}) must be after break start time ({break_start})"
                })
            
            # Validate break is within working hours
            if break_start < start_time:
                raise serializers.ValidationError({
                    'break_start': f"Break start time ({break_start}) cannot be before work start time ({start_time})"
                })
            
            if break_end > end_time:
                raise serializers.ValidationError({
                    'break_end': f"Break end time ({break_end}) cannot be after work end time ({end_time})"
                })
        elif break_start and not break_end:
            raise serializers.ValidationError({
                'break_end': "Break end time is required when break start time is provided"
            })
        elif break_end and not break_start:
            raise serializers.ValidationError({
                'break_start': "Break start time is required when break end time is provided"
            })
        
        # Validate region exists
        region_id = attrs.get('region_id')
        if region_id:
            from regions.models import Region
            if not Region.objects.filter(id=region_id, is_active=True).exists():
                raise serializers.ValidationError({
                    'region_id': f"Region with ID {region_id} does not exist or is not active"
                })
        
        logger.debug(f"Validation successful: {attrs}")
        return attrs

# ===================== USER MANAGEMENT SERIALIZERS =====================

class AdminUserCreateSerializer(serializers.ModelSerializer):
    """
    Create user by admin
    """
    password = serializers.CharField(write_only=True, validators=[validate_password])
    profile_picture = serializers.ImageField(required=False, allow_null=True)
    
    class Meta:
        model = User
        fields = [
            'first_name', 'last_name', 'email', 'password', 'user_type',
            'phone_number', 'current_region', 'is_active', 'is_verified',
            'date_of_birth', 'gender', 'profile_picture'
        ]
    
    def validate_email(self, value):
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError("A user with this email already exists.")
        return value
    
    def create(self, validated_data):
        password = validated_data.pop('password')
        user = User.objects.create_user(
            username=validated_data['email'],
            **validated_data
        )
        user.set_password(password)
        user.save()
        return user


class AdminUserUpdateSerializer(serializers.ModelSerializer):
    """
    Update user by admin
    """
    profile_picture = serializers.ImageField(required=False, allow_null=True)
    class Meta:
        model = User
        fields = [
            'first_name', 'last_name', 'email', 'user_type', 'phone_number',
            'current_region', 'is_active', 'is_verified', 'profile_completed',
            'date_of_birth', 'gender', 'profile_picture'
        ]


class AdminUserDetailSerializer(serializers.ModelSerializer):
    """
    Detailed user information for admin
    """
    total_bookings = serializers.SerializerMethodField()
    total_spent = serializers.SerializerMethodField()
    last_activity = serializers.DateTimeField(source='last_login', read_only=True)
    current_region_name = serializers.CharField(source='current_region.name', read_only=True)
    profile_picture = serializers.ImageField(read_only=True)
    date_of_birth = serializers.DateField(read_only=True)
    gender = serializers.CharField(read_only=True)
    
    class Meta:
        model = User
        fields = [
            'id', 'uid', 'first_name', 'last_name', 'email', 'username',
            'user_type', 'phone_number', 'current_region', 'current_region_name',
            'is_active', 'is_verified', 'profile_completed', 'date_of_birth', 'gender', 'profile_picture',
            'date_joined', 'last_login', 'last_activity', 'total_bookings', 'total_spent'
        ]
    
    def get_total_bookings(self, obj):
        return obj.bookings.count()
    
    def get_total_spent(self, obj):
        return obj.payments.filter(status='succeeded').aggregate(
            total=Sum('amount')
        )['total'] or 0


# ===================== PROFESSIONAL MANAGEMENT SERIALIZERS =====================

class AdminProfessionalCreateSerializer(serializers.ModelSerializer):
    """
    Create professional by admin
    """
    # User creation fields
    first_name = serializers.CharField()
    last_name = serializers.CharField()
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, validators=[validate_password])
    phone_number = serializers.CharField(required=False)
    gender = serializers.ChoiceField(choices=User.GENDER_CHOICES, required=False)
    date_of_birth = serializers.DateField(required=False)
    profile_picture = serializers.ImageField(required=False, allow_null=True)
    
    # Professional fields
    regions = serializers.PrimaryKeyRelatedField(
        queryset=Region.objects.filter(is_active=True),
        many=True
    )
    services = serializers.PrimaryKeyRelatedField(
        queryset=Service.objects.filter(is_active=True),
        many=True
    )
    
    # Availability data
    availability = ProfessionalAvailabilityDataSerializer(many=True, required=False)
    
    class Meta:
        model = Professional
        fields = [
            'first_name', 'last_name', 'email', 'password', 'phone_number',
            'gender', 'date_of_birth', 'profile_picture',
            'bio', 'experience_years', 'is_verified', 'is_active',
            'travel_radius_km', 'min_booking_notice_hours', 'commission_rate',
            'regions', 'services', 'availability'
        ]
    
    def validate_email(self, value):
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError("A user with this email already exists.")
        return value
    
    def to_internal_value(self, data):
        """
        Custom to_internal_value to handle complex data structures
        """
        import logging
        logger = logging.getLogger(__name__)
        logger.debug(f"AdminProfessionalCreateSerializer.to_internal_value called with data keys: {list(data.keys())}")
        
        # Let the serializer handle availability data naturally
        # The view should convert multipart form data to proper structure
        logger.debug(f"Processing data with availability: {data.get('availability', [])}")
        
        return super().to_internal_value(data)
    
    def create(self, validated_data):
        import logging
        logger = logging.getLogger(__name__)
        logger.debug(f"AdminProfessionalCreateSerializer.create called")
        
        # Extract user fields
        user_fields = {
            'first_name': validated_data.pop('first_name'),
            'last_name': validated_data.pop('last_name'),
            'email': validated_data.pop('email'),
            'phone_number': validated_data.pop('phone_number', ''),
            'gender': validated_data.pop('gender', ''),
            'date_of_birth': validated_data.pop('date_of_birth', None),
            'profile_picture': validated_data.pop('profile_picture', None),
            'user_type': 'professional'
        }
        password = validated_data.pop('password')
        regions = validated_data.pop('regions')
        services = validated_data.pop('services')
        availability_data = validated_data.pop('availability', [])
        
        logger.debug(f"Creating user with email: {user_fields['email']}")
        
        # Create user
        user = User.objects.create_user(
            username=user_fields['email'],
            **user_fields
        )
        user.set_password(password)
        user.current_region = regions[0] if regions else None
        user.save()
        
        logger.debug(f"Created user {user.id}, creating professional")
        
        # Create professional
        professional = Professional.objects.create(
            user=user,
            **validated_data
        )
        
        logger.debug(f"Created professional {professional.id}, setting regions and services")
        
        # Set regions and services
        professional.regions.set(regions)
        
        # Create ProfessionalService entries
        for region in regions:
            for service in services:
                ProfessionalService.objects.create(
                    professional=professional,
                    service=service,
                    region=region
                )
        
        logger.debug(f"Created ProfessionalService entries, processing availability")
        
        # Create availability entries
        for availability_item in availability_data:
            try:
                region = Region.objects.get(id=availability_item['region_id'])
                ProfessionalAvailability.objects.create(
                    professional=professional,
                    region=region,
                    weekday=availability_item['weekday'],
                    start_time=availability_item['start_time'],
                    end_time=availability_item['end_time'],
                    break_start=availability_item.get('break_start'),
                    break_end=availability_item.get('break_end'),
                    is_active=availability_item.get('is_active', True)
                )
                logger.debug(f"Created availability for region {region.id}, weekday {availability_item['weekday']}")
            except Region.DoesNotExist:
                logger.warning(f"Region {availability_item['region_id']} not found, skipping availability")
                continue
            except Exception as e:
                logger.error(f"Error creating availability: {str(e)}")
                continue
        
        logger.info(f"✅ Successfully created professional {professional.id}")
        return professional
    
    def to_representation(self, instance):
        # Return only the professional id to avoid AttributeError
        return {'id': instance.id}


class AdminProfessionalUpdateSerializer(serializers.ModelSerializer):
    """
    Update professional by admin - FIXED VERSION
    """
    # User fields - removed source mapping to handle manually
    first_name = serializers.CharField(required=False)
    last_name = serializers.CharField(required=False)
    email = serializers.EmailField(required=False)
    phone_number = serializers.CharField(required=False, allow_blank=True)
    gender = serializers.ChoiceField(choices=User.GENDER_CHOICES, required=False, allow_blank=True)
    date_of_birth = serializers.DateField(required=False, allow_null=True)
    profile_picture = serializers.ImageField(required=False, allow_null=True)
    user_is_active = serializers.BooleanField(required=False)
    
    # Professional fields with proper handling
    regions = serializers.ListField(
        child=serializers.IntegerField(),
        required=False,
        allow_empty=False
    )
    services = serializers.ListField(
        child=serializers.IntegerField(),
        required=False,
        allow_empty=False
    )
    
    # Availability data
    availability = ProfessionalAvailabilityDataSerializer(many=True, required=False)
    
    class Meta:
        model = Professional
        fields = [
            'first_name', 'last_name', 'email', 'phone_number', 'gender', 
            'date_of_birth', 'profile_picture', 'user_is_active',
            'bio', 'experience_years', 'is_verified', 'is_active',
            'travel_radius_km', 'min_booking_notice_hours', 'commission_rate',
            'regions', 'services', 'availability'
        ]
    
    def validate_regions(self, value):
        """Validate that all region IDs exist and are active"""
        if not value:
            return value
        
        from regions.models import Region
        valid_regions = Region.objects.filter(id__in=value, is_active=True)
        valid_ids = set(valid_regions.values_list('id', flat=True))
        provided_ids = set(value)
        
        if provided_ids != valid_ids:
            missing_ids = provided_ids - valid_ids
            raise serializers.ValidationError(f"Invalid region IDs: {list(missing_ids)}")
        
        return list(valid_regions)
    
    def validate_services(self, value):
        """Validate that all service IDs exist and are active"""
        if not value:
            return value
        
        from services.models import Service
        valid_services = Service.objects.filter(id__in=value, is_active=True)
        valid_ids = set(valid_services.values_list('id', flat=True))
        provided_ids = set(value)
        
        if provided_ids != valid_ids:
            missing_ids = provided_ids - valid_ids
            raise serializers.ValidationError(f"Invalid service IDs: {list(missing_ids)}")
        
        return list(valid_services)
    
    def to_internal_value(self, data):
        """
        Custom to_internal_value to handle complex data structures
        """
        import logging
        logger = logging.getLogger(__name__)
        logger.debug(f"AdminProfessionalUpdateSerializer.to_internal_value called")
        logger.debug(f"Raw data keys: {list(data.keys())}")
        
        # Handle the availability data separately to avoid conflicts
        availability_data = data.get('availability', [])
        if availability_data:
            logger.debug(f"Processing {len(availability_data)} availability items for update")
            logger.debug(f"Availability data type: {type(availability_data)}")
            logger.debug(f"Availability data: {availability_data}")
            
            processed_availability = []
            for i, item in enumerate(availability_data):
                try:
                    logger.debug(f"Processing availability item {i}: {item}")
                    logger.debug(f"Item type: {type(item)}")
                    
                    # Ensure item is a dictionary
                    if not isinstance(item, dict):
                        logger.error(f"Availability item {i} is not a dict: {type(item)}")
                        raise serializers.ValidationError({f'availability[{i}]': f"Expected dictionary, got {type(item)}"})
                    
                    # Create a new serializer instance for each availability item
                    availability_serializer = ProfessionalAvailabilityDataSerializer(data=item)
                    if availability_serializer.is_valid():
                        processed_availability.append(availability_serializer.validated_data)
                        logger.debug(f"  ✅ Availability item {i} validated successfully")
                    else:
                        logger.error(f"  ❌ Availability item {i} validation failed: {availability_serializer.errors}")
                        raise serializers.ValidationError({f'availability[{i}]': availability_serializer.errors})
                except serializers.ValidationError:
                    # Re-raise validation errors
                    raise
                except Exception as e:
                    logger.error(f"  💥 Error processing availability item {i}: {str(e)}")
                    raise serializers.ValidationError({f'availability[{i}]': str(e)})
            
            # Replace the availability data with processed data
            data = data.copy()
            data['availability'] = processed_availability
            logger.debug(f"Processed all availability items successfully for update")
        
        return super().to_internal_value(data)
    
    def validate_email(self, value):
        """Validate email uniqueness"""
        if value and self.instance:
            existing_user = User.objects.filter(email=value).exclude(id=self.instance.user.id).first()
            if existing_user:
                raise serializers.ValidationError("A user with this email already exists.")
        return value
    
    def update(self, instance, validated_data):
        """
        Custom update method to handle user and professional fields separately
        """
        import logging
        logger = logging.getLogger(__name__)
        
        try:
            # Extract user fields
            user_fields = {}
            user_field_names = [
                'first_name', 'last_name', 'email', 'phone_number', 
                'gender', 'date_of_birth', 'profile_picture', 'user_is_active'
            ]
            
            for field_name in user_field_names:
                if field_name in validated_data:
                    value = validated_data.pop(field_name)
                    if field_name == 'user_is_active':
                        user_fields['is_active'] = value
                    else:
                        user_fields[field_name] = value
            
            # Update user fields if any provided
            if user_fields:
                logger.debug(f"Updating user fields: {user_fields}")
                for field, value in user_fields.items():
                    setattr(instance.user, field, value)
            instance.user.save()
        
            # Extract relationship fields
            regions = validated_data.pop('regions', None)
            services = validated_data.pop('services', None)
            availability_data = validated_data.pop('availability', None)
            
            # Update professional fields
            for field, value in validated_data.items():
                setattr(instance, field, value)
            instance.save()
            
            # Handle regions and services updates
            if regions is not None:
                logger.debug(f"Updating regions: {[r.id for r in regions]}")
                instance.regions.set(regions)
                
                # Get services for ProfessionalService updates
                if services is not None:
                    current_services = services
                else:
                    current_services = list(instance.services.all())
                
                # Update ProfessionalService entries
                instance.professionalservice_set.all().delete()
                for region in regions:
                    for service in current_services:
                        ProfessionalService.objects.create(
                            professional=instance,
                            service=service,
                            region=region
                        )
                
                if services is not None:
                    instance.services.set(services)
            
            elif services is not None:
                logger.debug(f"Updating services: {[s.id for s in services]}")
                # Only services changed, update ProfessionalService entries for existing regions
                existing_regions = list(instance.regions.all())
                instance.professionalservice_set.all().delete()
                for region in existing_regions:
                    for service in services:
                        ProfessionalService.objects.create(
                            professional=instance,
                            service=service,
                            region=region
                        )
                instance.services.set(services)
            
            # Handle availability updates
            if availability_data is not None:
                logger.debug(f"Updating availability: {len(availability_data)} items")
                # Clear existing availability
                instance.availability_schedule.all().delete()
                
                # Create new availability entries
                for availability_item in availability_data:
                    try:
                        region = Region.objects.get(id=availability_item['region_id'])
                        ProfessionalAvailability.objects.create(
                            professional=instance,
                            region=region,
                            weekday=availability_item['weekday'],
                            start_time=availability_item['start_time'],
                            end_time=availability_item['end_time'],
                            break_start=availability_item.get('break_start'),
                            break_end=availability_item.get('break_end'),
                            is_active=availability_item.get('is_active', True)
                        )
                        logger.debug(f"Created availability for region {region.id}, weekday {availability_item['weekday']}")
                    except Region.DoesNotExist:
                        logger.warning(f"Region {availability_item['region_id']} not found, skipping availability")
                        continue
                    except Exception as e:
                        logger.error(f"Error creating availability: {str(e)}")
                        continue
            
            logger.info(f"✅ Successfully updated professional {instance.id}")
            return instance
            
        except Exception as e:
            logger.error(f"💥 Error updating professional {instance.id}: {str(e)}")
            raise serializers.ValidationError(f"Failed to update professional: {str(e)}")


# ===================== CATEGORY MANAGEMENT SERIALIZERS =====================

class AdminCategorySerializer(serializers.ModelSerializer):
    """
    Category management by admin
    """
    services_count = serializers.SerializerMethodField()
    addons = serializers.PrimaryKeyRelatedField(queryset=AddOn.objects.all(), many=True, required=False, write_only=True)
    addons_details = serializers.SerializerMethodField(read_only=True)
    class Meta:
        model = Category
        fields = [
            'id', 'name', 'description', 'icon', 'region', 'is_active',
            'is_featured', 'sort_order', 'slug', 'meta_description', 'services_count',
            'addons', 'addons_details', 'created_at', 'updated_at'
        ]
    def get_services_count(self, obj):
        return obj.services.filter(is_active=True).count()
    def get_addons_details(self, obj):
        return AdminAddOnSerializer(obj.addons.all(), many=True).data
    def create(self, validated_data):
        addons = validated_data.pop('addons', [])
        category = super().create(validated_data)
        if addons:
            category.addons.set(addons)
        return category
    def update(self, instance, validated_data):
        addons = validated_data.pop('addons', None)
        category = super().update(instance, validated_data)
        if addons is not None:
            category.addons.set(addons)
        return category


# ===================== SERVICE MANAGEMENT SERIALIZERS =====================

class AdminServiceSerializer(serializers.ModelSerializer):
    """
    Service management by admin
    """
    category_name = serializers.CharField(source='category.name', read_only=True)
    region_name = serializers.CharField(source='category.region.name', read_only=True)
    professionals_count = serializers.SerializerMethodField()
    bookings_count = serializers.SerializerMethodField()
    
    class Meta:
        model = Service
        fields = [
            'id', 'name', 'description', 'category', 'category_name', 'region_name',
            'base_price', 'duration_minutes', 'preparation_time', 'cleanup_time',
            'is_active', 'sort_order', 'is_featured', 'image', 'slug',
            'professionals_count', 'bookings_count', 'created_at', 'updated_at'
        ]
    
    def get_professionals_count(self, obj):
        return obj.professionals.filter(is_active=True, is_verified=True).count()
    
    def get_bookings_count(self, obj):
        return obj.booking_set.count()


class AdminRegionalPricingSerializer(serializers.ModelSerializer):
    """
    Regional pricing management
    """
    service_name = serializers.CharField(source='service.name', read_only=True)
    region_name = serializers.CharField(source='region.name', read_only=True)
    
    class Meta:
        model = RegionalPricing
        fields = [
            'id', 'service', 'service_name', 'region', 'region_name',
            'price', 'promotional_price', 'promotion_start', 'promotion_end',
            'is_active', 'created_at'
        ]


# ===================== ADDON MANAGEMENT SERIALIZERS =====================

class AdminAddOnSerializer(serializers.ModelSerializer):
    """
    Add-on management by admin
    """
    categories_names = serializers.SerializerMethodField()
    region_name = serializers.CharField(source='region.name', read_only=True)
    
    class Meta:
        model = AddOn
        fields = [
            'id', 'name', 'description', 'categories', 'categories_names', 'region', 'region_name',
            'price', 'duration_minutes', 'is_active', 'max_quantity',
            'created_at', 'updated_at'
        ]
    
    def get_categories_names(self, obj):
        return [cat.name for cat in obj.categories.all()]


# ===================== BOOKING MANAGEMENT SERIALIZERS =====================

class AdminBookingSerializer(serializers.ModelSerializer):
    """
    Booking management by admin - FIXED field names
    """
    customer_name = serializers.CharField(source='customer.get_full_name', read_only=True)
    customer_email = serializers.CharField(source='customer.email', read_only=True)
    professional = serializers.SerializerMethodField()
    service_name = serializers.CharField(source='service.name', read_only=True)
    region_name = serializers.CharField(source='region.name', read_only=True)
    recipient = serializers.SerializerMethodField()
    selected_addons = BookingAddOnSerializer(many=True, read_only=True)
    review = ReviewSerializer(read_only=True)
    reschedule_requests = BookingRescheduleSerializer(many=True, read_only=True)
    messages = BookingMessageSerializer(many=True, read_only=True)
    status_history = serializers.SerializerMethodField()
    
    # Before and after pictures
    before_pictures = serializers.SerializerMethodField()
    after_pictures = serializers.SerializerMethodField()
    picture_counts = serializers.SerializerMethodField()
    
    class Meta:
        model = Booking
        fields = [
            'booking_id', 'customer', 'customer_name', 'customer_email',
            'professional', 'service', 'service_name',
            'region', 'region_name', 'scheduled_date', 'scheduled_time',
            'duration_minutes', 'total_amount', 'status', 'payment_status',
            'booking_for_self', 'recipient', 'customer_notes', 'professional_notes', 'admin_notes',
            'address_line1', 'address_line2', 'city', 'postal_code', 'location_notes',
            'base_amount', 'addon_amount', 'discount_amount', 'tax_amount',
            'deposit_required', 'deposit_percentage', 'deposit_amount',
            'cancelled_by', 'cancelled_at', 'cancellation_reason',
            'created_at', 'updated_at', 'confirmed_at', 'completed_at',
            'selected_addons', 'review', 'reschedule_requests', 'messages', 'status_history',
            'before_pictures', 'after_pictures', 'picture_counts'
        ]
    def get_professional(self, obj):
        if obj.professional and obj.professional.user:
            user = obj.professional.user
            return {
                'id': obj.professional.id,
                'name': user.get_full_name(),
                'email': user.email,
                'profile_picture': user.profile_picture.url if user.profile_picture else None
            }
        return None
    def get_recipient(self, obj):
        if not obj.booking_for_self:
            return {
                'name': obj.recipient_name,
                'phone': obj.recipient_phone,
                'email': obj.recipient_email
            }
        return None
    def get_status_history(self, obj):
        return [
            {
                'previous_status': h.previous_status,
                'new_status': h.new_status,
                'changed_by': h.changed_by.get_full_name() if h.changed_by else None,
                'reason': h.reason,
                'created_at': h.created_at
            }
            for h in obj.status_history.all().order_by('-created_at')
        ]
    
    def get_before_pictures(self, obj):
        """Get before pictures for the booking"""
        try:
            before_pics = obj.pictures.filter(picture_type='before').order_by('uploaded_at')
            return BookingPictureSerializer(before_pics, many=True, context=self.context).data
        except Exception:
            # Return empty list if pictures table doesn't exist yet (before migration)
            return []
    
    def get_after_pictures(self, obj):
        """Get after pictures for the booking"""
        try:
            after_pics = obj.pictures.filter(picture_type='after').order_by('uploaded_at')
            return BookingPictureSerializer(after_pics, many=True, context=self.context).data
        except Exception:
            # Return empty list if pictures table doesn't exist yet (before migration)
            return []
    
    def get_picture_counts(self, obj):
        """Get picture counts for admin reference"""
        try:
            before_count = obj.pictures.filter(picture_type='before').count()
            after_count = obj.pictures.filter(picture_type='after').count()
            return {
                'before': before_count,
                'after': after_count,
                'total': before_count + after_count,
                'can_add_before': 6 - before_count,
                'can_add_after': 6 - after_count
            }
        except Exception:
            # Return default counts if pictures table doesn't exist yet (before migration)
            return {
                'before': 0,
                'after': 0,
                'total': 0,
                'can_add_before': 6,
                'can_add_after': 6
            }

class AdminBookingUpdateSerializer(serializers.ModelSerializer):
    """
    Update booking by admin - FIXED field names
    """
    class Meta:
        model = Booking
        fields = [
            'status', 'payment_status', 'scheduled_date', 'scheduled_time',
            'professional_notes', 'admin_notes'  # Fixed: use correct field names
        ]

# ===================== PAYMENT MANAGEMENT SERIALIZERS =====================

class AdminPaymentSerializer(serializers.ModelSerializer):
    """
    Payment management by admin
    """
    customer_name = serializers.CharField(source='customer.get_full_name', read_only=True)
    customer_email = serializers.CharField(source='customer.email', read_only=True)
    booking_id = serializers.CharField(source='booking.booking_id', read_only=True)
    
    class Meta:
        model = Payment
        fields = [
            'payment_id', 'booking', 'booking_id', 'customer', 'customer_name',
            'customer_email', 'amount', 'currency', 'payment_type', 'status',
            'stripe_payment_intent_id', 'refund_amount', 'failure_reason',
            'created_at', 'processed_at'
        ]


class AdminPaymentUpdateSerializer(serializers.Serializer):
    """
    Update payment status by admin
    """
    payment_id = serializers.UUIDField()
    new_status = serializers.ChoiceField(choices=Payment.PAYMENT_STATUS)
    admin_notes = serializers.CharField(required=False)


# ===================== REGION MANAGEMENT SERIALIZERS =====================

class AdminRegionSerializer(serializers.ModelSerializer):
    """
    Region management by admin
    """
    users_count = serializers.SerializerMethodField()
    professionals_count = serializers.SerializerMethodField()
    categories_count = serializers.SerializerMethodField()
    
    class Meta:
        model = Region
        fields = [
            'id', 'code', 'name', 'currency', 'currency_symbol', 'timezone',
            'country_code', 'is_active', 'default_tax_rate', 'business_start_time',
            'business_end_time', 'support_email', 'support_phone',
            'users_count', 'professionals_count', 'categories_count',
            'created_at', 'updated_at'
        ]
    
    def get_users_count(self, obj):
        return obj.current_users.filter(is_active=True).count()
    
    def get_professionals_count(self, obj):
        return obj.professionals.filter(is_active=True).count()
    
    def get_categories_count(self, obj):
        return obj.categories.filter(is_active=True).count()


class AdminRegionalSettingsSerializer(serializers.ModelSerializer):
    """
    Regional settings management
    """
    region_name = serializers.CharField(source='region.name', read_only=True)
    
    class Meta:
        model = RegionalSettings
        fields = [
            'id', 'region', 'region_name', 'key', 'value', 'value_type',
            'description', 'created_at', 'updated_at'
        ]


# ===================== SYSTEM MANAGEMENT SERIALIZERS =====================

class AdminDashboardStatsSerializer(serializers.Serializer):
    """
    Comprehensive admin dashboard statistics
    """
    # User stats
    total_users = serializers.IntegerField()
    total_customers = serializers.IntegerField()
    total_professionals = serializers.IntegerField()
    new_users_today = serializers.IntegerField()
    new_users_this_week = serializers.IntegerField()
    new_users_this_month = serializers.IntegerField()
    
    # Booking stats
    total_bookings = serializers.IntegerField()
    bookings_today = serializers.IntegerField()
    bookings_this_week = serializers.IntegerField()
    bookings_this_month = serializers.IntegerField()
    pending_bookings = serializers.IntegerField()
    confirmed_bookings = serializers.IntegerField()
    completed_bookings = serializers.IntegerField()
    
    # Revenue stats
    total_revenue = serializers.DecimalField(max_digits=15, decimal_places=2)
    revenue_today = serializers.DecimalField(max_digits=15, decimal_places=2)
    revenue_this_week = serializers.DecimalField(max_digits=15, decimal_places=2)
    revenue_this_month = serializers.DecimalField(max_digits=15, decimal_places=2)
    
    # Professional stats
    pending_verifications = serializers.IntegerField()
    verified_professionals = serializers.IntegerField()
    active_professionals = serializers.IntegerField()
    
    # System stats
    total_services = serializers.IntegerField()
    total_categories = serializers.IntegerField()
    total_regions = serializers.IntegerField()
    open_support_tickets = serializers.IntegerField()
    unresolved_alerts = serializers.IntegerField()
    
    # Growth metrics
    user_growth_rate = serializers.FloatField()
    booking_growth_rate = serializers.FloatField()
    revenue_growth_rate = serializers.FloatField()


class BulkOperationSerializer(serializers.Serializer):
    """
    Bulk operations on multiple items
    """
    OPERATION_CHOICES = [
        ('activate', 'Activate'),
        ('deactivate', 'Deactivate'),
        ('delete', 'Delete'),
        ('verify', 'Verify'),
        ('unverify', 'Unverify'),
        ('feature', 'Feature'),
        ('unfeature', 'Unfeature'),
    ]
    
    ids = serializers.ListField(child=serializers.IntegerField())
    operation = serializers.ChoiceField(choices=OPERATION_CHOICES)
    reason = serializers.CharField(required=False)


class AdminReviewModerationSerializer(serializers.ModelSerializer):
    """
    Review moderation by admin
    """
    customer_name = serializers.CharField(source='customer.get_full_name', read_only=True)
    professional_name = serializers.CharField(source='professional.user.get_full_name', read_only=True)
    service_name = serializers.CharField(source='service.name', read_only=True)
    
    class Meta:
        model = Review
        fields = [
            'id', 'customer', 'customer_name', 'professional', 'professional_name',
            'service', 'service_name', 'overall_rating', 'comment',
            'is_verified', 'is_published', 'professional_response',
            'created_at'
        ]


class AdminNotificationSerializer(serializers.ModelSerializer):
    """
    Admin notification management
    """
    user_name = serializers.CharField(source='user.get_full_name', read_only=True)
    user_email = serializers.CharField(source='user.email', read_only=True)
    sender = serializers.SerializerMethodField()
    
    class Meta:
        model = Notification
        fields = [
            'notification_id', 'user', 'user_name', 'user_email',
            'sender',
            'notification_type', 'title', 'message', 'is_read',
            'push_sent', 'email_sent', 'created_at'
        ]
    def get_sender(self, obj):
        sender = getattr(obj, 'sender', None)
        if sender:
            return {
                'id': sender.id,
                'name': sender.get_full_name(),
                'email': sender.email,
                'profile_picture': sender.profile_picture.url if sender.profile_picture else None
            }
        return None


class BroadcastNotificationSerializer(serializers.Serializer):
    """
    Send broadcast notification to users
    """
    TARGET_CHOICES = [
        ('all', 'All Users'),
        ('customers', 'All Customers'),
        ('professionals', 'All Professionals'),
        ('region', 'Users in Specific Region'),
        ('verified_professionals', 'Verified Professionals Only'),
    ]
    
    target = serializers.ChoiceField(choices=TARGET_CHOICES)
    region = serializers.PrimaryKeyRelatedField(
        queryset=Region.objects.filter(is_active=True),
        required=False
    )
    title = serializers.CharField(max_length=200)
    message = serializers.CharField()
    send_push = serializers.BooleanField(default=True)
    send_email = serializers.BooleanField(default=False)
    

class AdminProfessionalDetailSerializer(serializers.ModelSerializer):
    """
    Detailed professional information for admin
    """
    # User fields
    first_name = serializers.CharField(source='user.first_name', read_only=True)
    last_name = serializers.CharField(source='user.last_name', read_only=True)
    email = serializers.EmailField(source='user.email', read_only=True)
    phone_number = serializers.CharField(source='user.phone_number', read_only=True)
    gender = serializers.CharField(source='user.gender', read_only=True)
    date_of_birth = serializers.DateField(source='user.date_of_birth', read_only=True)
    profile_picture = serializers.ImageField(source='user.profile_picture', read_only=True)
    user_is_active = serializers.BooleanField(source='user.is_active', read_only=True)
    date_joined = serializers.DateTimeField(source='user.date_joined', read_only=True)
    
    # Professional stats
    total_bookings = serializers.SerializerMethodField()
    total_earnings = serializers.SerializerMethodField()
    regions_served = serializers.SerializerMethodField()
    services_offered = serializers.SerializerMethodField()
    availability_by_region = serializers.SerializerMethodField()
    
    class Meta:
        model = Professional
        fields = [
            'id', 'first_name', 'last_name', 'email', 'phone_number', 'gender', 'date_of_birth', 'profile_picture', 'user_is_active', 'date_joined',
            'bio', 'experience_years', 'rating', 'total_reviews', 'is_verified', 'is_active',
            'travel_radius_km', 'min_booking_notice_hours', 'cancellation_policy', 'commission_rate',
            'total_bookings', 'total_earnings', 'regions_served', 'services_offered', 'availability_by_region',
            'created_at', 'updated_at', 'verified_at'
        ]
    
    def get_total_bookings(self, obj):
        try:
            return obj.bookings.count()
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Error getting total bookings for professional {obj.id}: {str(e)}")
            return 0
    
    def get_total_earnings(self, obj):
        try:
            from bookings.models import Booking
            completed_bookings = obj.bookings.filter(status='completed')
            return float(sum(booking.total_amount for booking in completed_bookings))
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Error getting total earnings for professional {obj.id}: {str(e)}")
            return 0.0
    
    def get_regions_served(self, obj):
        try:
            return [{'id': r.id, 'name': r.name, 'code': r.code} for r in obj.regions.all()]
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Error getting regions served for professional {obj.id}: {str(e)}")
            return []
    
    def get_services_offered(self, obj):
        try:
            services = obj.services.all()
            return [{'id': s.id, 'name': s.name, 'category': s.category.name} for s in services]
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Error getting services offered for professional {obj.id}: {str(e)}")
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
                        'weekday': availability.weekday,
                        'weekday_name': availability.get_weekday_display(),
                        'start_time': availability.start_time.strftime('%H:%M') if availability.start_time else None,
                        'end_time': availability.end_time.strftime('%H:%M') if availability.end_time else None,
                        'break_start': availability.break_start.strftime('%H:%M') if availability.break_start else None,
                        'break_end': availability.break_end.strftime('%H:%M') if availability.break_end else None,
                        'is_active': availability.is_active
                    })
                except Exception as e:
                    # Log individual availability errors but continue
                    import logging
                    logger = logging.getLogger(__name__)
                    logger.error(f"Error processing availability {availability.id}: {str(e)}")
                    continue
            
            return list(availability_data.values())
        except Exception as e:
            # Log any errors in the method
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Error in get_availability_by_region for professional {obj.id}: {str(e)}")
            return []
    
    

class SystemAlertSerializer(serializers.ModelSerializer):
    """
    System alert serializer for admin
    """
    related_user_name = serializers.CharField(source='related_user.get_full_name', read_only=True)
    resolved_by_name = serializers.CharField(source='resolved_by.get_full_name', read_only=True)
    
    class Meta:
        model = SystemAlert
        fields = [
            'alert_id', 'title', 'message', 'alert_type', 'category',
            'related_user', 'related_user_name', 'related_booking', 'related_payment',
            'is_resolved', 'resolved_by', 'resolved_by_name', 'resolved_at',
            'resolution_notes', 'created_at'
        ]


class SupportTicketSerializer(serializers.ModelSerializer):
    """
    Support ticket serializer for admin
    """
    customer_name = serializers.CharField(source='customer.get_full_name', read_only=True)
    assigned_to_name = serializers.CharField(source='assigned_to.get_full_name', read_only=True)
    
    class Meta:
        model = SupportTicket
        fields = [
            'ticket_id', 'customer', 'customer_name', 'subject', 'description',
            'category', 'priority', 'status', 'assigned_to', 'assigned_to_name',
            'related_booking', 'created_at', 'updated_at', 'resolved_at'
        ]





