from rest_framework import serializers
from django.utils import timezone
from decimal import Decimal
from datetime import datetime, timedelta

from .models import (
    Booking, BookingAddOn, Review, BookingReschedule, 
    BookingMessage, BookingStatusHistory, BookingPicture
)
from accounts.serializers import UserSerializer
from professionals.serializers import ProfessionalListSerializer
from services.serializers import ServiceSerializer, AddOnSerializer


class BookingAddOnSerializer(serializers.ModelSerializer):
    """
    Booking add-on serializer
    """
    addon = AddOnSerializer(read_only=True)
    total_price = serializers.ReadOnlyField()
    
    class Meta:
        model = BookingAddOn
        fields = ['id', 'addon', 'quantity', 'price_at_booking', 'total_price']


class BookingListSerializer(serializers.ModelSerializer):
    """
    Booking list serializer (lightweight for listings)
    """
    customer_name = serializers.CharField(source='customer.get_full_name', read_only=True)
    professional_name = serializers.CharField(source='professional.user.get_full_name', read_only=True)
    service_name = serializers.CharField(source='service.name', read_only=True)
    region_name = serializers.CharField(source='region.name', read_only=True)
    is_upcoming = serializers.ReadOnlyField()
    can_be_cancelled = serializers.ReadOnlyField()
    
    class Meta:
        model = Booking
        fields = [
            'booking_id', 'customer_name', 'professional_name', 'service_name',
            'region_name', 'scheduled_date', 'scheduled_time', 'duration_minutes',
            'total_amount', 'status', 'payment_status', 'is_upcoming',
            'can_be_cancelled', 'created_at'
        ]


class BookingDetailSerializer(serializers.ModelSerializer):
    """
    Detailed booking serializer
    """
    customer = UserSerializer(read_only=True)
    professional = ProfessionalListSerializer(read_only=True)
    service = ServiceSerializer(read_only=True)
    selected_addons = BookingAddOnSerializer(many=True, read_only=True)
    region_name = serializers.CharField(source='region.name', read_only=True)
    is_upcoming = serializers.ReadOnlyField()
    can_be_cancelled = serializers.ReadOnlyField()
    
    # Before and after pictures
    before_pictures = serializers.SerializerMethodField()
    after_pictures = serializers.SerializerMethodField()
    picture_counts = serializers.SerializerMethodField()
    
    class Meta:
        model = Booking
        fields = [
            'booking_id', 'customer', 'professional', 'service', 'region_name',
            'booking_for_self', 'recipient_name', 'recipient_phone', 'recipient_email',
            'scheduled_date', 'scheduled_time', 'duration_minutes',
            'address_line1', 'address_line2', 'city', 'postal_code', 'location_notes',
            'base_amount', 'addon_amount', 'discount_amount', 'tax_amount', 'total_amount',
            'deposit_required', 'deposit_percentage', 'deposit_amount', 'status', 'payment_status',
            'customer_notes', 'professional_notes', 'selected_addons',
            'before_pictures', 'after_pictures', 'picture_counts',
            'is_upcoming', 'can_be_cancelled', 'created_at', 'confirmed_at'
        ]
    
    def get_before_pictures(self, obj):
        """Get before pictures for the booking"""
        before_pics = obj.pictures.filter(picture_type='before').order_by('uploaded_at')
        return BookingPictureSerializer(before_pics, many=True, context=self.context).data
    
    def get_after_pictures(self, obj):
        """Get after pictures for the booking"""
        after_pics = obj.pictures.filter(picture_type='after').order_by('uploaded_at')
        return BookingPictureSerializer(after_pics, many=True, context=self.context).data
    
    def get_picture_counts(self, obj):
        """Get picture counts for easy reference"""
        before_count = obj.pictures.filter(picture_type='before').count()
        after_count = obj.pictures.filter(picture_type='after').count()
        return {
            'before': before_count,
            'after': after_count,
            'total': before_count + after_count
        }


