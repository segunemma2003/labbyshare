from rest_framework import serializers
from django.contrib.auth.password_validation import validate_password
from firebase_admin import auth as firebase_auth
from .models import User
from regions.models import Region


class RegionSerializer(serializers.ModelSerializer):
    """
    Region serializer for user responses
    """
    class Meta:
        model = Region
        fields = ['id', 'code', 'name', 'currency', 'currency_symbol', 'timezone']
        ref_name = 'UserRegion'


class UserRegistrationSerializer(serializers.ModelSerializer):
    """
    User registration with email, password, and name (region optional)
    """
    password = serializers.CharField(write_only=True, validators=[validate_password])
    confirm_password = serializers.CharField(write_only=True)
    
    class Meta:
        model = User
        fields = [
            'first_name', 'last_name', 'email', 
            'password', 'confirm_password'
        ]
    
    def validate_email(self, value):
        """Validate email uniqueness"""
        if User.objects.filter(email=value.lower()).exists():
            raise serializers.ValidationError("User with this email already exists")
        return value.lower()
    
    def validate(self, attrs):
        """Validate password confirmation"""
        if attrs['password'] != attrs['confirm_password']:
            raise serializers.ValidationError("Passwords do not match")
        return attrs
    
    def create(self, validated_data):
        """Create new user"""
        validated_data.pop('confirm_password')
        
        # Create username from email
        email = validated_data['email']
        username = email.split('@')[0]
        
        # Ensure unique username
        base_username = username
        counter = 1
        while User.objects.filter(username=username).exists():
            username = f"{base_username}{counter}"
            counter += 1
        
        user = User.objects.create_user(
            username=username,
            **validated_data
        )
        return user


class UserLoginSerializer(serializers.Serializer):
    """
    User login serializer
    """
    email = serializers.EmailField()
    password = serializers.CharField()
    
    def validate_email(self, value):
        return value.lower()


class SocialAuthSerializer(serializers.Serializer):
    """
    Social authentication (Google/Apple) via Firebase (region optional)
    """
    firebase_token = serializers.CharField()
    provider = serializers.ChoiceField(choices=['google', 'apple'])
    
    def validate_firebase_token(self, value):
        """Validate Firebase token"""
        try:
            decoded_token = firebase_auth.verify_id_token(value)
            return decoded_token
        except Exception as e:
            raise serializers.ValidationError("Invalid Firebase token")


class RegionSelectionSerializer(serializers.Serializer):
    """
    Region selection/update serializer
    """
    region_code = serializers.CharField(max_length=10)
    
    def validate_region_code(self, value):
        """Validate region exists and is active"""
        try:
            region = Region.objects.get(code=value.upper(), is_active=True)
            return region
        except Region.DoesNotExist:
            raise serializers.ValidationError("Invalid or inactive region code")


class ProfileImageUpdateSerializer(serializers.ModelSerializer):
    """
    Update user profile image only
    """
    class Meta:
        model = User
        fields = ['profile_picture']
    
    def validate_profile_picture(self, value):
        """Validate image file"""
        if value:
            # Check file size (5MB limit)
            if value.size > 5 * 1024 * 1024:
                raise serializers.ValidationError("Image file too large. Maximum size is 5MB.")
            
            # Check file type
            allowed_types = ['image/jpeg', 'image/jpg', 'image/png', 'image/webp']
            if hasattr(value, 'content_type') and value.content_type not in allowed_types:
                raise serializers.ValidationError("Unsupported image format. Use JPEG, PNG, or WebP.")
        
        return value


class ProfileUpdateSerializer(serializers.ModelSerializer):
    """
    Update user profile information (excluding profile picture)
    """
    class Meta:
        model = User
        fields = [
            'first_name', 'last_name', 'phone_number', 
            'date_of_birth', 'gender'
        ]
    
    def update(self, instance, validated_data):
        """Update profile and check completion"""
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        
        # Check if profile is completed
        required_fields = ['phone_number', 'date_of_birth', 'gender']
        if all(getattr(instance, field) for field in required_fields):
            instance.profile_completed = True
        
        instance.save()
        return instance


class UserSerializer(serializers.ModelSerializer):
    """
    Complete user serializer for responses
    """
    current_region = RegionSerializer(read_only=True)
    full_name = serializers.SerializerMethodField()
    
    class Meta:
        model = User
        fields = [
            'id', 'uid', 'email', 'first_name', 'last_name', 'full_name',
            'phone_number', 'profile_picture', 'date_of_birth', 'gender',
            'user_type', 'current_region', 'profile_completed', 
            'is_verified', 'created_at'
        ]
    
    def get_full_name(self, obj):
        return obj.get_full_name()


class ForgotPasswordSerializer(serializers.Serializer):
    """
    Forgot password serializer
    """
    email = serializers.EmailField()
    
    def validate_email(self, value):
        return value.lower()


class ResetPasswordSerializer(serializers.Serializer):
    """
    Reset password with OTP
    """
    email = serializers.EmailField()
    otp = serializers.CharField(max_length=6, min_length=6)
    new_password = serializers.CharField(validators=[validate_password])
    confirm_password = serializers.CharField()
    
    def validate_email(self, value):
        return value.lower()
    
    def validate(self, attrs):
        if attrs['new_password'] != attrs['confirm_password']:
            raise serializers.ValidationError("Passwords do not match")
        return attrs


class ChangePasswordSerializer(serializers.Serializer):
    """
    Change password for authenticated user
    """
    current_password = serializers.CharField()
    new_password = serializers.CharField(validators=[validate_password])
    confirm_password = serializers.CharField()
    
    def validate(self, attrs):
        if attrs['new_password'] != attrs['confirm_password']:
            raise serializers.ValidationError("Passwords do not match")
        return attrs
    
    def validate_current_password(self, value):
        """Validate current password"""
        user = self.context['request'].user
        if not user.check_password(value):
            raise serializers.ValidationError("Current password is incorrect")
        return value
    
    
class VerifyEmailSerializer(serializers.Serializer):
    """
    Email verification serializer
    """
    email = serializers.EmailField()
    otp = serializers.CharField(max_length=6, min_length=6)
    
    def validate_email(self, value):
        return value.lower()
    
    def validate_otp(self, value):
        if not value.isdigit():
            raise serializers.ValidationError("OTP must contain only digits")
        return value


class ResendOTPSerializer(serializers.Serializer):
    """
    Resend OTP serializer
    """
    email = serializers.EmailField()
    purpose = serializers.ChoiceField(choices=['email_verification', 'password_reset'])
    
    def validate_email(self, value):
        return value.lower()


class VerifyResetOTPSerializer(serializers.Serializer):
    """
    Verify reset OTP serializer (without password reset)
    """
    email = serializers.EmailField()
    otp = serializers.CharField(max_length=6, min_length=6)
    
    def validate_email(self, value):
        return value.lower()
    
    def validate_otp(self, value):
        if not value.isdigit():
            raise serializers.ValidationError("OTP must contain only digits")
        return value