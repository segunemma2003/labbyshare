from rest_framework import generics, status, permissions, serializers
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from django.db.models import Q, Count, Avg, Sum, F
from django.utils import timezone
from datetime import datetime, timedelta
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi
from rest_framework.pagination import PageNumberPagination
import logging

logger = logging.getLogger(__name__)

from .models import AdminActivity, SystemAlert, SupportTicket
from .serializers import *
from accounts.models import User
from professionals.models import Professional, ProfessionalService, ProfessionalAvailability
from bookings.models import Booking, Review
from payments.models import Payment
from services.models import Category, Service, AddOn, RegionalPricing
from regions.models import Region, RegionalSettings
from notifications.models import Notification
from utils.permissions import IsAdminUser



# ===================== DASHBOARD & ANALYTICS =====================

class LargeResultsSetPagination(PageNumberPagination):
    page_size = 500
    page_size_query_param = 'page_size'
    max_page_size = 500

def get_requested_region(request):
    region_id = request.query_params.get('region')
    if not region_id:
        region_code = request.headers.get('X-Region')
        if region_code:
            from regions.models import Region
            try:
                return Region.objects.get(code=region_code)
            except Region.DoesNotExist:
                return None
        return None
    from regions.models import Region
    try:
        return Region.objects.get(id=region_id)
    except Region.DoesNotExist:
        return None

class AdminDashboardView(generics.GenericAPIView):
    permission_classes = [IsAdminUser]
    
    @swagger_auto_schema(
        operation_description="Get comprehensive admin dashboard statistics and paginated services/addons (filtered by region if provided)",
        responses={200: 'Dashboard statistics and paginated data'}
    )
    def get(self, request):
        region = get_requested_region(request)
        today = timezone.now().date()
        week_start = today - timedelta(days=today.weekday())
        month_start = today.replace(day=1)
        
        # Calculate previous periods for growth
        prev_week_start = week_start - timedelta(days=7)
        prev_month_start = (month_start - timedelta(days=1)).replace(day=1)
        
        # Base querysets
        user_qs = User.objects
        booking_qs = Booking.objects
        payment_qs = Payment.objects
        professional_qs = Professional.objects
        service_qs = Service.objects.filter(is_active=True)
        addon_qs = AddOn.objects.filter(is_active=True)
        
        # Apply region filter if provided
        if region:
            user_qs = user_qs.filter(current_region=region)
            booking_qs = booking_qs.filter(region=region)
            payment_qs = payment_qs.filter(booking__region=region)
            professional_qs = professional_qs.filter(regions=region)
            service_qs = service_qs.filter(category__region=region)
            addon_qs = addon_qs.filter(region=region)
        
        # User Statistics
        total_users = user_qs.filter(user_type='customer').count()
        total_customers = user_qs.filter(user_type='customer').count()
        total_professionals = professional_qs.count()
        
        new_users_today = user_qs.filter(date_joined__date=today).count()
        new_users_this_week = user_qs.filter(date_joined__date__gte=week_start).count()
        new_users_this_month = user_qs.filter(date_joined__date__gte=month_start).count()
        
        # Booking Statistics
        total_bookings = booking_qs.count()
        bookings_today = booking_qs.filter(created_at__date=today).count()
        bookings_this_week = booking_qs.filter(created_at__date__gte=week_start).count()
        bookings_this_month = booking_qs.filter(created_at__date__gte=month_start).count()
        
        pending_bookings = booking_qs.filter(status='pending').count()
        confirmed_bookings = booking_qs.filter(status='confirmed').count()
        completed_bookings = booking_qs.filter(status='completed').count()
        
        # Revenue Statistics
        successful_payments = payment_qs.filter(status='succeeded')
        total_revenue = successful_payments.aggregate(total=Sum('amount'))['total'] or 0
        revenue_today = successful_payments.filter(created_at__date=today).aggregate(total=Sum('amount'))['total'] or 0
        revenue_this_week = successful_payments.filter(created_at__date__gte=week_start).aggregate(total=Sum('amount'))['total'] or 0
        revenue_this_month = successful_payments.filter(created_at__date__gte=month_start).aggregate(total=Sum('amount'))['total'] or 0
        
        # Professional Statistics
        pending_verifications = professional_qs.filter(is_verified=False, is_active=True).count()
        verified_professionals = professional_qs.filter(is_verified=True).count()
        active_professionals = professional_qs.filter(is_active=True).count()
        
        # System Statistics
        total_services = service_qs.count()
        total_addons = addon_qs.count()
        total_categories = Category.objects.filter(is_active=True)
        total_regions = Region.objects.filter(is_active=True).count()
        open_support_tickets = SupportTicket.objects.filter(status__in=['open', 'in_progress']).count()
        unresolved_alerts = SystemAlert.objects.filter(is_resolved=False).count()
        
        if region:
            total_categories = total_categories.filter(region=region)
        total_categories = total_categories.count()
        
        # Growth Calculations
        prev_week_users = user_qs.filter(
            date_joined__date__gte=prev_week_start,
            date_joined__date__lt=week_start
        ).count()
        prev_week_bookings = booking_qs.filter(
            created_at__date__gte=prev_week_start,
            created_at__date__lt=week_start
        ).count()
        prev_week_revenue = successful_payments.filter(
            created_at__date__gte=prev_week_start,
            created_at__date__lt=week_start
        ).aggregate(total=Sum('amount'))['total'] or 0
        
        # Calculate growth rates
        user_growth_rate = ((new_users_this_week - prev_week_users) / max(prev_week_users, 1)) * 100
        booking_growth_rate = ((bookings_this_week - prev_week_bookings) / max(prev_week_bookings, 1)) * 100
        revenue_growth_rate = ((float(revenue_this_week) - float(prev_week_revenue)) / max(float(prev_week_revenue), 1)) * 100
        
        # Paginated data
        service_qs = service_qs.order_by('-created_at')
        addon_qs = addon_qs.order_by('-created_at')
        service_paginator = LargeResultsSetPagination()
        addon_paginator = LargeResultsSetPagination()
        paginated_services = service_paginator.paginate_queryset(service_qs, request)
        paginated_addons = addon_paginator.paginate_queryset(addon_qs, request)
        services_data = AdminServiceSerializer(paginated_services, many=True).data
        addons_data = AdminAddOnSerializer(paginated_addons, many=True).data
        
        return Response({
            # Statistics
            'total_users': total_users,
            'total_customers': total_customers,
            'total_professionals': total_professionals,
            'new_users_today': new_users_today,
            'new_users_this_week': new_users_this_week,
            'new_users_this_month': new_users_this_month,
            'total_bookings': total_bookings,
            'bookings_today': bookings_today,
            'bookings_this_week': bookings_this_week,
            'bookings_this_month': bookings_this_month,
            'pending_bookings': pending_bookings,
            'confirmed_bookings': confirmed_bookings,
            'completed_bookings': completed_bookings,
            'total_revenue': total_revenue,
            'revenue_today': revenue_today,
            'revenue_this_week': revenue_this_week,
            'revenue_this_month': revenue_this_month,
            'pending_verifications': pending_verifications,
            'verified_professionals': verified_professionals,
            'active_professionals': active_professionals,
            'total_services': total_services,
            'total_addons': total_addons,
            'total_categories': total_categories,
            'total_regions': total_regions,
            'open_support_tickets': open_support_tickets,
            'unresolved_alerts': unresolved_alerts,
            'user_growth_rate': round(user_growth_rate, 2),
            'booking_growth_rate': round(booking_growth_rate, 2),
            'revenue_growth_rate': round(revenue_growth_rate, 2),
            # Paginated data
            'services': services_data,
            'addons': addons_data,
            'services_count': service_qs.count(),
            'addons_count': addon_qs.count(),
        })


# ===================== USER MANAGEMENT =====================

