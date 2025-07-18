from rest_framework import generics, status, permissions
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

class AdminDashboardView(generics.GenericAPIView):
    """
    Comprehensive admin dashboard with detailed metrics
    """
    permission_classes = [IsAdminUser]
    
    @swagger_auto_schema(
        operation_description="Get comprehensive admin dashboard statistics",
        responses={200: AdminDashboardStatsSerializer()}
    )
    def get(self, request):
        today = timezone.now().date()
        week_start = today - timedelta(days=today.weekday())
        month_start = today.replace(day=1)
        
        # Calculate previous periods for growth
        prev_week_start = week_start - timedelta(days=7)
        prev_month_start = (month_start - timedelta(days=1)).replace(day=1)
        
        # User Statistics
        total_users = User.objects.count()
        total_customers = User.objects.filter(user_type='customer').count()
        total_professionals = Professional.objects.count()
        
        new_users_today = User.objects.filter(date_joined__date=today).count()
        new_users_this_week = User.objects.filter(date_joined__date__gte=week_start).count()
        new_users_this_month = User.objects.filter(date_joined__date__gte=month_start).count()
        
        # Booking Statistics
        total_bookings = Booking.objects.count()
        bookings_today = Booking.objects.filter(created_at__date=today).count()
        bookings_this_week = Booking.objects.filter(created_at__date__gte=week_start).count()
        bookings_this_month = Booking.objects.filter(created_at__date__gte=month_start).count()
        
        pending_bookings = Booking.objects.filter(status='pending').count()
        confirmed_bookings = Booking.objects.filter(status='confirmed').count()
        completed_bookings = Booking.objects.filter(status='completed').count()
        
        # Revenue Statistics
        successful_payments = Payment.objects.filter(status='succeeded')
        total_revenue = successful_payments.aggregate(total=Sum('amount'))['total'] or 0
        revenue_today = successful_payments.filter(created_at__date=today).aggregate(total=Sum('amount'))['total'] or 0
        revenue_this_week = successful_payments.filter(created_at__date__gte=week_start).aggregate(total=Sum('amount'))['total'] or 0
        revenue_this_month = successful_payments.filter(created_at__date__gte=month_start).aggregate(total=Sum('amount'))['total'] or 0
        
        # Professional Statistics
        pending_verifications = Professional.objects.filter(is_verified=False, is_active=True).count()
        verified_professionals = Professional.objects.filter(is_verified=True).count()
        active_professionals = Professional.objects.filter(is_active=True).count()
        
        # System Statistics
        total_services = Service.objects.filter(is_active=True).count()
        total_categories = Category.objects.filter(is_active=True).count()
        total_regions = Region.objects.filter(is_active=True).count()
        open_support_tickets = SupportTicket.objects.filter(status__in=['open', 'in_progress']).count()
        unresolved_alerts = SystemAlert.objects.filter(is_resolved=False).count()
        
        # Growth Calculations
        prev_week_users = User.objects.filter(
            date_joined__date__gte=prev_week_start,
            date_joined__date__lt=week_start
        ).count()
        prev_week_bookings = Booking.objects.filter(
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
        
        stats = {
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
            'total_categories': total_categories,
            'total_regions': total_regions,
            'open_support_tickets': open_support_tickets,
            'unresolved_alerts': unresolved_alerts,
            'user_growth_rate': round(user_growth_rate, 2),
            'booking_growth_rate': round(booking_growth_rate, 2),
            'revenue_growth_rate': round(revenue_growth_rate, 2),
        }
        
        return Response(stats)


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
        return User.objects.select_related('current_region').prefetch_related('bookings', 'payments')
    
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
            # Log admin activity
            AdminActivity.objects.create(
                admin_user=request.user,
                activity_type='user_action',
                description=f"Created user: {response.data['email']}",
                target_model='User',
                target_id=str(response.data['id'])
            )
        
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
        AdminActivity.objects.create(
            admin_user=self.request.user,
            activity_type='user_action',
            description=f"Deleted user: {instance.email}",
            target_model='User',
            target_id=str(instance.id)
        )
        instance.delete()


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
        return Professional.objects.select_related('user').prefetch_related('regions', 'services')
    
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
            AdminActivity.objects.create(
                admin_user=request.user,
                activity_type='professional_verification',
                description=f"Created professional: {request.data['email']}",
                target_model='Professional',
                target_id=str(response.data['id'])
            )
        
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


# ===================== CATEGORY MANAGEMENT =====================

class AdminCategoryListView(generics.ListCreateAPIView):
    """
    List and create categories (admin)
    """
    serializer_class = AdminCategorySerializer
    permission_classes = [IsAdminUser]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['region', 'is_active']
    search_fields = ['name', 'description']
    ordering_fields = ['sort_order', 'name', 'created_at']
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
            AdminActivity.objects.create(
                admin_user=request.user,
                activity_type='content_moderation',
                description=f"Created category: {response.data['name']}",
                target_model='Category',
                target_id=str(response.data['id'])
            )
        
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
    filterset_fields = ['category', 'category__region', 'is_active']
    search_fields = ['name', 'description']
    ordering = ['category__name', 'name']
    
    def get_queryset(self):
        return AddOn.objects.select_related('category__region')


class AdminAddOnDetailView(generics.RetrieveUpdateDestroyAPIView):
    """
    Get, update, or delete add-on (admin)
    """
    serializer_class = AdminAddOnSerializer
    permission_classes = [IsAdminUser]
    queryset = AddOn.objects.all()


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
        return Booking.objects.select_related(
            'customer', 'professional__user', 'service', 'region'
        )


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