class BookingCreateSerializer(serializers.ModelSerializer):
    """
    Create booking serializer with server-side payment calculation
    """
    selected_addons = serializers.ListField(
        child=serializers.DictField(),
        write_only=True,
        required=False
    )
    
    # Payment type selection
    payment_type = serializers.ChoiceField(
        choices=[
            ('full', 'Full Payment'),
            ('partial', 'Partial Payment (50%)')
        ],
        default='partial',
        write_only=True,
        help_text="Choose 'full' to pay the entire amount upfront, or 'partial' to pay 50% now and 50% later"
    )
    
    # Remove discount_amount from frontend - calculate server-side only
    # discount_amount = ... (removed)
    
    # Read-only fields for response
    payment_amount = serializers.DecimalField(
        max_digits=10,
        decimal_places=2,
        read_only=True,
        help_text="The actual amount to be charged based on payment type"
    )
    
    class Meta:
        model = Booking
        fields = [
            'booking_id',  # <-- Add this field to the output
            'professional', 'service', 'scheduled_date', 'scheduled_time',
            'booking_for_self', 'recipient_name', 'recipient_phone', 'recipient_email',
            'address_line1', 'address_line2', 'city', 'postal_code', 'location_notes',
            'customer_notes', 'selected_addons', 'payment_type', 'payment_amount'
        ]
    
    def validate_scheduled_date(self, value):
        """Validate booking date is in the future"""
        if value < timezone.now().date():
            raise serializers.ValidationError("Cannot book for past dates")
        return value
    
    def validate(self, attrs):
        """Validate booking details"""
        professional = attrs['professional']
        service = attrs['service']
        scheduled_date = attrs['scheduled_date']
        scheduled_time = attrs['scheduled_time']
        
        # Check if professional offers this service
        region = self.context['region']
        if not professional.services.filter(
            id=service.id,
            professionalservice__region=region,
            professionalservice__is_active=True
        ).exists():
            raise serializers.ValidationError(
                "Professional does not offer this service in this region"
            )
        
        # Check professional availability
        weekday = scheduled_date.weekday()
        availability = professional.availability_schedule.filter(
            region=region,
            weekday=weekday,
            start_time__lte=scheduled_time,
            end_time__gte=scheduled_time,
            is_active=True
        )
        
        if not availability.exists():
            raise serializers.ValidationError(
                "Professional is not available at the selected time"
            )
        
        # Check for existing bookings at the same time
        existing_booking = Booking.objects.filter(
            professional=professional,
            scheduled_date=scheduled_date,
            scheduled_time=scheduled_time,
            status__in=['confirmed', 'in_progress']
        ).exists()
        
        if existing_booking:
            raise serializers.ValidationError(
                "Professional already has a booking at this time"
            )
        
        return attrs
    
    def create(self, validated_data):
        selected_addons = validated_data.pop('selected_addons', [])
        payment_type = validated_data.pop('payment_type', 'partial')
        
        user = self.context['request'].user
        region = self.context['region']
        
        # Get service pricing (SERVER-SIDE CALCULATION)
        professional = validated_data['professional']
        service = validated_data['service']
        
        try:
            professional_service = professional.professionalservice_set.get(
                service=service,
                region=region,
                is_active=True
            )
            base_price = professional_service.get_price()
        except:
            base_price = service.get_regional_price(region)
        
        # Calculate add-on total (SERVER-SIDE CALCULATION)
        addon_total = Decimal('0.00')
        addon_items = []
        
        for addon_data in selected_addons:
            addon_id = addon_data.get('addon_id')
            quantity = max(1, addon_data.get('quantity', 1))  # Ensure positive quantity
            
            try:
                addon = service.category.addons.get(id=addon_id, is_active=True)
                addon_items.append({
                    'addon': addon,
                    'quantity': quantity,
                    'price': addon.price
                })
                addon_total += addon.price * quantity
            except:
                continue
        
        # Calculate tax based on region (SERVER-SIDE CALCULATION)
        tax_rate = self._get_tax_rate(region)
        subtotal = base_price + addon_total
        tax_amount = subtotal * tax_rate / 100
        
        # Apply any server-side discounts (if applicable)
        discount_amount = self._calculate_discount(user, service, subtotal)
        
        # Calculate total amount (SERVER-SIDE CALCULATION)
        total_amount = base_price + addon_total + tax_amount - discount_amount
        
        # Validate total amount is positive
        if total_amount <= 0:
            raise serializers.ValidationError(
                "Invalid booking calculation. Please contact support."
            )
        
        # Calculate payment amounts based on payment type (SERVER-SIDE CALCULATION)
        if payment_type == 'full':
            # Full payment: pay entire amount upfront
            deposit_amount = total_amount
            payment_amount = total_amount
            deposit_required = False
            deposit_percentage = Decimal('100.00')
        else:
            # Partial payment: pay 50% now, 50% later
            deposit_percentage = Decimal('50.00')
            deposit_amount = (total_amount * deposit_percentage) / 100
            payment_amount = deposit_amount
            deposit_required = True
        
        # Ensure payment amount is valid
        if payment_amount <= 0:
            raise serializers.ValidationError(
                "Payment amount must be greater than zero"
            )
        
        # Create booking with calculated amounts
        booking = Booking.objects.create(
            customer=user,
            region=region,
            duration_minutes=service.duration_minutes,
            base_amount=base_price,
            addon_amount=addon_total,
            tax_amount=tax_amount,
            discount_amount=discount_amount,
            total_amount=total_amount,
            deposit_required=deposit_required,
            deposit_percentage=deposit_percentage,
            deposit_amount=deposit_amount,
            **validated_data
        )
        
        # Create add-on records
        for addon_item in addon_items:
            BookingAddOn.objects.create(
                booking=booking,
                addon=addon_item['addon'],
                quantity=addon_item['quantity'],
                price_at_booking=addon_item['price']
            )
        
        # Store payment information for the view
        booking._payment_amount = payment_amount
        booking._payment_type = payment_type
        
        # Schedule reminders
        try:
            from .tasks import schedule_booking_reminders
            schedule_booking_reminders.delay(booking.id)
        except Exception as e:
            # Log error but don't fail the booking creation
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Failed to schedule reminders for booking {booking.id}: {str(e)}")
        
        return booking
    
    def _get_tax_rate(self, region):
        """Get tax rate based on region (SERVER-SIDE CALCULATION)"""
        tax_rates = {
            'UK': Decimal('20.00'),    # VAT 20%
            'UAE': Decimal('5.00'),    # VAT 5%
        }
        return tax_rates.get(region.code, Decimal('0.00'))
    
    def _calculate_discount(self, user, service, subtotal):
        """Calculate any applicable discounts (SERVER-SIDE CALCULATION)"""
        discount_amount = Decimal('0.00')
        
        # Example discount logic (implement based on business rules)
        # First-time customer discount
        if not user.bookings.exists():
            discount_amount = min(subtotal * Decimal('0.10'), Decimal('10.00'))  # 10% max £10
        
        # Loyalty discount for frequent customers
        elif user.bookings.filter(status='completed').count() >= 5:
            discount_amount = subtotal * Decimal('0.05')  # 5% loyalty discount
        
        # Service-specific promotions
        if hasattr(service, 'promotion_discount'):
            promo_discount = subtotal * (service.promotion_discount / 100)
            discount_amount = max(discount_amount, promo_discount)
        
        return discount_amount
    
    def to_representation(self, instance):
        """Add payment_amount to the response"""
        data = super().to_representation(instance)
        if hasattr(instance, '_payment_amount'):
            data['payment_amount'] = str(instance._payment_amount)
        return data