class AdminUserListView(generics.ListCreateAPIView):
    """
    List and create users (admin)
    """
    permission_classes = [IsAdminUser]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['user_type', 'is_active', 'is_verified', 'current_region']
    search_fields = ['first_name', 'last_name', 'email', 'username']
    ordering_fields = ['date_joined', 'last_login', 'first_name']
    ordering = ['-date_joined']
    
    def get_queryset(self):
        region = get_requested_region(self.request)
        qs = User.objects.select_related('current_region').prefetch_related('bookings', 'payments')
        if region:
            qs = qs.filter(current_region=region)
        return qs
    
    def get_serializer_class(self):
        if self.request.method == 'POST':
            return AdminUserCreateSerializer
        return AdminUserDetailSerializer
    
    @swagger_auto_schema(
        operation_description="Create new user (admin)",
        request_body=AdminUserCreateSerializer,
        responses={201: AdminUserDetailSerializer()}
    )
    def post(self, request, *args, **kwargs):
        response = super().create(request, *args, **kwargs)
        if response.status_code == 201:
            user = User.objects.get(email=response.data['email'])
            detail_data = AdminUserDetailSerializer(user).data
            AdminActivity.objects.create(
                admin_user=request.user,
                activity_type='user_action',
                description=f"Created user: {user.email}",
                target_model='User',
                target_id=str(user.id)
            )
            return Response(detail_data, status=201)
        return response


class AdminUserDetailView(generics.RetrieveUpdateDestroyAPIView):
    """
    Get, update, or delete user (admin)
    """
    permission_classes = [IsAdminUser]
    queryset = User.objects.all()
    
    def get_serializer_class(self):
        if self.request.method in ['PUT', 'PATCH']:
            return AdminUserUpdateSerializer
        return AdminUserDetailSerializer
    
    @swagger_auto_schema(
        operation_description="Update user (admin)",
        request_body=AdminUserUpdateSerializer,
        responses={200: AdminUserDetailSerializer()}
    )
    def put(self, request, *args, **kwargs):
        response = super().update(request, *args, **kwargs)
        
        if response.status_code == 200:
            AdminActivity.objects.create(
                admin_user=request.user,
                activity_type='user_action',
                description=f"Updated user: {response.data['email']}",
                target_model='User',
                target_id=str(response.data['id'])
            )
        
        return response
    
    def perform_destroy(self, instance):
        try:
            # Log the deletion attempt
            AdminActivity.objects.create(
                admin_user=self.request.user,
                activity_type='user_action',
                description=f"Attempting to delete user: {instance.email}",
                target_model='User',
                target_id=str(instance.id)
            )
            
            # Check if user has related data that might prevent deletion
            related_bookings = instance.bookings.count()
            related_payments = instance.payments.count()
            related_reviews = instance.reviews_given.count()
            
            if related_bookings > 0 or related_payments > 0 or related_reviews > 0:
                # Log the related data
                AdminActivity.objects.create(
                    admin_user=self.request.user,
                    activity_type='user_action',
                    description=f"Cannot delete user {instance.email} - has {related_bookings} bookings, {related_payments} payments, {related_reviews} reviews",
                    target_model='User',
                    target_id=str(instance.id)
                )
                raise Exception(f"Cannot delete user with related data: {related_bookings} bookings, {related_payments} payments, {related_reviews} reviews")
            
            # Perform the actual deletion
            instance.delete()
            
            # Log successful deletion
            AdminActivity.objects.create(
                admin_user=self.request.user,
                activity_type='user_action',
                description=f"Successfully deleted user: {instance.email}",
                target_model='User',
                target_id=str(instance.id)
            )
            
        except Exception as e:
            # Log the error
            AdminActivity.objects.create(
                admin_user=self.request.user,
                activity_type='user_action',
                description=f"Failed to delete user {instance.email}: {str(e)}",
                target_model='User',
                target_id=str(instance.id)
            )
            raise e


# ===================== PROFESSIONAL MANAGEMENT =====================

class AdminProfessionalListView(generics.ListCreateAPIView):
    """
    List and create professionals (admin)
    """
    permission_classes = [IsAdminUser]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['is_verified', 'is_active', 'regions']
    search_fields = ['user__first_name', 'user__last_name', 'user__email', 'bio']
    ordering_fields = ['created_at', 'rating', 'total_reviews']
    ordering = ['-created_at']
    
    def get_queryset(self):
        region = get_requested_region(self.request)
        qs = Professional.objects.select_related('user').prefetch_related('regions', 'services')
        if region:
            qs = qs.filter(regions=region)
        return qs
    
    def get_serializer_class(self):
        if self.request.method == 'POST':
            return AdminProfessionalCreateSerializer
        return AdminProfessionalDetailSerializer
    
    @swagger_auto_schema(
        operation_description="Create new professional (admin)",
        request_body=AdminProfessionalCreateSerializer,
        responses={201: AdminProfessionalDetailSerializer()}
    )
    def post(self, request, *args, **kwargs):
        response = super().create(request, *args, **kwargs)
        if response.status_code == 201:
            professional = Professional.objects.get(id=response.data['id'])
            detail_data = AdminProfessionalDetailSerializer(professional).data
            AdminActivity.objects.create(
                admin_user=request.user,
                activity_type='professional_verification',
                description=f"Created professional: {request.data['email']}",
                target_model='Professional',
                target_id=str(professional.id)
            )
            return Response(detail_data, status=201)
        return response


