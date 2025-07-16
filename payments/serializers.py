from rest_framework import serializers
from decimal import Decimal
from .models import Payment, SavedPaymentMethod, PaymentRefund


class PaymentMethodSerializer(serializers.ModelSerializer):
    """
    Saved payment method serializer
    """
    class Meta:
        model = SavedPaymentMethod
        fields = [
            'id', 'card_brand', 'card_last_four', 'card_exp_month',
            'card_exp_year', 'is_default', 'nickname', 'created_at'
        ]
        read_only_fields = [
            'card_brand', 'card_last_four', 'card_exp_month', 'card_exp_year'
        ]


class PaymentRefundSerializer(serializers.ModelSerializer):
    """
    Payment refund serializer
    """
    class Meta:
        model = PaymentRefund
        fields = [
            'refund_id', 'amount', 'reason', 'status', 'created_at', 'processed_at'
        ]


class PaymentSerializer(serializers.ModelSerializer):
    """
    Enhanced payment record serializer
    """
    booking_id = serializers.CharField(source='booking.booking_id', read_only=True)
    customer_name = serializers.CharField(source='customer.get_full_name', read_only=True)
    service_name = serializers.CharField(source='booking.service.name', read_only=True)
    refunds = PaymentRefundSerializer(many=True, read_only=True)
    
    # Computed fields
    is_successful = serializers.ReadOnlyField()
    can_be_refunded = serializers.ReadOnlyField()
    refundable_amount = serializers.SerializerMethodField()
    
    class Meta:
        model = Payment
        fields = [
            'payment_id', 'booking_id', 'customer_name', 'service_name',
            'amount', 'currency', 'payment_type', 'payment_method',
            'status', 'description', 'refund_amount', 'failure_reason',
            'is_successful', 'can_be_refunded', 'refundable_amount',
            'refunds', 'created_at', 'processed_at'
        ]
    
    def get_refundable_amount(self, obj):
        """Get refundable amount"""
        return str(obj.get_refund_amount())


class PaymentSummarySerializer(serializers.Serializer):
    """
    Payment summary serializer
    """
    total_payments = serializers.IntegerField()
    successful_payments = serializers.IntegerField()
    failed_payments = serializers.IntegerField()
    pending_payments = serializers.IntegerField()
    total_amount_paid = serializers.DecimalField(max_digits=10, decimal_places=2)
    total_refunded = serializers.DecimalField(max_digits=10, decimal_places=2)
    currency_breakdown = serializers.DictField()


class PaymentIntentCreateSerializer(serializers.Serializer):
    """
    Create payment intent request serializer
    """
    booking_id = serializers.UUIDField()
    payment_type = serializers.ChoiceField(
        choices=[
            ('full', 'Full Payment'),
            ('deposit', 'Deposit Payment'),
            ('remaining', 'Remaining Payment')
        ],
        default='deposit'
    )
    payment_method_id = serializers.CharField(required=False, allow_blank=True)
    save_payment_method = serializers.BooleanField(default=False)
    use_saved_method = serializers.BooleanField(default=False)
    
    def validate_booking_id(self, value):
        """Validate booking exists and belongs to user"""
        from bookings.models import Booking
        try:
            booking = Booking.objects.get(
                booking_id=value,
                customer=self.context['request'].user
            )
            return booking
        except Booking.DoesNotExist:
            raise serializers.ValidationError("Invalid booking or access denied")
    
    def validate(self, attrs):
        """Additional validation"""
        booking = attrs['booking_id']
        payment_type = attrs['payment_type']
        
        # Validate payment type based on booking status
        if payment_type == 'remaining':
            if booking.payment_status != 'deposit_paid':
                raise serializers.ValidationError(
                    "Remaining payment can only be made after deposit is paid"
                )
        elif payment_type == 'deposit':
            if booking.payment_status in ['deposit_paid', 'fully_paid']:
                raise serializers.ValidationError(
                    "Deposit has already been paid for this booking"
                )
        elif payment_type == 'full':
            if booking.payment_status == 'fully_paid':
                raise serializers.ValidationError(
                    "This booking has already been fully paid"
                )
        
        return attrs


class PaymentIntentResponseSerializer(serializers.Serializer):
    """
    Payment intent response serializer
    """
    client_secret = serializers.CharField()
    payment_id = serializers.UUIDField()
    amount = serializers.DecimalField(max_digits=10, decimal_places=2)
    currency = serializers.CharField()
    payment_type = serializers.CharField()
    requires_action = serializers.BooleanField()
    
    # Booking breakdown
    booking_breakdown = serializers.DictField()


class PaymentConfirmSerializer(serializers.Serializer):
    """
    Payment confirmation serializer
    """
    payment_intent_id = serializers.CharField()
    payment_method_id = serializers.CharField(required=False, allow_blank=True)
    
    def validate_payment_intent_id(self, value):
        """Validate payment intent exists"""
        try:
            payment = Payment.objects.get(
                stripe_payment_intent_id=value,
                customer=self.context['request'].user
            )
            return payment
        except Payment.DoesNotExist:
            raise serializers.ValidationError("Invalid payment intent or access denied")


