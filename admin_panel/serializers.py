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
    Serializer for professional availability data in admin operations
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
        if attrs['end_time'] <= attrs['start_time']:
            raise serializers.ValidationError("End time must be after start time")
        
        # Validate break times if provided
        if attrs.get('break_start') and attrs.get('break_end'):
            if attrs['break_end'] <= attrs['break_start']:
                raise serializers.ValidationError("Break end time must be after break start time")
            
            # Validate break is within working hours
            if (attrs['break_start'] < attrs['start_time'] or 
                attrs['break_end'] > attrs['end_time']):
                raise serializers.ValidationError("Break time must be within working hours")
        
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
    date_of_birth = serializers.DateField(required=False)
    gender = serializers.CharField(required=False)
    profile_picture = serializers.ImageField(required=False)
    
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
            'date_of_birth', 'gender', 'profile_picture',
            'bio', 'experience_years', 'is_verified', 'is_active',
            'travel_radius_km', 'min_booking_notice_hours', 'commission_rate',
            'regions', 'services', 'availability'
        ]
    
    def validate_email(self, value):
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError("A user with this email already exists.")
        return value
    
    def create(self, validated_data):
        # Extract user fields
        user_fields = {
            'first_name': validated_data.pop('first_name'),
            'last_name': validated_data.pop('last_name'),
            'email': validated_data.pop('email'),
            'phone_number': validated_data.pop('phone_number', ''),
            'date_of_birth': validated_data.pop('date_of_birth', None),
            'gender': validated_data.pop('gender', ''),
            'profile_picture': validated_data.pop('profile_picture', None),
            'user_type': 'professional'
        }
        password = validated_data.pop('password')
        regions = validated_data.pop('regions')
        services = validated_data.pop('services')
        availability_data = validated_data.pop('availability', [])
        
        # Set default values for admin-created professionals
        validated_data.setdefault('is_verified', True)
        validated_data.setdefault('is_active', True)
        
        # Create user
        user = User.objects.create_user(
            username=user_fields['email'],
            **user_fields
        )
        user.set_password(password)
        user.current_region = regions[0] if regions else None
        user.save()
        
        # Create professional
        professional = Professional.objects.create(
            user=user,
            **validated_data
        )
        
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
            except Region.DoesNotExist:
                # Skip if region doesn't exist
                continue
        
        return professional
    
    def to_representation(self, instance):
        # Return only the professional id to avoid AttributeError
        return {'id': instance.id}


