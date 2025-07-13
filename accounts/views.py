from rest_framework import status, generics
from rest_framework.decorators import api_view, permission_classes, throttle_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.authtoken.models import Token
from rest_framework.throttling import UserRateThrottle, AnonRateThrottle
from django.contrib.auth import authenticate
from django.core.cache import cache
from django.conf import settings
from django.utils import timezone
from datetime import timedelta
import random
import string

from .models import User, OTPVerification
from .serializers import (
    UserRegistrationSerializer, 
    UserLoginSerializer, 
    SocialAuthSerializer,
    ProfileUpdateSerializer,
    UserSerializer,
    ForgotPasswordSerializer,
    ResetPasswordSerializer
)
from regions.models import Region
from .tasks import send_otp_email


class RegisterThrottle(AnonRateThrottle):
    scope = 'register'


class LoginThrottle(AnonRateThrottle):
    scope = 'login'


@api_view(['POST'])
@permission_classes([AllowAny])
@throttle_classes([RegisterThrottle])
def register(request):
    """
    Register new user with email, password, and region selection
    """
    serializer = UserRegistrationSerializer(data=request.data)
    
    if serializer.is_valid():
        # Check if user already exists
        email = serializer.validated_data['email'].lower()
        if User.objects.filter(email=email).exists():
            return Response(
                {'error': 'User with this email already exists'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        user = serializer.save()
        
        # Create authentication token
        token, created = Token.objects.get_or_create(user=user)
        
        # Generate OTP for email verification
        otp = ''.join(random.choices(string.digits, k=6))
        expires_at = timezone.now() + timedelta(minutes=10)
        
        OTPVerification.objects.create(
            email=user.email,
            otp=otp,
            purpose='email_verification',
            expires_at=expires_at
        )
        
        # Send verification email asynchronously
        send_otp_email.delay(user.email, otp, 'verification')
        
        # Cache user profile
        cache_key = settings.CACHE_KEYS['USER_PROFILE'].format(user.id)
        cache.set(cache_key, UserSerializer(user).data, settings.CACHE_TIMEOUTS['USER_PROFILE'])
        
        return Response({
            'message': 'Registration successful. Please verify your email.',
            'token': token.key,
            'user': UserSerializer(user).data
        }, status=status.HTTP_201_CREATED)
    
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@permission_classes([AllowAny])
@throttle_classes([LoginThrottle])
def login(request):
    """
    Login user with email and password
    """
    serializer = UserLoginSerializer(data=request.data)
    
    if serializer.is_valid():
        email = serializer.validated_data['email'].lower()
        password = serializer.validated_data['password']
        
        user = authenticate(username=email, password=password)
        
        if user and user.is_active:
            # Update last login region if provided
            region_code = request.data.get('region_code')
            if region_code:
                try:
                    region = Region.objects.get(code=region_code.upper(), is_active=True)
                    user.last_login_region = region
                    if not user.current_region:
                        user.current_region = region
                    user.save(update_fields=['last_login_region', 'current_region'])
                except Region.DoesNotExist:
                    pass
            
            # Get or create token
            token, created = Token.objects.get_or_create(user=user)
            
            # Cache user profile
            cache_key = settings.CACHE_KEYS['USER_PROFILE'].format(user.id)
            cache.set(cache_key, UserSerializer(user).data, settings.CACHE_TIMEOUTS['USER_PROFILE'])
            
            return Response({
                'token': token.key,
                'user': UserSerializer(user).data
            }, status=status.HTTP_200_OK)
        
        return Response(
            {'error': 'Invalid credentials'}, 
            status=status.HTTP_401_UNAUTHORIZED
        )
    
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@permission_classes([AllowAny])
@throttle_classes([RegisterThrottle])
def social_auth(request):
    """
    Social authentication with Google/Apple via Firebase
    """
    serializer = SocialAuthSerializer(data=request.data)
    
    if serializer.is_valid():
        firebase_token = serializer.validated_data['firebase_token']
        provider = serializer.validated_data['provider']
        current_region = serializer.validated_data['current_region']
        
        try:
            # The token is already verified in the serializer
            decoded_token = firebase_token
            
            email = decoded_token.get('email', '').lower()
            firebase_uid = decoded_token.get('uid')
            name = decoded_token.get('name', '')
            
            if not email:
                return Response(
                    {'error': 'Email not provided by social provider'}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Split name into first and last name
            name_parts = name.split(' ', 1)
            first_name = name_parts[0] if name_parts else ''
            last_name = name_parts[1] if len(name_parts) > 1 else ''
            
            # Check if user exists
            user = None
            try:
                if provider == 'google':
                    user = User.objects.get(google_id=firebase_uid)
                elif provider == 'apple':
                    user = User.objects.get(apple_id=firebase_uid)
                else:
                    user = User.objects.get(email=email)
            except User.DoesNotExist:
                # Create new user
                username = email.split('@')[0] + '_' + ''.join(random.choices(string.digits, k=4))
                user = User.objects.create_user(
                    username=username,
                    email=email,
                    first_name=first_name,
                    last_name=last_name,
                    current_region=current_region,
                    firebase_uid=firebase_uid,
                    is_verified=True  # Social auth users are pre-verified
                )
                
                # Set provider-specific ID
                if provider == 'google':
                    user.google_id = firebase_uid
                elif provider == 'apple':
                    user.apple_id = firebase_uid
                
                user.save()
            
            # Update user's firebase UID if not set
            if not user.firebase_uid:
                user.firebase_uid = firebase_uid
                user.save(update_fields=['firebase_uid'])
            
            # Get or create token
            token, created = Token.objects.get_or_create(user=user)
            
            # Cache user profile
            cache_key = settings.CACHE_KEYS['USER_PROFILE'].format(user.id)
            cache.set(cache_key, UserSerializer(user).data, settings.CACHE_TIMEOUTS['USER_PROFILE'])
            
            return Response({
                'token': token.key,
                'user': UserSerializer(user).data,
                'is_new_user': created
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            return Response(
                {'error': 'Invalid Firebase token'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
    
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def logout(request):
    """
    Logout user by deleting token
    """
    try:
        # Delete token
        request.user.auth_token.delete()
        
        # Clear user cache
        cache_key = settings.CACHE_KEYS['USER_PROFILE'].format(request.user.id)
        cache.delete(cache_key)
        
        return Response(
            {'message': 'Successfully logged out'}, 
            status=status.HTTP_200_OK
        )
    except:
        return Response(
            {'error': 'Error logging out'}, 
            status=status.HTTP_400_BAD_REQUEST
        )


@api_view(['POST'])
@permission_classes([AllowAny])
def forgot_password(request):
    """
    Send OTP for password reset
    """
    serializer = ForgotPasswordSerializer(data=request.data)
    
    if serializer.is_valid():
        email = serializer.validated_data['email'].lower()
        
        try:
            user = User.objects.get(email=email)
            
            # Generate OTP
            otp = ''.join(random.choices(string.digits, k=6))
            expires_at = timezone.now() + timedelta(minutes=10)
            
            # Delete any existing OTPs for this email and purpose
            OTPVerification.objects.filter(
                email=email, 
                purpose='password_reset'
            ).delete()
            
            # Create new OTP
            OTPVerification.objects.create(
                email=email,
                otp=otp,
                purpose='password_reset',
                expires_at=expires_at
            )
            
            # Send email asynchronously
            send_otp_email.delay(email, otp, 'password_reset')
            
            return Response(
                {'message': 'OTP sent to your email'}, 
                status=status.HTTP_200_OK
            )
        
        except User.DoesNotExist:
            # Don't reveal if email exists or not for security
            return Response(
                {'message': 'If the email exists, OTP has been sent'}, 
                status=status.HTTP_200_OK
            )
    
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@permission_classes([AllowAny])
def reset_password(request):
    """
    Reset password using OTP
    """
    serializer = ResetPasswordSerializer(data=request.data)
    
    if serializer.is_valid():
        email = serializer.validated_data['email'].lower()
        otp = serializer.validated_data['otp']
        new_password = serializer.validated_data['new_password']
        
        try:
            otp_verification = OTPVerification.objects.get(
                email=email,
                otp=otp,
                purpose='password_reset',
                used=False
            )
            
            if otp_verification.is_expired():
                return Response(
                    {'error': 'OTP has expired'}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Get user and update password
            user = User.objects.get(email=email)
            user.set_password(new_password)
            user.save()
            
            # Mark OTP as used
            otp_verification.used = True
            otp_verification.save()
            
            # Invalidate all existing tokens for this user
            Token.objects.filter(user=user).delete()
            
            # Clear user cache
            cache_key = settings.CACHE_KEYS['USER_PROFILE'].format(user.id)
            cache.delete(cache_key)
            
            return Response(
                {'message': 'Password reset successful'}, 
                status=status.HTTP_200_OK
            )
        
        except OTPVerification.DoesNotExist:
            return Response(
                {'error': 'Invalid OTP'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        except User.DoesNotExist:
            return Response(
                {'error': 'User not found'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
    
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def switch_region(request):
    """
    Switch user's current region
    """
    region_code = request.data.get('region_code', '').upper()
    
    if not region_code:
        return Response(
            {'error': 'Region code is required'}, 
            status=status.HTTP_400_BAD_REQUEST
        )
    
    try:
        region = Region.objects.get(code=region_code, is_active=True)
        
        # Update user's current region
        request.user.current_region = region
        request.user.save(update_fields=['current_region'])
        
        # Clear user cache
        cache_key = settings.CACHE_KEYS['USER_PROFILE'].format(request.user.id)
        cache.delete(cache_key)
        
        return Response({
            'message': f'Switched to {region.name}',
            'region': {
                'code': region.code,
                'name': region.name,
                'currency': region.currency,
                'timezone': region.timezone
            }
        }, status=status.HTTP_200_OK)
    
    except Region.DoesNotExist:
        return Response(
            {'error': 'Invalid region code'}, 
            status=status.HTTP_400_BAD_REQUEST
        )


class ProfileUpdateView(generics.UpdateAPIView):
    """
    Update user profile
    """
    serializer_class = ProfileUpdateSerializer
    permission_classes = [IsAuthenticated]
    
    def get_object(self):
        return self.request.user
    
    def perform_update(self, serializer):
        serializer.save()
        
        # Clear user cache
        cache_key = settings.CACHE_KEYS['USER_PROFILE'].format(self.request.user.id)
        cache.delete(cache_key)