class BookingUpdateSerializer(serializers.ModelSerializer):
    """
    Update booking serializer (limited fields)
    """
    class Meta:
        model = Booking
        fields = [
            'recipient_name', 'recipient_phone', 'recipient_email',
            'address_line1', 'address_line2', 'city', 'postal_code',
            'location_notes', 'customer_notes'
        ]


class ReviewSerializer(serializers.ModelSerializer):
    """
    Review serializer
    """
    customer = UserSerializer(read_only=True)
    professional = ProfessionalListSerializer(read_only=True)
    service = ServiceSerializer(read_only=True)
    
    class Meta:
        model = Review
        fields = [
            'id', 'customer', 'professional', 'service', 'overall_rating',
            'service_rating', 'professional_rating', 'value_rating',
            'comment', 'would_recommend', 'professional_response',
            'response_date', 'created_at'
        ]


class ReviewCreateSerializer(serializers.ModelSerializer):
    """
    Create review serializer
    """
    class Meta:
        model = Review
        fields = [
            'overall_rating', 'service_rating', 'professional_rating',
            'value_rating', 'comment', 'would_recommend'
        ]
    
    def create(self, validated_data):
        booking = self.context['booking']
        
        # Check if booking is completed
        if booking.status != 'completed':
            raise serializers.ValidationError("Can only review completed bookings")
        
        # Check if review already exists
        if hasattr(booking, 'review'):
            raise serializers.ValidationError("Review already exists for this booking")
        
        return Review.objects.create(
            booking=booking,
            customer=booking.customer,
            professional=booking.professional,
            service=booking.service,
            **validated_data
        )