class RefundRequestSerializer(serializers.Serializer):
    """
    Refund request serializer
    """
    payment_id = serializers.UUIDField()
    amount = serializers.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        required=False
    )
    reason = serializers.CharField(max_length=500)
    
    def validate_payment_id(self, value):
        """Validate payment exists and is refundable"""
        try:
            payment = Payment.objects.get(
                payment_id=value,
                customer=self.context['request'].user
            )
            if not payment.can_be_refunded:
                raise serializers.ValidationError("Payment is not refundable")
            return payment
        except Payment.DoesNotExist:
            raise serializers.ValidationError("Invalid payment or access denied")
    
    def validate_amount(self, value):
        """Validate refund amount"""
        if value is not None and value <= 0:
            raise serializers.ValidationError("Refund amount must be positive")
        return value
    
    def validate(self, attrs):
        """Validate refund amount against payment"""
        payment = attrs['payment_id']
        amount = attrs.get('amount')
        
        if amount and amount > payment.get_refund_amount():
            raise serializers.ValidationError(
                f"Refund amount cannot exceed {payment.get_refund_amount()}"
            )
        
        return attrs


class RefundResponseSerializer(serializers.Serializer):
    """
    Refund response serializer
    """
    success = serializers.BooleanField()
    refund_id = serializers.CharField()
    amount = serializers.DecimalField(max_digits=10, decimal_places=2)
    status = serializers.CharField()
    message = serializers.CharField()


class RemainingPaymentSerializer(serializers.Serializer):
    """
    Remaining payment request serializer
    """
    booking_id = serializers.UUIDField()
    payment_method_id = serializers.CharField(required=False, allow_blank=True)
    
    def validate_booking_id(self, value):
        """Validate booking exists and has deposit paid"""
        from bookings.models import Booking
        try:
            booking = Booking.objects.get(
                booking_id=value,
                customer=self.context['request'].user
            )
            
            if booking.payment_status != 'deposit_paid':
                raise serializers.ValidationError(
                    "Booking must have deposit paid to process remaining payment"
                )
            
            # Check if there's actually a remaining amount
            remaining_amount = booking.total_amount - booking.deposit_amount
            if remaining_amount <= 0:
                raise serializers.ValidationError(
                    "No remaining amount to pay for this booking"
                )
            
            return booking
        except Booking.DoesNotExist:
            raise serializers.ValidationError("Invalid booking or access denied")


class PaymentWebhookSerializer(serializers.Serializer):
    """
    Webhook event serializer for logging
    """
    event_id = serializers.CharField()
    event_type = serializers.CharField()
    processed = serializers.BooleanField()
    payment_id = serializers.UUIDField(required=False)
    error = serializers.CharField(required=False)


class PaymentMethodCreateSerializer(serializers.Serializer):
    """
    Create saved payment method serializer
    """
    stripe_payment_method_id = serializers.CharField()
    nickname = serializers.CharField(max_length=50, required=False, allow_blank=True)
    set_as_default = serializers.BooleanField(default=False)


class PaymentAnalyticsSerializer(serializers.Serializer):
    """
    Payment analytics serializer
    """
    period = serializers.CharField()
    total_revenue = serializers.DecimalField(max_digits=12, decimal_places=2)
    total_transactions = serializers.IntegerField()
    successful_transactions = serializers.IntegerField()
    failed_transactions = serializers.IntegerField()
    refunded_amount = serializers.DecimalField(max_digits=12, decimal_places=2)
    
    # Breakdown by payment type
    deposit_payments = serializers.IntegerField()
    full_payments = serializers.IntegerField()
    remaining_payments = serializers.IntegerField()
    
    # Currency breakdown
    currency_breakdown = serializers.DictField()
    
    # Payment method breakdown
    payment_method_breakdown = serializers.DictField()


class BookingPaymentStatusSerializer(serializers.Serializer):
    """
    Booking payment status serializer
    """
    booking_id = serializers.UUIDField()
    payment_status = serializers.CharField()
    total_amount = serializers.DecimalField(max_digits=10, decimal_places=2)
    deposit_amount = serializers.DecimalField(max_digits=10, decimal_places=2)
    amount_paid = serializers.DecimalField(max_digits=10, decimal_places=2)
    remaining_amount = serializers.DecimalField(max_digits=10, decimal_places=2)
    payment_history = PaymentSerializer(many=True)
    
    # Payment breakdown
    breakdown = serializers.DictField()
    
    # Next payment info
    next_payment_due = serializers.DecimalField(max_digits=10, decimal_places=2, required=False)
    next_payment_type = serializers.CharField(required=False)