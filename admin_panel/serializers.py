from rest_framework import serializers
from django.db.models import Q, Count, Avg, Sum
from datetime import datetime, timedelta
from django.utils import timezone
from django.contrib.auth.password_validation import validate_password

from .models import AdminActivity, SystemAlert, SupportTicket, TicketMessage
from accounts.models import User
from professionals.models import Professional, ProfessionalAvailability, ProfessionalService
from bookings.models import Booking, Review
from payments.models import Payment, SavedPaymentMethod
from services.models import Category, Service, AddOn, RegionalPricing
from regions.models import Region, RegionalSettings
from notifications.models import Notification

# ===================== USER MANAGEMENT SERIALIZERS =====================

class AdminUserCreateSerializer(serializers.ModelSerializer):
    """
    Create user by admin
    """
    password = serializers.CharField(write_only=True, validators=[validate_password])
    
    class Meta:
        model = User
        fields = [
            'first_name', 'last_name', 'email', 'password', 'user_type',
            'phone_number', 'current_region', 'is_active', 'is_verified'
        ]
    
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
    class Meta:
        model = User
        fields = [
            'first_name', 'last_name', 'email', 'user_type', 'phone_number',
            'current_region', 'is_active', 'is_verified', 'profile_completed'
        ]


class AdminUserDetailSerializer(serializers.ModelSerializer):
    """
    Detailed user information for admin
    """
    total_bookings = serializers.SerializerMethodField()
    total_spent = serializers.SerializerMethodField()
    last_activity = serializers.DateTimeField(source='last_login', read_only=True)
    current_region_name = serializers.CharField(source='current_region.name', read_only=True)
    
    class Meta:
        model = User
        fields = [
            'id', 'uid', 'first_name', 'last_name', 'email', 'username',
            'user_type', 'phone_number', 'current_region', 'current_region_name',
            'is_active', 'is_verified', 'profile_completed', 'date_joined',
            'last_login', 'last_activity', 'total_bookings', 'total_spent'
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
    
    # Professional fields
    regions = serializers.PrimaryKeyRelatedField(
        queryset=Region.objects.filter(is_active=True),
        many=True
    )
    services = serializers.PrimaryKeyRelatedField(
        queryset=Service.objects.filter(is_active=True),
        many=True
    )
    
    class Meta:
        model = Professional
        fields = [
            'first_name', 'last_name', 'email', 'password', 'phone_number',
            'bio', 'experience_years', 'is_verified', 'is_active',
            'travel_radius_km', 'min_booking_notice_hours', 'commission_rate',
            'regions', 'services'
        ]
    
    def create(self, validated_data):
        # Extract user fields
        user_fields = {
            'first_name': validated_data.pop('first_name'),
            'last_name': validated_data.pop('last_name'),
            'email': validated_data.pop('email'),
            'phone_number': validated_data.pop('phone_number', ''),
            'user_type': 'professional'
        }
        password = validated_data.pop('password')
        regions = validated_data.pop('regions')
        services = validated_data.pop('services')
        
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
        
        return professional


class AdminProfessionalUpdateSerializer(serializers.ModelSerializer):
    """
    Update professional by admin
    """
    # User fields
    first_name = serializers.CharField(source='user.first_name')
    last_name = serializers.CharField(source='user.last_name')
    email = serializers.EmailField(source='user.email')
    phone_number = serializers.CharField(source='user.phone_number', required=False)
    user_is_active = serializers.BooleanField(source='user.is_active')
    
    class Meta:
        model = Professional
        fields = [
            'first_name', 'last_name', 'email', 'phone_number', 'user_is_active',
            'bio', 'experience_years', 'is_verified', 'is_active',
            'travel_radius_km', 'min_booking_notice_hours', 'commission_rate'
        ]
    
    def update(self, instance, validated_data):
        user_data = {}
        if 'user' in validated_data:
            user_data = validated_data.pop('user')
        
        # Update user fields
        if user_data:
            for field, value in user_data.items():
                setattr(instance.user, field, value)
            instance.user.save()
        
        # Update professional fields
        for field, value in validated_data.items():
            setattr(instance, field, value)
        
        instance.save()
        return instance


# ===================== CATEGORY MANAGEMENT SERIALIZERS =====================

class AdminCategorySerializer(serializers.ModelSerializer):
    """
    Category management by admin
    """
    services_count = serializers.SerializerMethodField()
    
    class Meta:
        model = Category
        fields = [
            'id', 'name', 'description', 'icon', 'region', 'is_active',
            'sort_order', 'slug', 'meta_description', 'services_count',
            'created_at', 'updated_at'
        ]
    
    def get_services_count(self, obj):
        return obj.services.filter(is_active=True).count()


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
    category_name = serializers.CharField(source='category.name', read_only=True)
    region_name = serializers.CharField(source='category.region.name', read_only=True)
    
    class Meta:
        model = AddOn
        fields = [
            'id', 'name', 'description', 'category', 'category_name', 'region_name',
            'price', 'duration_minutes', 'is_active', 'max_quantity',
            'created_at', 'updated_at'
        ]


# ===================== BOOKING MANAGEMENT SERIALIZERS =====================

class AdminBookingSerializer(serializers.ModelSerializer):
    """
    Booking management by admin - FIXED field names
    """
    customer_name = serializers.CharField(source='customer.get_full_name', read_only=True)
    customer_email = serializers.CharField(source='customer.email', read_only=True)
    professional_name = serializers.CharField(source='professional.user.get_full_name', read_only=True)
    service_name = serializers.CharField(source='service.name', read_only=True)
    region_name = serializers.CharField(source='region.name', read_only=True)
    
    class Meta:
        model = Booking
        fields = [
            'booking_id', 'customer', 'customer_name', 'customer_email',
            'professional', 'professional_name', 'service', 'service_name',
            'region', 'region_name', 'scheduled_date', 'scheduled_time',
            'duration_minutes', 'total_amount', 'status', 'payment_status',
            'booking_for_self', 'recipient_name', 'customer_notes', 'created_at'  # Fixed: customer_notes instead of notes
        ]

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
    
    class Meta:
        model = Notification
        fields = [
            'notification_id', 'user', 'user_name', 'user_email',
            'notification_type', 'title', 'message', 'is_read',
            'push_sent', 'email_sent', 'created_at'
        ]


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
    
    # Professional stats
    total_bookings = serializers.SerializerMethodField()
    total_earnings = serializers.SerializerMethodField()
    regions_served = serializers.SerializerMethodField()
    services_offered = serializers.SerializerMethodField()
    
    class Meta:
        model = Professional
        fields = [
            'id', 'first_name', 'last_name', 'email', 'phone_number', 'user_is_active',
            'date_joined', 'bio', 'experience_years', 'rating', 'total_reviews',
            'is_verified', 'is_active', 'travel_radius_km', 'min_booking_notice_hours',
            'commission_rate', 'total_bookings', 'total_earnings', 'regions_served',
            'services_offered', 'verified_at', 'created_at'
        ]
    
    def get_total_bookings(self, obj):
        return obj.bookings.count()
    
    def get_total_earnings(self, obj):
        from bookings.models import Booking
        completed_bookings = obj.bookings.filter(status='completed')
        return float(sum(booking.total_amount for booking in completed_bookings))
    
    def get_regions_served(self, obj):
        return [{'id': r.id, 'name': r.name, 'code': r.code} for r in obj.regions.all()]
    
    def get_services_offered(self, obj):
        services = obj.services.all()
        return [{'id': s.id, 'name': s.name, 'category': s.category.name} for s in services]
    
    

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