class BookingRescheduleSerializer(serializers.ModelSerializer):
    """
    Booking reschedule request serializer (customer can only request, admin assigns date)
    """
    class Meta:
        model = BookingReschedule
        fields = [
            'id', 'reason', 'status', 'response_reason', 'created_at', 'expires_at'
        ]
        read_only_fields = ['status', 'response_reason', 'expires_at']
    
    def create(self, validated_data):
        booking = self.context['booking']
        user = self.context['request'].user
        
        # Set expiration (48 hours)
        expires_at = timezone.now() + timedelta(hours=48)
        
        # Create reschedule request without specific date/time
        # Admin will assign the new date/time when approving
        reschedule_request = BookingReschedule.objects.create(
            booking=booking,
            requested_by=user,
            original_date=booking.scheduled_date,
            original_time=booking.scheduled_time,
            requested_date=booking.scheduled_date,  # Placeholder - admin will update
            requested_time=booking.scheduled_time,  # Placeholder - admin will update
            expires_at=expires_at,
            **validated_data
        )
        
        # Notify admin about reschedule request (optional - don't fail if this fails)
        try:
            from notifications.tasks import create_notification
            create_notification.delay(
                user_id=1,  # Assuming admin user ID is 1, adjust as needed
                notification_type='reschedule_requested',
                title='New Reschedule Request',
                message=f'Customer {user.get_full_name()} has requested to reschedule booking {booking.booking_id} (currently scheduled for {booking.scheduled_date} at {booking.scheduled_time}). Reason: {validated_data.get("reason", "No reason provided")}. Please assign a new date/time.',
                related_booking_id=booking.id
            )
        except Exception as e:
            # Log error but don't fail the reschedule request creation
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Failed to send reschedule notification to admin: {str(e)}")
            # Continue without notification - reschedule request is still created successfully
        
        return reschedule_request


class BookingMessageSerializer(serializers.ModelSerializer):
    """
    Booking message serializer
    """
    sender = UserSerializer(read_only=True)
    
    class Meta:
        model = BookingMessage
        fields = [
            'id', 'sender', 'message', 'is_read', 'message_type', 'created_at'
        ]
        read_only_fields = ['sender', 'message_type']