class AdminProfessionalUpdateSerializer(serializers.ModelSerializer):
    """
    Update professional by admin
    """
    # User fields
    first_name = serializers.CharField(source='user.first_name')
    last_name = serializers.CharField(source='user.last_name')
    email = serializers.EmailField(source='user.email')
    phone_number = serializers.CharField(source='user.phone_number', required=False)
    date_of_birth = serializers.DateField(source='user.date_of_birth', required=False)
    gender = serializers.CharField(source='user.gender', required=False)
    profile_picture = serializers.ImageField(source='user.profile_picture', required=False)
    user_is_active = serializers.BooleanField(source='user.is_active')
    regions = serializers.PrimaryKeyRelatedField(queryset=Region.objects.filter(is_active=True), many=True)
    services = serializers.PrimaryKeyRelatedField(queryset=Service.objects.filter(is_active=True), many=True)
    
    # Professional status fields
    is_verified = serializers.BooleanField(required=False)
    is_active = serializers.BooleanField(required=False)
    
    # Availability data
    availability = ProfessionalAvailabilityDataSerializer(many=True, required=False)
    
    class Meta:
        model = Professional
        fields = [
            'first_name', 'last_name', 'email', 'phone_number', 'date_of_birth', 'gender', 'profile_picture',
            'user_is_active', 'bio', 'experience_years', 'is_verified', 'is_active',
            'travel_radius_km', 'min_booking_notice_hours', 'cancellation_policy',
            'commission_rate', 'regions', 'services', 'availability'
        ]
    
    def to_internal_value(self, data):
        # Remove user fields from data before processing to avoid assignment error
        user_fields = ['first_name', 'last_name', 'email', 'phone_number', 'user_is_active']
        internal_data = data.copy()
        
        # Store user data separately
        self.user_data = {}
        for field in user_fields:
            if field in internal_data:
                self.user_data[field] = internal_data.pop(field)
        
        return super().to_internal_value(internal_data)
    
    def update(self, instance, validated_data):
        # Handle user fields using the data stored in to_internal_value
        if hasattr(self, 'user_data') and self.user_data:
            # Map serializer field names to user model field names
            field_mapping = {
                'first_name': 'first_name',
                'last_name': 'last_name',
                'email': 'email', 
                'phone_number': 'phone_number',
                'user_is_active': 'is_active'
            }
            
            for serializer_field, user_field in field_mapping.items():
                if serializer_field in self.user_data:
                    setattr(instance.user, user_field, self.user_data[serializer_field])
            instance.user.save()
        
        # Extract other fields
        regions = validated_data.pop('regions', None)
        services = validated_data.pop('services', None)
        availability_data = validated_data.pop('availability', None)
        
        # Update professional fields (excluding user fields)
        for field, value in validated_data.items():
            setattr(instance, field, value)
        instance.save()
        
        # Handle regions and services updates
        if regions is not None:
            instance.regions.set(regions)
            
            # Update ProfessionalService entries if services are also provided
            if services is not None:
                # Clear existing ProfessionalService entries
                instance.professionalservice_set.all().delete()
                
                # Create new ProfessionalService entries for each region-service combination
                for region in regions:
                    for service in services:
                        ProfessionalService.objects.create(
                            professional=instance,
                            service=service,
                            region=region
                        )
            else:
                # If only regions changed, update ProfessionalService entries for existing services
                existing_services = instance.services.all()
                instance.professionalservice_set.all().delete()
                for region in regions:
                    for service in existing_services:
                        ProfessionalService.objects.create(
                            professional=instance,
                            service=service,
                            region=region
                        )
        elif services is not None:
            # Only services changed, update ProfessionalService entries for existing regions
            existing_regions = instance.regions.all()
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
            try:
                # Clear existing availability for this professional
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
                    except Region.DoesNotExist:
                        # Skip if region doesn't exist
                        continue
                    except Exception as e:
                        # Log any other errors but continue
                        import logging
                        logger = logging.getLogger(__name__)
                        logger.error(f"Error creating availability for professional {instance.id}: {str(e)}")
                        continue
            except Exception as e:
                # Log any errors in availability handling
                import logging
                logger = logging.getLogger(__name__)
                logger.error(f"Error updating availability for professional {instance.id}: {str(e)}")
        
        return instance


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
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Error getting total bookings for professional {obj.id}: {str(e)}")
            return 0
    
    def get_total_earnings(self, obj):
        try:
            from bookings.models import Booking
            completed_bookings = Booking.objects.filter(
                professional=obj, 
                status='completed'
            )
            return float(sum(booking.total_amount for booking in completed_bookings))
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Error getting total earnings for professional {obj.id}: {str(e)}")
            return 0.0
    
    def get_regions_served(self, obj):
        try:
            return [{
                'id': r.id, 
                'name': r.name, 
                'code': r.code,
                'is_primary': obj.professionalregion_set.filter(region=r).first().is_primary if obj.professionalregion_set.filter(region=r).exists() else False
            } for r in obj.regions.all()]
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Error getting regions served for professional {obj.id}: {str(e)}")
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
                        'id': availability.id,
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
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Error getting documents for professional {obj.id}: {str(e)}")
            return []
    
    def get_verification_documents(self, obj):
        """Get verification documents list"""
        try:
            return obj.verification_documents
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Error getting verification documents for professional {obj.id}: {str(e)}")
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
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Error getting profile completion status for professional {obj.id}: {str(e)}")
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
