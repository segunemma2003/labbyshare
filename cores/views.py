from rest_framework import serializers
from django.contrib.auth import authenticate
from django.contrib.auth.password_validation import validate_password
from .models import *
import random
import string
from datetime import datetime, timedelta
from firebase_admin import auth as firebase_auth


class RegionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Region
        fields = ['id', 'code', 'name', 'currency', 'timezone', 'is_active']


class UserRegistrationSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, validators=[validate_password])
    confirm_password = serializers.CharField(write_only=True)
    current_region = serializers.PrimaryKeyRelatedField(queryset=Region.objects.filter(is_active=True))
    
    class Meta:
        model = User
        fields = [
            'first_name', 'last_name', 'email', 'password', 
            'confirm_password', 'current_region'
        ]
    
    def validate(self, attrs):
        if attrs['password'] != attrs['confirm_password']:
            raise serializers.ValidationError("Passwords do not match")
        return attrs
    
    def create(self, validated_data):
        validated_data.pop('confirm_password')
        region = validated_data.pop('current_region')
        
        user = User.objects.create_user(
            username=validated_data['email'],
            **validated_data
        )
        user.current_region = region
        user.save()
        return user


class SocialAuthSerializer(serializers.Serializer):
    firebase_token = serializers.CharField()
    provider = serializers.ChoiceField(choices=['google', 'apple'])
    current_region = serializers.PrimaryKeyRelatedField(queryset=Region.objects.filter(is_active=True))
    
    def validate_firebase_token(self, value):
        try:
            decoded_token = firebase_auth.verify_id_token(value)
            return decoded_token
        except Exception as e:
            raise serializers.ValidationError("Invalid Firebase token")


class ProfileUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = [
            'first_name', 'last_name', 'phone_number', 'profile_picture',
            'date_of_birth', 'gender'
        ]
    
    def update(self, instance, validated_data):
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        
        # Check if profile is completed
        required_fields = ['phone_number', 'date_of_birth', 'gender']
        if all(getattr(instance, field) for field in required_fields):
            instance.profile_completed = True
        
        instance.save()
        return instance


class UserSerializer(serializers.ModelSerializer):
    current_region = RegionSerializer(read_only=True)
    
    class Meta:
        model = User
        fields = [
            'id', 'uid', 'first_name', 'last_name', 'email', 'phone_number',
            'profile_picture', 'date_of_birth', 'gender', 'current_region',
            'profile_completed', 'created_at'
        ]


class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ['id', 'name', 'description', 'icon', 'sort_order']


class ServiceSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source='category.name', read_only=True)
    
    class Meta:
        model = Service
        fields = [
            'id', 'name', 'description', 'base_price', 'duration_minutes',
            'category_name', 'sort_order'
        ]


class AddOnSerializer(serializers.ModelSerializer):
    class Meta:
        model = AddOn
        fields = ['id', 'name', 'description', 'price']


class ProfessionalSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)
    services = ServiceSerializer(many=True, read_only=True)
    
    class Meta:
        model = Professional
        fields = [
            'id', 'user', 'bio', 'experience_years', 'rating',
            'total_reviews', 'is_verified', 'services'
        ]


class BookingCreateSerializer(serializers.ModelSerializer):
    selected_addons = serializers.ListField(
        child=serializers.DictField(), 
        write_only=True, 
        required=False
    )
    
    class Meta:
        model = Booking
        fields = [
            'professional', 'service', 'scheduled_date', 'scheduled_time',
            'booking_for_self', 'recipient_name', 'recipient_phone',
            'notes', 'selected_addons'
        ]
    
    def create(self, validated_data):
        selected_addons = validated_data.pop('selected_addons', [])
        user = self.context['request'].user
        
        booking = Booking.objects.create(
            customer=user,
            region=user.current_region,
            duration_minutes=validated_data['service'].duration_minutes,
            base_amount=validated_data['service'].base_price,
            **validated_data
        )
        
        # Handle add-ons
        addon_total = Decimal('0.00')
        for addon_data in selected_addons:
            addon = AddOn.objects.get(id=addon_data['addon_id'])
            quantity = addon_data.get('quantity', 1)
            
            BookingAddOn.objects.create(
                booking=booking,
                addon=addon,
                quantity=quantity,
                price_at_booking=addon.price
            )
            addon_total += addon.price * quantity
        
        booking.addon_amount = addon_total
        booking.total_amount = booking.base_amount + addon_total
        booking.save()
        
        return booking


class BookingSerializer(serializers.ModelSerializer):
    customer = UserSerializer(read_only=True)
    professional = ProfessionalSerializer(read_only=True)
    service = ServiceSerializer(read_only=True)
    selected_addons = serializers.SerializerMethodField()
    
    class Meta:
        model = Booking
        fields = [
            'booking_id', 'customer', 'professional', 'service',
            'scheduled_date', 'scheduled_time', 'duration_minutes',
            'booking_for_self', 'recipient_name', 'total_amount',
            'status', 'payment_status', 'selected_addons', 'notes',
            'created_at'
        ]
    
    def get_selected_addons(self, obj):
        addons = obj.selected_addons.all()
        return [{
            'addon': AddOnSerializer(addon.addon).data,
            'quantity': addon.quantity,
            'price': addon.price_at_booking
        } for addon in addons]