class BookingPictureSerializer(serializers.ModelSerializer):
    """
    Serializer for displaying booking pictures
    """
    uploaded_by_name = serializers.CharField(source='uploaded_by.get_full_name', read_only=True)
    file_size_mb = serializers.ReadOnlyField()
    image_url = serializers.SerializerMethodField()
    
    class Meta:
        model = BookingPicture
        fields = [
            'id', 'picture_type', 'image', 'image_url', 'caption', 
            'uploaded_by_name', 'uploaded_at', 'file_size', 'file_size_mb', 
            'width', 'height'
        ]
        read_only_fields = [
            'uploaded_by_name', 'uploaded_at', 'file_size', 'file_size_mb',
            'width', 'height', 'image_url'
        ]
    
    def get_image_url(self, obj):
        """Get full URL for the image"""
        if obj.image:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.image.url)
            return obj.image.url
        return None
    
    def validate_image(self, value):
        """Validate image file"""
        # Check file size (max 10MB)
        if value.size > 10 * 1024 * 1024:
            raise serializers.ValidationError("Image file size cannot exceed 10MB.")
        
        # Check file format
        allowed_formats = ['image/jpeg', 'image/jpg', 'image/png', 'image/webp']
        if hasattr(value, 'content_type') and value.content_type not in allowed_formats:
            raise serializers.ValidationError(
                "Only JPEG, PNG, and WebP image formats are allowed."
            )
        
        return value


class BookingPictureUploadSerializer(serializers.Serializer):
    """
    Serializer for uploading multiple booking pictures at once
    """
    booking_id = serializers.UUIDField(help_text="UUID of the booking to add pictures to")
    picture_type = serializers.ChoiceField(
        choices=BookingPicture.PICTURE_TYPE_CHOICES,
        help_text="Type of pictures being uploaded (before or after)"
    )
    images = serializers.ListField(
        child=serializers.ImageField(),
        min_length=1,
        max_length=6,
        help_text="Upload 1-6 images at once"
    )
    captions = serializers.ListField(
        child=serializers.CharField(max_length=255, allow_blank=True),
        required=False,
        allow_empty=True,
        help_text="Optional captions for each image (must match number of images)"
    )
    
    def validate(self, data):
        """Validate the upload data"""
        images = data.get('images', [])
        captions = data.get('captions', [])
        booking_id = data.get('booking_id')
        picture_type = data.get('picture_type')
        
        # Validate image count
        if len(images) < 1 or len(images) > 6:
            raise serializers.ValidationError("You must upload between 1 and 6 images.")
        
        # Validate captions count if provided
        if captions and len(captions) != len(images):
            raise serializers.ValidationError(
                "Number of captions must match number of images if captions are provided."
            )
        
        # Validate booking exists
        try:
            booking = Booking.objects.get(booking_id=booking_id)
        except Booking.DoesNotExist:
            raise serializers.ValidationError("Booking not found.")
        
        # Check if we can add these pictures without exceeding limit
        if not BookingPicture.can_add_pictures(booking, picture_type, len(images)):
            current_count = BookingPicture.get_picture_count(booking, picture_type)
            raise serializers.ValidationError(
                f"Cannot upload {len(images)} more {picture_type} pictures. "
                f"This booking already has {current_count} {picture_type} pictures. "
                f"Maximum allowed is 6 per type."
            )
        
        # Validate each image individually
        for i, image in enumerate(images):
            # Check file size (max 10MB)
            if image.size > 10 * 1024 * 1024:
                raise serializers.ValidationError(f"Image {i+1}: File size cannot exceed 10MB.")
            
            # Check file format
            allowed_formats = ['image/jpeg', 'image/jpg', 'image/png', 'image/webp']
            if hasattr(image, 'content_type') and image.content_type not in allowed_formats:
                raise serializers.ValidationError(
                    f"Image {i+1}: Only JPEG, PNG, and WebP formats are allowed."
                )
        
        return data
    
    def create_pictures(self, validated_data, uploaded_by):
        """
        Create BookingPicture instances from validated data
        """
        booking = Booking.objects.get(booking_id=validated_data['booking_id'])
        images = validated_data['images']
        captions = validated_data.get('captions', [])
        picture_type = validated_data['picture_type']
        
        created_pictures = []
        
        for i, image in enumerate(images):
            caption = captions[i] if i < len(captions) else ''
            
            picture = BookingPicture.objects.create(
                booking=booking,
                picture_type=picture_type,
                image=image,
                caption=caption,
                uploaded_by=uploaded_by
            )
            created_pictures.append(picture)
        
        return created_pictures