class AdminProfessionalDetailView(generics.RetrieveUpdateDestroyAPIView):
    """
    Get, update, or delete professional (admin)
    """
    permission_classes = [IsAdminUser]
    queryset = Professional.objects.select_related('user').prefetch_related('regions', 'services')
    
    def get_serializer_class(self):
        if self.request.method in ['PUT', 'PATCH']:
            return AdminProfessionalUpdateSerializer
        return AdminProfessionalDetailSerializer
    
    def update(self, request, *args, **kwargs):
        try:
            return super().update(request, *args, **kwargs)
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Error updating professional {kwargs.get('pk')}: {str(e)}")
            return Response(
                {'error': 'Failed to update professional. Please check the logs for details.'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


# ===================== CATEGORY MANAGEMENT =====================

class AdminCategoryListView(generics.ListCreateAPIView):
    """
    List and create categories (admin)
    """
    serializer_class = AdminCategorySerializer
    permission_classes = [IsAdminUser]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['region', 'is_active', 'is_featured']
    search_fields = ['name', 'description']
    ordering_fields = ['sort_order', 'name', 'created_at', 'is_featured']
    ordering = ['sort_order', 'name']
    
    def get_queryset(self):
        return Category.objects.select_related('region').prefetch_related('services')
    
    @swagger_auto_schema(
        operation_description="Create new category (admin)",
        request_body=AdminCategorySerializer,
        responses={201: AdminCategorySerializer()}
    )
    def post(self, request, *args, **kwargs):
        response = super().create(request, *args, **kwargs)
        if response.status_code == 201:
            category = Category.objects.get(id=response.data['id'])
            detail_data = AdminCategorySerializer(category).data
            AdminActivity.objects.create(
                admin_user=request.user,
                activity_type='content_moderation',
                description=f"Created category: {response.data['name']}",
                target_model='Category',
                target_id=str(category.id)
            )
            return Response(detail_data, status=201)
        return response


class AdminCategoryDetailView(generics.RetrieveUpdateDestroyAPIView):
    """
    Get, update, or delete category (admin)
    """
    serializer_class = AdminCategorySerializer
    permission_classes = [IsAdminUser]
    queryset = Category.objects.all()


# ===================== SERVICE MANAGEMENT =====================

class AdminServiceListView(generics.ListCreateAPIView):
    """
    List and create services (admin)
    """
    serializer_class = AdminServiceSerializer
    permission_classes = [IsAdminUser]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['category', 'category__region', 'is_active', 'is_featured']
    search_fields = ['name', 'description']
    ordering_fields = ['sort_order', 'name', 'base_price', 'created_at']
    ordering = ['sort_order', 'name']
    
    def get_queryset(self):
        return Service.objects.select_related('category__region').prefetch_related('professionals')

    @swagger_auto_schema(
        operation_description="Create new service (admin)",
        request_body=AdminServiceSerializer,
        responses={201: AdminServiceSerializer()}
    )
    def post(self, request, *args, **kwargs):
        response = super().create(request, *args, **kwargs)
        if response.status_code == 201:
            service = Service.objects.get(id=response.data['id'])
            detail_data = AdminServiceSerializer(service).data
            # Optionally log activity here
            return Response(detail_data, status=201)
        return response


class AdminServiceDetailView(generics.RetrieveUpdateDestroyAPIView):
    """
    Get, update, or delete service (admin)
    """
    serializer_class = AdminServiceSerializer
    permission_classes = [IsAdminUser]
    queryset = Service.objects.all()


# ===================== REGIONAL PRICING MANAGEMENT =====================

class AdminRegionalPricingListView(generics.ListCreateAPIView):
    """
    Manage regional pricing (admin)
    """
    serializer_class = AdminRegionalPricingSerializer
    permission_classes = [IsAdminUser]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['service', 'region', 'is_active']
    search_fields = ['service__name', 'region__name']
    ordering = ['service__name', 'region__name']
    
    def get_queryset(self):
        return RegionalPricing.objects.select_related('service', 'region')


class AdminRegionalPricingDetailView(generics.RetrieveUpdateDestroyAPIView):
    """
    Update or delete regional pricing (admin)
    """
    serializer_class = AdminRegionalPricingSerializer
    permission_classes = [IsAdminUser]
    queryset = RegionalPricing.objects.all()


# ===================== ADDON MANAGEMENT =====================

class AdminAddOnListView(generics.ListCreateAPIView):
    """
    List and create add-ons (admin)
    """
    serializer_class = AdminAddOnSerializer
    permission_classes = [IsAdminUser]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['categories', 'region', 'is_active']
    search_fields = ['name', 'description']
    ordering = ['name']
    
    def get_queryset(self):
        region = get_requested_region(self.request)
        qs = AddOn.objects.prefetch_related('categories', 'region')
        if region:
            qs = qs.filter(region=region)
        return qs


class AdminAddOnDetailView(generics.RetrieveUpdateDestroyAPIView):
    """
    Get, update, or delete add-on (admin)
    """
    serializer_class = AdminAddOnSerializer
    permission_classes = [IsAdminUser]
    queryset = AddOn.objects.prefetch_related('categories', 'region')


# ===================== BOOKING MANAGEMENT =====================

class AdminBookingListView(generics.ListAPIView):
    """
    List bookings (admin)
    """
    serializer_class = AdminBookingSerializer
    permission_classes = [IsAdminUser]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['status', 'payment_status', 'region', 'scheduled_date']
    search_fields = ['customer__email', 'professional__user__email', 'service__name']
    ordering_fields = ['created_at', 'scheduled_date', 'total_amount']
    ordering = ['-created_at']
    
    def get_queryset(self):
        region = get_requested_region(self.request)
        qs = Booking.objects.select_related(
            'customer', 'professional__user', 'service', 'region'
        )
        if region:
            qs = qs.filter(region=region)
        return qs


class AdminBookingDetailView(generics.RetrieveUpdateAPIView):
    """
    Get and update booking (admin)
    """
    permission_classes = [IsAdminUser]
    lookup_field = 'booking_id'
    
    def get_serializer_class(self):
        if self.request.method in ['PUT', 'PATCH']:
            return AdminBookingUpdateSerializer
        return AdminBookingSerializer
    
    def get_queryset(self):
        try:
            return Booking.objects.select_related(
                'customer', 'professional__user', 'service', 'region'
            ).prefetch_related('pictures')
        except Exception:
            # Return queryset without pictures prefetch if table doesn't exist yet
            return Booking.objects.select_related(
                'customer', 'professional__user', 'service', 'region'
            )


@api_view(['POST'])
@permission_classes([IsAdminUser])
@swagger_auto_schema(
    operation_description="Update booking status (admin)",
    request_body=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        properties={
            'booking_id': openapi.Schema(type=openapi.TYPE_STRING),
            'new_status': openapi.Schema(type=openapi.TYPE_STRING),
            'admin_notes': openapi.Schema(type=openapi.TYPE_STRING),
        },
        required=['booking_id', 'new_status']
    ),
    responses={200: 'Booking status updated'}
)
def update_booking_status(request):
    """
    Update booking status by admin
    """
    booking_id = request.data.get('booking_id')
    new_status = request.data.get('new_status')
    admin_notes = request.data.get('admin_notes', '')
    
    try:
        booking = Booking.objects.get(booking_id=booking_id)
        old_status = booking.status
        
        booking.status = new_status
        booking.admin_notes = admin_notes
        
        if new_status == 'completed':
            booking.completed_at = timezone.now()
        
        booking.save()
        
        # Log admin activity
        AdminActivity.objects.create(
            admin_user=request.user,
            activity_type='booking_management',
            description=f"Updated booking {booking_id} status: {old_status} → {new_status}",
            target_model='Booking',
            target_id=str(booking.id),
            previous_data={'status': old_status},
            new_data={'status': new_status, 'admin_notes': admin_notes}
        )
        
        # Send notification to customer
        from notifications.tasks import create_notification
        create_notification.delay(
            user_id=booking.customer.id,
            notification_type='booking_updated',
            title='Booking Status Updated',
            message=f'Your booking status has been updated to: {new_status}',
            related_booking_id=booking.id
        )
        
        return Response({'message': 'Booking status updated successfully'})
        
    except Booking.DoesNotExist:
        return Response(
            {'error': 'Booking not found'},
            status=status.HTTP_404_NOT_FOUND
        )


@api_view(['POST'])
@permission_classes([IsAdminUser])
@swagger_auto_schema(
    operation_description="Upload before/after pictures for booking (admin only)",
    manual_parameters=[
        openapi.Parameter(
            'booking_id',
            openapi.IN_FORM,
            description="Booking UUID to add pictures to",
            type=openapi.TYPE_STRING,
            required=True
        ),
        openapi.Parameter(
            'picture_type',
            openapi.IN_FORM,
            description="Type of pictures being uploaded",
            type=openapi.TYPE_STRING,
            enum=['before', 'after'],
            required=True
        ),
        openapi.Parameter(
            'images',
            openapi.IN_FORM,
            description="Image files to upload (1-6 images)",
            type=openapi.TYPE_FILE,
            required=True
        ),
        openapi.Parameter(
            'captions',
            openapi.IN_FORM,
            description="Optional captions for images",
            type=openapi.TYPE_STRING,
            required=False
        ),
    ],
    responses={201: 'Pictures uploaded successfully'}
)
def upload_booking_pictures(request):
    """
    Upload before/after pictures for booking (admin only)
    Accepts multiple image files and optional captions
    """
    try:
        from bookings.serializers import BookingPictureUploadSerializer, BookingPictureSerializer
        
        # Extract data from request
        booking_id = request.data.get('booking_id')
        picture_type = request.data.get('picture_type')
        images = request.FILES.getlist('images')
        captions = request.data.getlist('captions') if 'captions' in request.data else []
        
        # Validate required fields
        if not booking_id:
            return Response(
                {'error': 'booking_id is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if not picture_type or picture_type not in ['before', 'after']:
            return Response(
                {'error': 'picture_type is required and must be "before" or "after"'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if not images:
            return Response(
                {'error': 'At least one image is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Validate booking exists
        try:
            booking = Booking.objects.get(booking_id=booking_id)
        except Booking.DoesNotExist:
            return Response(
                {'error': 'Booking not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Prepare data for serializer
        upload_data = {
            'booking_id': booking_id,
            'picture_type': picture_type,
            'images': images,
            'captions': captions if captions else []
        }
        
        # Validate the upload
        serializer = BookingPictureUploadSerializer(data=upload_data)
        try:
            if not serializer.is_valid():
                return Response(
                    {'errors': serializer.errors},
                    status=status.HTTP_400_BAD_REQUEST
                )
        except Exception as e:
            # Check if this is a table doesn't exist error
            if 'bookings_bookingpicture' in str(e) and ('does not exist' in str(e) or 'no such table' in str(e)):
                return Response(
                    {
                        'error': 'Picture upload feature not available yet. Please run database migrations first.',
                        'details': 'Run: python manage.py makemigrations bookings && python manage.py migrate'
                    },
                    status=status.HTTP_503_SERVICE_UNAVAILABLE
                )
            # Re-raise other exceptions
            raise e
        
        # Create the pictures
        try:
            created_pictures = serializer.create_pictures(serializer.validated_data, request.user)
        except Exception as e:
            # Check if this is a table doesn't exist error
            if 'bookings_bookingpicture' in str(e) and ('does not exist' in str(e) or 'no such table' in str(e)):
                return Response(
                    {
                        'error': 'Picture upload feature not available yet. Please run database migrations first.',
                        'details': 'Run: python manage.py makemigrations bookings && python manage.py migrate'
                    },
                    status=status.HTTP_503_SERVICE_UNAVAILABLE
                )
            # Re-raise other exceptions
            raise e
        
        # Log admin activity
        AdminActivity.objects.create(
            admin_user=request.user,
            activity_type='booking_management',
            description=f"Uploaded {len(created_pictures)} {picture_type} picture(s) for booking {booking_id}",
            target_model='Booking',
            target_id=str(booking.id),
            new_data={
                'picture_type': picture_type,
                'pictures_count': len(created_pictures),
                'picture_ids': [p.id for p in created_pictures]
            }
        )
        
        # Return success response with created pictures
        picture_data = BookingPictureSerializer(created_pictures, many=True, context={'request': request}).data
        
        return Response({
            'message': f'Successfully uploaded {len(created_pictures)} {picture_type} picture(s)',
            'uploaded_pictures': picture_data,
            'booking_id': str(booking_id),
            'picture_type': picture_type
        }, status=status.HTTP_201_CREATED)
        
    except Exception as e:
        logger.error(f"Error uploading booking pictures: {str(e)}")
        return Response(
            {'error': 'Failed to upload pictures. Please try again.'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
@permission_classes([IsAdminUser])
@swagger_auto_schema(
    operation_description="Get all pictures for a specific booking (admin only)",
    manual_parameters=[
        openapi.Parameter(
            'booking_id',
            openapi.IN_PATH,
            description="Booking UUID",
            type=openapi.TYPE_STRING,
            required=True
        ),
        openapi.Parameter(
            'picture_type',
            openapi.IN_QUERY,
            description="Filter by picture type",
            type=openapi.TYPE_STRING,
            enum=['before', 'after'],
            required=False
        ),
    ],
    responses={200: 'List of booking pictures'}
)
def get_booking_pictures(request, booking_id):
    """
    Get all pictures for a specific booking with optional filtering by type
    """
    try:
        from bookings.models import BookingPicture
        from bookings.serializers import BookingPictureSerializer
        
        # Validate booking exists
        try:
            booking = Booking.objects.get(booking_id=booking_id)
        except Booking.DoesNotExist:
            return Response(
                {'error': 'Booking not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Get pictures with optional filtering
        pictures = BookingPicture.objects.filter(booking=booking)
        
        picture_type = request.query_params.get('picture_type')
        if picture_type and picture_type in ['before', 'after']:
            pictures = pictures.filter(picture_type=picture_type)
        
        pictures = pictures.order_by('picture_type', 'uploaded_at')
        
        # Serialize and return
        serializer = BookingPictureSerializer(pictures, many=True, context={'request': request})
        
        # Add summary info
        before_count = BookingPicture.objects.filter(booking=booking, picture_type='before').count()
        after_count = BookingPicture.objects.filter(booking=booking, picture_type='after').count()
        
        return Response({
            'booking_id': str(booking_id),
            'pictures': serializer.data,
            'summary': {
                'before_count': before_count,
                'after_count': after_count,
                'total_count': before_count + after_count,
                'can_add_before': 6 - before_count,
                'can_add_after': 6 - after_count
            }
        })
        
    except Exception as e:
        # Check if this is a table doesn't exist error
        if 'bookings_bookingpicture' in str(e) and 'does not exist' in str(e):
            return Response(
                {
                    'error': 'Picture feature not available yet. Please run database migrations first.',
                    'details': 'Run: python manage.py makemigrations bookings && python manage.py migrate'
                },
                status=status.HTTP_503_SERVICE_UNAVAILABLE
            )
        
        logger.error(f"Error getting booking pictures: {str(e)}")
        return Response(
            {'error': 'Failed to retrieve pictures'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['PUT', 'PATCH'])
@permission_classes([IsAdminUser])
@swagger_auto_schema(
    operation_description="Update a specific booking picture (admin only)",
    manual_parameters=[
        openapi.Parameter(
            'picture_id',
            openapi.IN_PATH,
            description="Picture ID",
            type=openapi.TYPE_INTEGER,
            required=True
        ),
    ],
    request_body=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        properties={
            'caption': openapi.Schema(
                type=openapi.TYPE_STRING,
                description="New caption for the picture"
            ),
        }
    ),
    responses={200: 'Picture updated successfully'}
)
def update_booking_picture(request, picture_id):
    """
    Update a specific booking picture (currently only caption can be updated)
    """
    try:
        from bookings.models import BookingPicture
        from bookings.serializers import BookingPictureSerializer
        
        # Get the picture
        try:
            picture = BookingPicture.objects.get(id=picture_id)
        except BookingPicture.DoesNotExist:
            return Response(
                {'error': 'Picture not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Update caption if provided
        caption = request.data.get('caption', '')
        if 'caption' in request.data:
            picture.caption = caption
            picture.save()
            
            # Log admin activity
            AdminActivity.objects.create(
                admin_user=request.user,
                activity_type='booking_management',
                description=f"Updated caption for {picture.picture_type} picture (ID: {picture_id}) for booking {picture.booking.booking_id}",
                target_model='BookingPicture',
                target_id=str(picture.id),
                previous_data={'caption': picture.caption},
                new_data={'caption': caption}
            )
        
        # Return updated picture
        serializer = BookingPictureSerializer(picture, context={'request': request})
        return Response({
            'message': 'Picture updated successfully',
            'picture': serializer.data
        })
        
    except Exception as e:
        # Check if this is a table doesn't exist error
        if 'bookings_bookingpicture' in str(e) and 'does not exist' in str(e):
            return Response(
                {
                    'error': 'Picture feature not available yet. Please run database migrations first.',
                    'details': 'Run: python manage.py makemigrations bookings && python manage.py migrate'
                },
                status=status.HTTP_503_SERVICE_UNAVAILABLE
            )
        
        logger.error(f"Error updating booking picture: {str(e)}")
        return Response(
            {'error': 'Failed to update picture'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['DELETE'])
@permission_classes([IsAdminUser])
@swagger_auto_schema(
    operation_description="Delete a specific booking picture (admin only)",
    manual_parameters=[
        openapi.Parameter(
            'picture_id',
            openapi.IN_PATH,
            description="Picture ID to delete",
            type=openapi.TYPE_INTEGER,
            required=True
        ),
    ],
    responses={204: 'Picture deleted successfully'}
)
def delete_booking_picture(request, picture_id):
    """
    Delete a specific booking picture
    """
    try:
        from bookings.models import BookingPicture
        
        # Get the picture
        try:
            picture = BookingPicture.objects.get(id=picture_id)
        except BookingPicture.DoesNotExist:
            return Response(
                {'error': 'Picture not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Store info for logging before deletion
        booking_id = picture.booking.booking_id
        picture_type = picture.picture_type
        image_path = picture.image.name if picture.image else None
        
        # Delete the image file from storage
        if picture.image:
            try:
                picture.image.delete(save=False)
            except Exception as e:
                logger.warning(f"Failed to delete image file {image_path}: {str(e)}")
        
        # Delete the database record
        picture.delete()
        
        # Log admin activity
        AdminActivity.objects.create(
            admin_user=request.user,
            activity_type='booking_management',
            description=f"Deleted {picture_type} picture (ID: {picture_id}) for booking {booking_id}",
            target_model='BookingPicture',
            target_id=str(picture_id),
            previous_data={
                'picture_type': picture_type,
                'image_path': image_path,
                'booking_id': str(booking_id)
            }
        )
        
        return Response({
            'message': f'{picture_type.title()} picture deleted successfully',
            'deleted_picture_id': picture_id,
            'booking_id': str(booking_id)
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        # Check if this is a table doesn't exist error
        if 'bookings_bookingpicture' in str(e) and 'does not exist' in str(e):
            return Response(
                {
                    'error': 'Picture feature not available yet. Please run database migrations first.',
                    'details': 'Run: python manage.py makemigrations bookings && python manage.py migrate'
                },
                status=status.HTTP_503_SERVICE_UNAVAILABLE
            )
        
        logger.error(f"Error deleting booking picture: {str(e)}")
        return Response(
            {'error': 'Failed to delete picture'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['POST'])
@permission_classes([IsAdminUser])
@swagger_auto_schema(
    operation_description="Upload a single picture to a booking (admin only)",
    manual_parameters=[
        openapi.Parameter(
            'booking_id',
            openapi.IN_PATH,
            description="Booking UUID to add picture to",
            type=openapi.TYPE_STRING,
            required=True
        ),
        openapi.Parameter(
            'picture_type',
            openapi.IN_FORM,
            description="Type of picture being uploaded",
            type=openapi.TYPE_STRING,
            enum=['before', 'after'],
            required=True
        ),
        openapi.Parameter(
            'image',
            openapi.IN_FORM,
            description="Single image file to upload",
            type=openapi.TYPE_FILE,
            required=True
        ),
        openapi.Parameter(
            'caption',
            openapi.IN_FORM,
            description="Optional caption for the image",
            type=openapi.TYPE_STRING,
            required=False
        ),
    ],
    responses={201: 'Picture uploaded successfully'}
)
def upload_single_booking_picture(request, booking_id):
    """
    Upload a single picture to a booking (alternative to bulk upload)
    """
    try:
        from bookings.models import BookingPicture
        from bookings.serializers import BookingPictureSerializer
        
        # Extract data from request
        picture_type = request.data.get('picture_type')
        image = request.FILES.get('image')
        caption = request.data.get('caption', '')
        
        # Validate required fields
        if not picture_type or picture_type not in ['before', 'after']:
            return Response(
                {'error': 'picture_type is required and must be "before" or "after"'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if not image:
            return Response(
                {'error': 'image file is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Validate booking exists
        try:
            booking = Booking.objects.get(booking_id=booking_id)
        except Booking.DoesNotExist:
            return Response(
                {'error': 'Booking not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Check if we can add this picture without exceeding limit
        if not BookingPicture.can_add_pictures(booking, picture_type, 1):
            current_count = BookingPicture.get_picture_count(booking, picture_type)
            return Response(
                {
                    'error': f'Cannot add more {picture_type} pictures. This booking already has {current_count} {picture_type} pictures. Maximum allowed is 6 per type.'
                },
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Validate image file
        if image.size > 10 * 1024 * 1024:  # 10MB
            return Response(
                {'error': 'Image file size cannot exceed 10MB'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        allowed_formats = ['image/jpeg', 'image/jpg', 'image/png', 'image/webp']
        if hasattr(image, 'content_type') and image.content_type not in allowed_formats:
            return Response(
                {'error': 'Only JPEG, PNG, and WebP image formats are allowed'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Create the picture
        picture = BookingPicture.objects.create(
            booking=booking,
            picture_type=picture_type,
            image=image,
            caption=caption,
            uploaded_by=request.user
        )
        
        # Log admin activity
        AdminActivity.objects.create(
            admin_user=request.user,
            activity_type='booking_management',
            description=f"Uploaded single {picture_type} picture for booking {booking_id}",
            target_model='BookingPicture',
            target_id=str(picture.id),
            new_data={
                'picture_type': picture_type,
                'caption': caption,
                'booking_id': str(booking_id)
            }
        )
        
        # Return success response
        serializer = BookingPictureSerializer(picture, context={'request': request})
        return Response({
            'message': f'Successfully uploaded {picture_type} picture',
            'picture': serializer.data,
            'booking_id': str(booking_id)
        }, status=status.HTTP_201_CREATED)
        
    except Exception as e:
        # Check if this is a table doesn't exist error
        if 'bookings_bookingpicture' in str(e) and 'does not exist' in str(e):
            return Response(
                {
                    'error': 'Picture upload feature not available yet. Please run database migrations first.',
                    'details': 'Run: python manage.py makemigrations bookings && python manage.py migrate'
                },
                status=status.HTTP_503_SERVICE_UNAVAILABLE
            )
        
        logger.error(f"Error uploading single booking picture: {str(e)}")
        return Response(
            {'error': 'Failed to upload picture'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


# ===================== PAYMENT MANAGEMENT =====================

class AdminPaymentListView(generics.ListAPIView):
    """
    List payments (admin)
    """
    serializer_class = AdminPaymentSerializer
    permission_classes = [IsAdminUser]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['status', 'payment_type', 'currency']
    search_fields = ['customer__email', 'booking__booking_id', 'stripe_payment_intent_id']
    ordering_fields = ['created_at', 'amount', 'processed_at']
    ordering = ['-created_at']
    
    def get_queryset(self):
        return Payment.objects.select_related('customer', 'booking')


class AdminPaymentDetailView(generics.RetrieveAPIView):
    """
    Get payment details (admin)
    """
    serializer_class = AdminPaymentSerializer
    permission_classes = [IsAdminUser]
    lookup_field = 'payment_id'
    queryset = Payment.objects.select_related('customer', 'booking')


@api_view(['POST'])
@permission_classes([IsAdminUser])
@swagger_auto_schema(
    operation_description="Update payment status (admin)",
    request_body=AdminPaymentUpdateSerializer,
    responses={200: 'Payment status updated'}
)
def update_payment_status(request):
    """
    Update payment status by admin
    """
    serializer = AdminPaymentUpdateSerializer(data=request.data)
    
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    payment_id = serializer.validated_data['payment_id']
    new_status = serializer.validated_data['new_status']
    admin_notes = serializer.validated_data.get('admin_notes', '')
    
    try:
        payment = Payment.objects.get(payment_id=payment_id)
        old_status = payment.status
        
        payment.status = new_status
        payment.save()
        
        # Update booking payment status if needed
        if new_status == 'succeeded':
            booking = payment.booking
            if payment.payment_type == 'deposit':
                booking.payment_status = 'deposit_paid'
            elif payment.payment_type in ['remaining', 'full']:
                booking.payment_status = 'fully_paid'
            booking.save()
        
        # Log admin activity
        AdminActivity.objects.create(
            admin_user=request.user,
            activity_type='payment_management',
            description=f"Updated payment {payment_id} status: {old_status} → {new_status}",
            target_model='Payment',
            target_id=str(payment.id),
            previous_data={'status': old_status},
            new_data={'status': new_status, 'admin_notes': admin_notes}
        )
        
        return Response({'message': 'Payment status updated successfully'})
        
    except Payment.DoesNotExist:
        return Response(
            {'error': 'Payment not found'},
            status=status.HTTP_404_NOT_FOUND
        )


# ===================== REGION MANAGEMENT =====================

class AdminRegionListView(generics.ListCreateAPIView):
    """
    List and create regions (admin)
    """
    serializer_class = AdminRegionSerializer
    permission_classes = [IsAdminUser]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['is_active', 'currency']
    search_fields = ['name', 'code', 'country_code']
    ordering = ['name']
    
    def get_queryset(self):
        return Region.objects.prefetch_related('current_users', 'professionals', 'categories')


class AdminRegionDetailView(generics.RetrieveUpdateDestroyAPIView):
    """
    Get, update, or delete region (admin)
    """
    serializer_class = AdminRegionSerializer
    permission_classes = [IsAdminUser]
    queryset = Region.objects.all()


class AdminRegionalSettingsView(generics.ListCreateAPIView):
    """
    Manage regional settings (admin)
    """
    serializer_class = AdminRegionalSettingsSerializer
    permission_classes = [IsAdminUser]
    filter_backends = [DjangoFilterBackend, SearchFilter]
    filterset_fields = ['region']
    search_fields = ['key', 'description']
    
    def get_queryset(self):
        return RegionalSettings.objects.select_related('region')


# ===================== REVIEW MODERATION =====================

class AdminReviewListView(generics.ListAPIView):
    """
    Review moderation (admin)
    """
    serializer_class = AdminReviewModerationSerializer
    permission_classes = [IsAdminUser]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['is_verified', 'is_published', 'overall_rating']
    search_fields = ['comment', 'customer__email', 'professional__user__email']
    ordering_fields = ['created_at', 'overall_rating']
    ordering = ['-created_at']
    
    def get_queryset(self):
        return Review.objects.select_related(
            'customer', 'professional__user', 'service'
        )


@api_view(['POST'])
@permission_classes([IsAdminUser])
@swagger_auto_schema(
    operation_description="Moderate review (admin)",
    request_body=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        properties={
            'review_id': openapi.Schema(type=openapi.TYPE_INTEGER),
            'action': openapi.Schema(type=openapi.TYPE_STRING, enum=['approve', 'reject', 'delete']),
            'reason': openapi.Schema(type=openapi.TYPE_STRING),
        },
        required=['review_id', 'action']
    ),
    responses={200: 'Review moderated'}
)
def moderate_review(request):
    """
    Moderate review by admin
    """
    review_id = request.data.get('review_id')
    action = request.data.get('action')
    reason = request.data.get('reason', '')
    
    try:
        review = Review.objects.get(id=review_id)
        
        if action == 'approve':
            review.is_verified = True
            review.is_published = True
        elif action == 'reject':
            review.is_published = False
        elif action == 'delete':
            review.delete()
            
            AdminActivity.objects.create(
                admin_user=request.user,
                activity_type='content_moderation',
                description=f"Deleted review by {review.customer.email}",
                target_model='Review',
                target_id=str(review_id)
            )
            
            return Response({'message': 'Review deleted successfully'})
        
        review.save()
        
        # Update professional rating if needed
        if action == 'approve':
            review.professional.update_rating()
        
        AdminActivity.objects.create(
            admin_user=request.user,
            activity_type='content_moderation',
            description=f"Moderated review: {action} - {reason}",
            target_model='Review',
            target_id=str(review.id)
        )
        
        return Response({'message': f'Review {action}ed successfully'})
        
    except Review.DoesNotExist:
        return Response(
            {'error': 'Review not found'},
            status=status.HTTP_404_NOT_FOUND
        )


# ===================== NOTIFICATION MANAGEMENT =====================

class AdminNotificationListView(generics.ListAPIView):
    """
    List notifications (admin)
    """
    serializer_class = AdminNotificationSerializer
    permission_classes = [IsAdminUser]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['notification_type', 'is_read', 'push_sent', 'email_sent']
    search_fields = ['title', 'message', 'user__email']
    ordering_fields = ['created_at']
    ordering = ['-created_at']
    
    def get_queryset(self):
        return Notification.objects.select_related('user')


@api_view(['POST'])
@permission_classes([IsAdminUser])
@swagger_auto_schema(
    operation_description="Send broadcast notification (admin)",
    request_body=BroadcastNotificationSerializer,
    responses={200: 'Notification sent'}
)
def send_broadcast_notification(request):
    """
    Send broadcast notification to users
    """
    serializer = BroadcastNotificationSerializer(data=request.data)
    
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    target = serializer.validated_data['target']
    region = serializer.validated_data.get('region')
    title = serializer.validated_data['title']
    message = serializer.validated_data['message']
    send_push = serializer.validated_data['send_push']
    send_email = serializer.validated_data['send_email']
    
    # Get target users
    if target == 'all':
        users = User.objects.filter(is_active=True)
    elif target == 'customers':
        users = User.objects.filter(user_type='customer', is_active=True)
    elif target == 'professionals':
        users = User.objects.filter(user_type='professional', is_active=True)
    elif target == 'region':
        users = User.objects.filter(current_region=region, is_active=True)
    elif target == 'verified_professionals':
        professional_user_ids = Professional.objects.filter(
            is_verified=True, is_active=True
        ).values_list('user_id', flat=True)
        users = User.objects.filter(id__in=professional_user_ids, is_active=True)
    
    # Send notifications asynchronously
    from notifications.tasks import create_notification, send_push_notification, send_email_notification
    
    user_count = 0
    for user in users[:1000]:  # Limit to prevent overload
        create_notification.delay(
            user_id=user.id,
            notification_type='system_announcement',
            title=title,
            message=message
        )
        
        if send_push:
            send_push_notification.delay(
                user_id=user.id,
                title=title,
                body=message,
                data={'type': 'broadcast'}
            )
        
        if send_email:
            send_email_notification.delay(
                user_id=user.id,
                subject=title,
                template='emails/broadcast_notification.html',
                context={'title': title, 'message': message}
            )
        
        user_count += 1
    
    # Log admin activity
    AdminActivity.objects.create(
        admin_user=request.user,
        activity_type='system_configuration',
        description=f"Sent broadcast notification to {user_count} users: {title}",
        target_model='Notification',
        new_data={
            'target': target,
            'title': title,
            'user_count': user_count
        }
    )
    
    return Response({
        'message': f'Broadcast notification sent to {user_count} users',
        'user_count': user_count
    })


# ===================== BULK OPERATIONS =====================

@api_view(['POST'])
@permission_classes([IsAdminUser])
@swagger_auto_schema(
    operation_description="Perform bulk operations (admin)",
    request_body=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        properties={
            'model': openapi.Schema(type=openapi.TYPE_STRING),
            'operation': openapi.Schema(type=openapi.TYPE_STRING),
            'ids': openapi.Schema(type=openapi.TYPE_ARRAY, items=openapi.Schema(type=openapi.TYPE_INTEGER)),
            'reason': openapi.Schema(type=openapi.TYPE_STRING),
        },
        required=['model', 'operation', 'ids']
    ),
    responses={200: 'Bulk operation completed'}
)
def bulk_operations(request):
    """
    Perform bulk operations on multiple items
    """
    model_name = request.data.get('model')
    operation = request.data.get('operation')
    ids = request.data.get('ids', [])
    reason = request.data.get('reason', '')
    
    if not all([model_name, operation, ids]):
        return Response(
            {'error': 'model, operation, and ids are required'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    # Map model names to actual models
    model_mapping = {
        'user': User,
        'professional': Professional,
        'category': Category,
        'service': Service,
        'addon': AddOn,
        'booking': Booking,
        'review': Review,
    }
    
    if model_name not in model_mapping:
        return Response(
            {'error': 'Invalid model name'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    model_class = model_mapping[model_name]
    
    try:
        queryset = model_class.objects.filter(id__in=ids)
        count = queryset.count()
        
        if operation == 'activate':
            queryset.update(is_active=True)
        elif operation == 'deactivate':
            queryset.update(is_active=False)
        elif operation == 'verify' and model_name == 'professional':
            queryset.update(is_verified=True, verified_at=timezone.now())
        elif operation == 'unverify' and model_name == 'professional':
            queryset.update(is_verified=False)
        elif operation == 'feature' and model_name == 'category':
            queryset.update(is_featured=True)
        elif operation == 'unfeature' and model_name == 'category':
            queryset.update(is_featured=False)
        elif operation == 'delete':
            queryset.delete()
        else:
            return Response(
                {'error': 'Invalid operation'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Log admin activity
        AdminActivity.objects.create(
            admin_user=request.user,
            activity_type='system_configuration',
            description=f"Bulk {operation} on {count} {model_name}s: {reason}",
            target_model=model_class.__name__,
            new_data={
                'operation': operation,
                'count': count,
                'ids': ids,
                'reason': reason
            }
        )
        
        return Response({
            'message': f'Bulk {operation} completed on {count} {model_name}s',
            'count': count
        })
        
    except Exception as e:
        return Response(
            {'error': str(e)},
            status=status.HTTP_400_BAD_REQUEST
        )
        
# Add these missing view functions to the end of admin_panel/views.py

@api_view(['POST'])
@permission_classes([IsAdminUser])
@swagger_auto_schema(
    operation_description="Verify professional",
    request_body=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        properties={
            'professional_id': openapi.Schema(type=openapi.TYPE_INTEGER),
            'action': openapi.Schema(type=openapi.TYPE_STRING, enum=['approve', 'reject']),
            'notes': openapi.Schema(type=openapi.TYPE_STRING),
        },
        required=['professional_id', 'action']
    ),
    responses={200: 'Professional verification updated'}
)
def verify_professional(request):
    """
    Verify or reject professional - ADD swagger_fake_view check
    """
    # Handle schema generation
    if getattr(request, 'swagger_fake_view', False):
        return Response({'message': 'Schema generation'})
        
    professional_id = request.data.get('professional_id')
    action = request.data.get('action')
    notes = request.data.get('notes', '')
    
    try:
        professional = Professional.objects.get(id=professional_id)
        
        if action == 'approve':
            professional.is_verified = True
            professional.verified_at = timezone.now()
            message = 'Professional verified successfully'
        else:
            professional.is_verified = False
            professional.verified_at = None
            message = 'Professional verification rejected'
        
        professional.save()
        
        # Log admin activity
        AdminActivity.objects.create(
            admin_user=request.user,
            activity_type='professional_verification',
            description=f"Professional verification {action}: {professional.user.email}",
            target_model='Professional',
            target_id=str(professional.id),
            new_data={'action': action, 'notes': notes}
        )
        
        # Send notification to professional
        from notifications.tasks import send_professional_verification_notification
        send_professional_verification_notification.delay(professional.id, action, notes)
        
        return Response({'message': message})
        
    except Professional.DoesNotExist:
        return Response(
            {'error': 'Professional not found'},
            status=status.HTTP_404_NOT_FOUND
        )



@api_view(['GET'])
@permission_classes([IsAdminUser])
@swagger_auto_schema(
    operation_description="Get analytics data",
    responses={200: 'Analytics data'}
)
def analytics_data(request):
    """
    Get comprehensive analytics data
    """
    from django.db.models import Count, Sum, Avg
    from datetime import datetime, timedelta
    
    # Get date range
    days = int(request.GET.get('days', 30))
    start_date = timezone.now() - timedelta(days=days)
    
    # User analytics
    user_data = User.objects.filter(date_joined__gte=start_date).extra(
        {'day': 'date(date_joined)'}
    ).values('day').annotate(count=Count('id')).order_by('day')
    
    # Booking analytics
    booking_data = Booking.objects.filter(created_at__gte=start_date).extra(
        {'day': 'date(created_at)'}
    ).values('day').annotate(
        count=Count('id'),
        revenue=Sum('total_amount')
    ).order_by('day')
    
    # Payment analytics
    payment_data = Payment.objects.filter(
        created_at__gte=start_date,
        status='succeeded'
    ).extra(
        {'day': 'date(created_at)'}
    ).values('day').annotate(
        count=Count('id'),
        total=Sum('amount')
    ).order_by('day')
    
    return Response({
        'user_registrations': list(user_data),
        'booking_trends': list(booking_data),
        'payment_trends': list(payment_data),
    })


@api_view(['POST'])
@permission_classes([IsAdminUser])
@swagger_auto_schema(
    operation_description="Resolve system alert",
    request_body=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        properties={
            'alert_id': openapi.Schema(type=openapi.TYPE_STRING),
            'resolution_notes': openapi.Schema(type=openapi.TYPE_STRING),
        },
        required=['alert_id']
    ),
    responses={200: 'Alert resolved'}
)
def resolve_alert(request):
    """
    Resolve system alert
    """
    alert_id = request.data.get('alert_id')
    resolution_notes = request.data.get('resolution_notes', '')
    
    try:
        alert = SystemAlert.objects.get(alert_id=alert_id)
        alert.is_resolved = True
        alert.resolved_by = request.user
        alert.resolved_at = timezone.now()
        alert.resolution_notes = resolution_notes
        alert.save()
        
        return Response({'message': 'Alert resolved successfully'})
        
    except SystemAlert.DoesNotExist:
        return Response(
            {'error': 'Alert not found'},
            status=status.HTTP_404_NOT_FOUND
        )


@api_view(['POST'])
@permission_classes([IsAdminUser])
@swagger_auto_schema(
    operation_description="Assign support ticket",
    request_body=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        properties={
            'ticket_id': openapi.Schema(type=openapi.TYPE_STRING),
            'assigned_to': openapi.Schema(type=openapi.TYPE_INTEGER),
        },
        required=['ticket_id', 'assigned_to']
    ),
    responses={200: 'Ticket assigned'}
)
def assign_ticket(request):
    """
    Assign support ticket to admin user
    """
    ticket_id = request.data.get('ticket_id')
    assigned_to_id = request.data.get('assigned_to')
    
    try:
        ticket = SupportTicket.objects.get(ticket_id=ticket_id)
        assigned_to = User.objects.get(id=assigned_to_id)
        
        ticket.assigned_to = assigned_to
        ticket.status = 'in_progress'
        ticket.save()
        
        return Response({'message': 'Ticket assigned successfully'})
        
    except (SupportTicket.DoesNotExist, User.DoesNotExist):
        return Response(
            {'error': 'Ticket or user not found'},
            status=status.HTTP_404_NOT_FOUND
        )


# ===================== SYSTEM MANAGEMENT VIEWS =====================

class SystemAlertsView(generics.ListAPIView):
    """
    List system alerts - FIXED serializer_class
    """
    serializer_class = SystemAlertSerializer  # Fixed: Added missing serializer_class
    permission_classes = [IsAdminUser]
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = ['alert_type', 'category', 'is_resolved']
    ordering = ['-created_at']
    
    def get_queryset(self):
        # Handle schema generation with AnonymousUser
        if getattr(self, 'swagger_fake_view', False):
            return SystemAlert.objects.none()
        return SystemAlert.objects.filter(is_resolved=False).order_by('-created_at')


class SupportTicketsView(generics.ListAPIView):
    """
    List support tickets - FIXED serializer_class
    """
    serializer_class = SupportTicketSerializer  # Fixed: Added missing serializer_class
    permission_classes = [IsAdminUser]
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = ['status', 'priority', 'category', 'assigned_to']
    ordering = ['-created_at']
    
    def get_queryset(self):
        # Handle schema generation with AnonymousUser
        if getattr(self, 'swagger_fake_view', False):
            return SupportTicket.objects.none()
        return SupportTicket.objects.all().order_by('-created_at')


@api_view(['POST'])
@permission_classes([IsAdminUser])
@swagger_auto_schema(
    operation_description="Handle booking reschedule request (admin)",
    request_body=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        required=['reschedule_id', 'action'],
        properties={
            'reschedule_id': openapi.Schema(type=openapi.TYPE_INTEGER, description='Reschedule request ID'),
            'action': openapi.Schema(
                type=openapi.TYPE_STRING, 
                enum=['approve', 'reject'],
                description='Action to take on reschedule request'
            ),
            'new_date': openapi.Schema(
                type=openapi.TYPE_STRING, 
                format='date',
                description='New date for rescheduled booking (required when approving)'
            ),
            'new_time': openapi.Schema(
                type=openapi.TYPE_STRING, 
                format='time',
                description='New time for rescheduled booking (required when approving)'
            ),
            'admin_notes': openapi.Schema(type=openapi.TYPE_STRING, description='Admin notes for the decision'),
        }
    ),
    responses={200: 'Reschedule request processed'}
)
def handle_reschedule_request(request):
    """
    Handle booking reschedule request by admin
    """
    reschedule_id = request.data.get('reschedule_id')
    action = request.data.get('action')
    new_date = request.data.get('new_date')
    new_time = request.data.get('new_time')
    admin_notes = request.data.get('admin_notes', '')
    
    if not reschedule_id or not action:
        return Response(
            {'error': 'reschedule_id and action are required'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    if action not in ['approve', 'reject']:
        return Response(
            {'error': 'action must be either "approve" or "reject"'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    # Validate new date and time when approving
    if action == 'approve':
        if not new_date or not new_time:
            return Response(
                {'error': 'new_date and new_time are required when approving reschedule request'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Validate that new date is not in the past
        from datetime import datetime
        try:
            new_datetime = datetime.strptime(f"{new_date} {new_time}", "%Y-%m-%d %H:%M")
            if new_datetime < timezone.now():
                return Response(
                    {'error': 'New date and time cannot be in the past'},
                    status=status.HTTP_400_BAD_REQUEST
                )
        except ValueError:
            return Response(
                {'error': 'Invalid date or time format. Use YYYY-MM-DD for date and HH:MM for time'},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    try:
        from bookings.models import BookingReschedule
        reschedule_request = BookingReschedule.objects.get(id=reschedule_id, status='pending')
        booking = reschedule_request.booking
        
        # Update reschedule request status
        reschedule_request.status = 'approved' if action == 'approve' else 'rejected'
        reschedule_request.responded_by = request.user
        reschedule_request.response_reason = admin_notes
        reschedule_request.responded_at = timezone.now()
        
        if action == 'approve':
            # Update the requested date/time with admin's choice
            reschedule_request.requested_date = new_date
            reschedule_request.requested_time = new_time
        
        reschedule_request.save()
        
        if action == 'approve':
            # Update booking with new date and time (admin's choice)
            booking.scheduled_date = new_date
            booking.scheduled_time = new_time
            booking.status = 'confirmed'  # Re-confirm the booking
            booking.save()
            
            # Create status history
            from bookings.models import BookingStatusHistory
            BookingStatusHistory.objects.create(
                booking=booking,
                previous_status='confirmed',
                new_status='rescheduled',
                changed_by=request.user,
                reason=f"Reschedule approved by admin. New date: {new_date} {new_time}. Notes: {admin_notes}"
            )
            
            # Send notification to customer
            from notifications.tasks import create_notification
            create_notification.delay(
                user_id=booking.customer.id,
                notification_type='reschedule_approved',
                title='Reschedule Request Approved',
                message=f'Your reschedule request for booking {booking.booking_id} has been approved. New date: {new_date} at {new_time}. Admin notes: {admin_notes}',
                related_booking_id=booking.id
            )
            
            message = f'Reschedule request approved. Booking updated to {new_date} at {new_time}'
        else:
            # Send rejection notification to customer
            from notifications.tasks import create_notification
            create_notification.delay(
                user_id=booking.customer.id,
                notification_type='reschedule_rejected',
                title='Reschedule Request Rejected',
                message=f'Your reschedule request for booking {booking.booking_id} has been rejected. Reason: {admin_notes}',
                related_booking_id=booking.id
            )
            
            message = 'Reschedule request rejected'
        
        # Log admin activity
        AdminActivity.objects.create(
            admin_user=request.user,
            activity_type='reschedule_management',
            description=f"{action.title()}d reschedule request {reschedule_id} for booking {booking.booking_id}",
            target_model='BookingReschedule',
            target_id=str(reschedule_request.id),
            previous_data={'status': 'pending'},
            new_data={'status': reschedule_request.status, 'admin_notes': admin_notes}
        )
        
        return Response({'message': message})
        
    except BookingReschedule.DoesNotExist:
        return Response(
            {'error': 'Reschedule request not found or already processed'},
            status=status.HTTP_404_NOT_FOUND
        )
    except Exception as e:
        logger.error(f"Error handling reschedule request: {str(e)}")
        return Response(
            {'error': str(e)},
            status=status.HTTP_400_BAD_REQUEST
        )


@api_view(['POST'])
@permission_classes([IsAdminUser])
@swagger_auto_schema(
    operation_description="Fix booking payment status (admin)",
    request_body=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        required=['booking_id'],
        properties={
            'booking_id': openapi.Schema(type=openapi.TYPE_STRING, format='uuid', description='Booking ID to fix'),
        }
    ),
    responses={200: 'Payment status fixed'}
)
def fix_booking_payment_status(request):
    """
    Fix booking payment status based on actual payments (admin utility)
    """
    booking_id = request.data.get('booking_id')
    
    if not booking_id:
        return Response(
            {'error': 'booking_id is required'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    try:
        from payments.services import StripePaymentService
        result = StripePaymentService.fix_booking_payment_status(booking_id)
        
        if result['success']:
            # Log admin activity
            AdminActivity.objects.create(
                admin_user=request.user,
                activity_type='payment_status_fix',
                description=f"Fixed payment status for booking {booking_id}: {result['old_status']} -> {result['new_status']}",
                target_model='Booking',
                target_id=booking_id,
                previous_data={'payment_status': result['old_status']},
                new_data={'payment_status': result['new_status']}
            )
            
            return Response({
                'message': 'Payment status fixed successfully',
                'old_status': result['old_status'],
                'new_status': result['new_status'],
                'total_paid': result['total_paid'],
                'booking_total': result['booking_total']
            })
        else:
            return Response(
                {'error': result['error']},
                status=status.HTTP_400_BAD_REQUEST
            )
            
    except Exception as e:
        logger.error(f"Error fixing payment status: {str(e)}")
        return Response(
            {'error': str(e)},
            status=status.HTTP_400_BAD_REQUEST
        )


@api_view(['POST'])
@permission_classes([IsAdminUser])
@swagger_auto_schema(
    operation_description="Test professional update serializer",
    request_body=AdminProfessionalUpdateSerializer,
    responses={200: 'Test successful'}
)
def test_professional_update(request):
    """
    Test endpoint to debug professional update issues
    """
    try:
        # Test the serializer
        serializer = AdminProfessionalUpdateSerializer(data=request.data)
        if serializer.is_valid():
            return Response({
                'message': 'Serializer is valid',
                'validated_data': serializer.validated_data
            })
        else:
            return Response({
                'message': 'Serializer validation failed',
                'errors': serializer.errors
            }, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Error in test_professional_update: {str(e)}")
        return Response({
            'error': str(e),
            'type': type(e).__name__
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
