from rest_framework import serializers
from decimal import Decimal
from .models import Payment, SavedPaymentMethod


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


class PaymentSerializer(serializers.ModelSerializer):
    """
    Payment record serializer
    """
    booking_id = serializers.CharField(source='booking.booking_id', read_only=True)
    customer_name = serializers.CharField(source='customer.get_full_name', read_only=True)
    
    class Meta:
        model = Payment
        fields = [
            'payment_id', 'booking_id', 'customer_name', 'amount', 'currency',
            'payment_type', 'status', 'description', 'refund_amount',
            'created_at', 'processed_at'
        ]


class PaymentIntentSerializer(serializers.Serializer):
    """
    Create payment intent request
    """
    booking_id = serializers.UUIDField()
    payment_type = serializers.ChoiceField(choices=Payment.PAYMENT_TYPES)
    payment_method_id = serializers.CharField(required=False)
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
            raise serializers.ValidationError("Invalid booking")


class RefundRequestSerializer(serializers.Serializer):
    """
    Request refund
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
            if not payment.is_refundable:
                raise serializers.ValidationError("Payment is not refundable")
            return payment
        except Payment.DoesNotExist:
            raise serializers.ValidationError("Invalid payment")
    
    def validate_amount(self, value):
        """Validate refund amount"""
        if value and value <= 0:
            raise serializers.ValidationError("Refund amount must be positive")
        return value
    
    def validate(self, attrs):
        """Validate refund amount against payment"""
        payment = attrs['payment_id']
        amount = attrs.get('amount')
        
        if amount and amount > payment.get_refundable_amount():
            raise serializers.ValidationError(
                f"Refund amount cannot exceed {payment.get_refundable_amount()}"
            )
        
        return attrs