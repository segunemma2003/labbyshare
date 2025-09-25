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
from rest_framework.exceptions import ValidationError



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
        logger = logging.getLogger(__name__)
        
        # 🔍 COMPREHENSIVE REQUEST LOGGING
        logger.info("=" * 80)
        logger.info("🔍 PROFESSIONAL CREATE REQUEST DEBUG")
        logger.info("=" * 80)
        
        # Log all request data
        logger.info(f"📋 Request method: {request.method}")
        logger.info(f"📋 Content type: {request.content_type}")
        logger.info(f"📋 Request data keys: {list(request.data.keys())}")
        logger.info(f"📋 Request FILES keys: {list(request.FILES.keys())}")
        
        # Handle multipart form data preprocessing
        data = request.data.copy()
        
        # Handle boolean fields FIRST - convert string "true"/"false" to actual booleans
        boolean_fields = ['is_verified', 'is_active']
        for field in boolean_fields:
            if field in data:
                value = data[field]
                logger.info(f"🔧 Processing boolean field '{field}': type={type(value)}, value='{value}'")
                
                if isinstance(value, str):
                    # Handle various string formats
                    clean_value = value.strip().lower()
                    logger.info(f"  🔧 String value: '{value}' -> clean: '{clean_value}'")
                    
                    if clean_value in ['true', '1', 'yes', 'on']:
                        data[field] = True
                        logger.info(f"  ✅ Converted to True")
                    elif clean_value in ['false', '0', 'no', 'off']:
                        data[field] = False
                        logger.info(f"  ✅ Converted to False")
                    else:
                        # Try to evaluate string representations like "[True]"
                        logger.info(f"  🔧 Attempting ast.literal_eval for '{value}'")
                        try:
                            import ast
                            evaluated = ast.literal_eval(value)
                            logger.info(f"  🔧 ast.literal_eval result: {evaluated} (type: {type(evaluated)})")
                            
                            if isinstance(evaluated, bool):
                                data[field] = evaluated
                                logger.info(f"  ✅ Converted to {evaluated}")
                            elif isinstance(evaluated, (list, tuple)) and len(evaluated) == 1:
                                data[field] = bool(evaluated[0])
                                logger.info(f"  ✅ Converted list/tuple to {data[field]}")
                            else:
                                data[field] = bool(evaluated)
                                logger.info(f"  ✅ Converted other type to {data[field]}")
                        except (ValueError, SyntaxError) as e:
                            # If all else fails, default to False
                            data[field] = False
                            logger.warning(f"  ⚠️ ast.literal_eval failed: {e}, defaulting to False")
                elif isinstance(value, (list, tuple)) and len(value) == 1:
                    # Handle list/tuple with single value
                    single_value = value[0]
                    logger.info(f"  🔧 List/tuple value: {value} -> single: {single_value}")
                    if isinstance(single_value, str):
                        data[field] = single_value.lower() in ['true', '1', 'yes', 'on']
                        logger.info(f"  ✅ Converted list string to {data[field]}")
                    else:
                        data[field] = bool(single_value)
                        logger.info(f"  ✅ Converted list non-string to {data[field]}")
                elif isinstance(value, bool):
                    # Already a boolean, keep as is
                    data[field] = value
                    logger.info(f"  ✅ Already boolean: {value}")
                else:
                    # Convert to boolean
                    data[field] = bool(value)
                    logger.info(f"  ✅ Converted other type to {data[field]}")
        
        # Special handling for profile_picture
        if 'profile_picture' in request.FILES:
            profile_picture = request.FILES['profile_picture']
            logger.debug(f"Profile picture from FILES: {type(profile_picture)} - {profile_picture}")
            data['profile_picture'] = profile_picture
        elif 'profile_picture' in request.data:
            # Handle case where profile_picture is in data but not FILES
            pp_value = request.data['profile_picture']
            logger.debug(f"Profile picture from data: {type(pp_value)} - {pp_value}")
            if isinstance(pp_value, (list, tuple)):
                if len(pp_value) == 1:
                    data['profile_picture'] = pp_value[0]
                elif len(pp_value) == 0:
                    data['profile_picture'] = None
                else:
                    logger.error(f"Multiple profile pictures detected: {len(pp_value)}")
            elif isinstance(pp_value, str) and pp_value.strip() == "":
                data['profile_picture'] = None
        
        # Handle services field - they might come as multiple values
        if 'services' in data:
            services_data = data.getlist('services') if hasattr(data, 'getlist') else data.get('services')
            if services_data:
                if not isinstance(services_data, (list, tuple)):
                    services_data = [services_data]
                # Convert string IDs to integers and get the actual Service objects
                try:
                    from services.models import Service
                    service_ids = [int(sid) for sid in services_data if sid]
                    services_objects = Service.objects.filter(id__in=service_ids, is_active=True)
                    if len(services_objects) != len(service_ids):
                        missing_ids = set(service_ids) - set(services_objects.values_list('id', flat=True))
                        logger.warning(f"Some service IDs not found: {missing_ids}")
                    data['services'] = service_ids
                    logger.debug(f"Processed services: {service_ids}")
                except (ValueError, TypeError) as e:
                    logger.error(f"Error processing services: {e}")
                    return Response({
                        'error': 'Invalid service IDs provided',
                        'details': str(e)
                    }, status=status.HTTP_400_BAD_REQUEST)
        
        # Handle regions field - similar to services
        if 'regions' in data:
            regions_data = data.getlist('regions') if hasattr(data, 'getlist') else data.get('regions')
            if regions_data:
                if not isinstance(regions_data, (list, tuple)):
                    regions_data = [regions_data]
                # Convert string IDs to integers and get the actual Region objects
                try:
                    from regions.models import Region
                    region_ids = [int(rid) for rid in regions_data if rid]
                    regions_objects = Region.objects.filter(id__in=region_ids, is_active=True)
                    if len(regions_objects) != len(region_ids):
                        missing_ids = set(region_ids) - set(regions_objects.values_list('id', flat=True))
                        logger.warning(f"Some region IDs not found: {missing_ids}")
                    data['regions'] = region_ids
                    logger.debug(f"Processed regions: {region_ids}")
                except (ValueError, TypeError) as e:
                    logger.error(f"Error processing regions: {e}")
                    return Response({
                        'error': 'Invalid region IDs provided',
                        'details': str(e)
                    }, status=status.HTTP_400_BAD_REQUEST)
        
        # Convert multipart form data to proper format for serializer
        availability_data = []
        i = 0
        
        while f'availability[{i}][region_id]' in data:
            # Convert multipart form data to proper structure
            availability_item = {
                'region_id': data.get(f'availability[{i}][region_id]'),
                'weekday': data.get(f'availability[{i}][weekday]'),
                'start_time': data.get(f'availability[{i}][start_time]'),
                'end_time': data.get(f'availability[{i}][end_time]'),
                'break_start': data.get(f'availability[{i}][break_start]') or None,
                'break_end': data.get(f'availability[{i}][break_end]') or None,
                'is_active': data.get(f'availability[{i}][is_active]', 'true')
            }
            availability_data.append(availability_item)
            i += 1
        
        if availability_data:
            data['availability'] = availability_data
            logger.debug(f"Converted {len(availability_data)} availability items for serializer")
            logger.debug(f"Final availability data structure: {availability_data}")
        
        # Convert QueryDict to regular dict to avoid nested list issues
        clean_data = {}
        for key, value in data.items():
            if key in ['regions', 'services', 'availability'] and isinstance(value, list):
                # Ensure these are flat lists of IDs/objects
                clean_data[key] = value
            else:
                clean_data[key] = value[0] if isinstance(value, list) and len(value) == 1 else value
        
        # Continue with serializer processing
        try:
            logger.debug(f"🔍 About to create serializer with data keys: {list(clean_data.keys())}")
            logger.debug(f"🔍 Clean data structure: {clean_data}")
            
            serializer = self.get_serializer(data=clean_data)
            
            logger.debug(f"🔍 Serializer created, checking validity...")
            is_valid = serializer.is_valid()
            logger.debug(f"🔍 Serializer is_valid: {is_valid}")
            
            if not is_valid:
                logger.error(f"❌ Serializer validation errors: {serializer.errors}")
                return Response({
                    'error': 'Failed to create professional',
                    'details': serializer.errors
                }, status=status.HTTP_400_BAD_REQUEST)
            
            logger.debug(f"🔍 Serializer is valid, performing create...")
            self.perform_create(serializer)
            
            # Get created instance
            professional = serializer.instance
            detail_serializer = AdminProfessionalDetailSerializer(professional)
            
            # Create admin activity log
            AdminActivity.objects.create(
                admin_user=request.user,
                activity_type='professional_verification',
                description=f"Created professional: {data.get('email', 'Unknown')}",
                target_model='Professional',
                target_id=str(professional.id)
            )
            
            logger.info(f"✅ Successfully created professional {professional.id}")
            return Response(detail_serializer.data, status=status.HTTP_201_CREATED)
            
        except serializers.ValidationError as e:
            logger.error(f"❌ Serializer validation error: {e.detail}")
            return Response({
                'error': 'Failed to create professional',
                'details': e.detail
            }, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(f"💥 Unexpected error during creation: {str(e)}")
            logger.error(f"Error type: {type(e).__name__}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            return Response({
                'error': 'Failed to create professional',
                'details': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)





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
    
    def get_serializer_context(self):
        """
        Add request to serializer context for PUT/PATCH validation
        """
        context = super().get_serializer_context()
        context['request'] = self.request
        return context
    
    def perform_destroy(self, instance):
        """
        Smart deletion logic:
        - If professional works in multiple regions: Remove from current region only
        - If professional works in only one region: Delete professional + user completely
        """
        import logging
        logger = logging.getLogger(__name__)
        
        # Get the region to remove from (from query params or request)
        region_id = self.request.query_params.get('region_id')
        if region_id:
            try:
                region = Region.objects.get(id=region_id)
            except Region.DoesNotExist:
                logger.error(f"Region {region_id} not found for professional deletion")
                raise ValidationError(f"Region {region_id} not found")
        else:
            # If no region specified, use the first region
            regions = instance.regions.all()
            if not regions.exists():
                logger.error(f"Professional {instance.id} has no regions assigned")
                raise ValidationError("Professional has no regions assigned")
            region = regions.first()
        
        # Check how many regions this professional works in
        total_regions = instance.regions.count()
        
        if total_regions > 1:
            # Professional works in multiple regions - remove from current region only
            logger.info(f"Removing professional {instance.id} from region {region.id} (works in {total_regions} regions)")
            
            # Remove from the specified region
            instance.regions.remove(region)
            
            # Remove ProfessionalService entries for this region
            instance.professionalservice_set.filter(region=region).delete()
            
            # Remove availability entries for this region
            instance.availability_schedule.filter(region=region).delete()
            
            # Update user's current region if it was the deleted region
            if instance.user.current_region == region:
                remaining_regions = instance.regions.all()
                if remaining_regions.exists():
                    instance.user.current_region = remaining_regions.first()
                    instance.user.save()
                else:
                    instance.user.current_region = None
                    instance.user.save()
            
            logger.info(f"Successfully removed professional {instance.id} from region {region.id}")
            
        else:
            # Professional works in only one region - delete completely
            logger.info(f"Deleting professional {instance.id} completely (works in only {total_regions} region)")
            
            # Delete the user (this will cascade to professional and related data)
            user = instance.user
            user.delete()
            
            logger.info(f"Successfully deleted professional {instance.id} and user {user.id}")
    
    def update(self, request, *args, **kwargs):
        """
        Enhanced update method with proper multipart form data handling
        """
        import logging
        import traceback
        
        logger = logging.getLogger(__name__)
        logger.debug(f"Updating professional {kwargs.get('pk')}")
        
        try:
            # Get the instance
            instance = self.get_object()
            
            # Log incoming request data for debugging
            logger.debug(f"Request content type: {request.content_type}")
            logger.debug(f"Request data keys: {list(request.data.keys())}")
            logger.debug(f"Request files keys: {list(request.FILES.keys())}")
            
            # Handle multipart form data preprocessing
            data = request.data.copy()
            
            # Handle boolean fields FIRST - convert string "true"/"false" to actual booleans
            boolean_fields = ['is_verified', 'is_active', 'user_is_active']
            for field in boolean_fields:
                if field in data:
                    value = data[field]
                    logger.debug(f"Processing boolean field {field}: {value} (type: {type(value)})")
                    
                    # Handle list format like ['true']
                    if isinstance(value, (list, tuple)):
                        if len(value) == 1:
                            value = value[0]
                        elif len(value) == 0:
                            data[field] = False
                            continue
                        else:
                            logger.warning(f"Multiple values for boolean field {field}: {value}")
                            value = value[0]  # Take first value
                    
                    # Now handle the actual value
                    if isinstance(value, str):
                        clean_value = value.strip().lower()
                        if clean_value in ['true', '1', 'yes', 'on']:
                            data[field] = True
                        elif clean_value in ['false', '0', 'no', 'off', '']:
                            data[field] = False
                        else:
                            # Try to evaluate string representations
                            try:
                                import ast
                                evaluated = ast.literal_eval(value)
                                data[field] = bool(evaluated)
                            except (ValueError, SyntaxError):
                                data[field] = False
                    elif isinstance(value, bool):
                        data[field] = value
                    else:
                        data[field] = bool(value)
                    
                    logger.debug(f"✅ Converted {field}: {data[field]} (type: {type(data[field])})")
            
            # Handle numeric fields
            numeric_fields = ['experience_years', 'travel_radius_km', 'min_booking_notice_hours', 'commission_rate']
            for field in numeric_fields:
                if field in data:
                    value = data[field]
                    if isinstance(value, (list, tuple)) and len(value) == 1:
                        value = value[0]
                    
                    if isinstance(value, str):
                        try:
                            if field == 'commission_rate':
                                data[field] = float(value)
                            else:
                                data[field] = int(value)
                        except ValueError:
                            logger.warning(f"Invalid numeric value for {field}: {value}")
            
            # Handle profile_picture
            if 'profile_picture' in request.FILES:
                data['profile_picture'] = request.FILES['profile_picture']
            elif 'profile_picture' in data:
                pp_value = data['profile_picture']
                if isinstance(pp_value, (list, tuple)):
                    if len(pp_value) == 1:
                        data['profile_picture'] = pp_value[0]
                    elif len(pp_value) == 0:
                        data['profile_picture'] = None
                elif isinstance(pp_value, str) and pp_value.strip() == "":
                    data['profile_picture'] = None
            
            # Handle services and regions - convert to proper format
            for field_name in ['services', 'regions']:
                if field_name in data:
                    field_data = data.getlist(field_name) if hasattr(data, 'getlist') else data.get(field_name)
                    
                    # Handle the case where it comes as 'services[]' or 'regions[]'
                    array_key = f'{field_name}[]'
                    if array_key in data:
                        field_data = data.getlist(array_key) if hasattr(data, 'getlist') else data.get(array_key)
                    
                    if field_data:
                        if not isinstance(field_data, (list, tuple)):
                            field_data = [field_data]
                        
                        try:
                            if field_name == 'services':
                                from services.models import Service
                                service_ids = [int(sid) for sid in field_data if sid]
                                objects = Service.objects.filter(id__in=service_ids, is_active=True)
                            else:  # regions
                                from regions.models import Region
                                region_ids = [int(rid) for rid in field_data if rid]
                                objects = Region.objects.filter(id__in=region_ids, is_active=True)
                            
                            data[field_name] = service_ids if field_name == 'services' else region_ids
                            logger.debug(f"Processed {field_name}: {service_ids if field_name == 'services' else region_ids}")
                            logger.debug(f"Data type for {field_name}: {type(data[field_name])}")
                            logger.debug(f"Data content for {field_name}: {data[field_name]}")
                        except (ValueError, TypeError) as e:
                            logger.error(f"Error processing {field_name}: {e}")
                            return Response({
                                'error': f'Invalid {field_name[:-1]} IDs provided',
                                'details': str(e)
                            }, status=status.HTTP_400_BAD_REQUEST)
            
            # Handle availability data with better error handling
            availability_data = []
            i = 0
            
            logger.debug(f"🔍 Checking for availability data in request.data keys: {list(data.keys())}")
            logger.debug(f"🔍 Looking for availability[{i}][region_id] in data")
            
            # Check if we have any availability data at all
            has_availability_data = any(key.startswith('availability[') for key in data.keys())
            logger.debug(f"🔍 Has availability data: {has_availability_data}")
            
            if has_availability_data:
                while f'availability[{i}][region_id]' in data:
                    try:
                        # Extract all fields for this availability item
                        availability_fields = {}
                        required_fields = ['region_id', 'weekday', 'start_time', 'end_time']
                        optional_fields = ['break_start', 'break_end', 'is_active']
                        
                        # Get required fields
                        for field in required_fields:
                            key = f'availability[{i}][{field}]'
                            if key not in data:
                                logger.error(f"Missing required field {field} for availability item {i}")
                                return Response({
                                    'error': f'Missing required field {field} for availability item {i}',
                                    'details': f'Key {key} not found in request data'
                                }, status=status.HTTP_400_BAD_REQUEST)
                            availability_fields[field] = data[key]
                        
                        # Get optional fields
                        for field in optional_fields:
                            key = f'availability[{i}][{field}]'
                            availability_fields[field] = data.get(key, None)
                        
                        # Process the fields
                        region_id = int(availability_fields['region_id'])
                        weekday = int(availability_fields['weekday'])
                        
                        # Process time fields
                        from datetime import datetime
                        
                        def parse_time(time_str):
                            if not time_str or time_str.strip() == '':
                                return None
                            try:
                                return datetime.strptime(time_str, '%H:%M').time()
                            except ValueError:
                                try:
                                    return datetime.strptime(time_str, '%H:%M:%S').time()
                                except ValueError:
                                    return None
                        
                        start_time = parse_time(availability_fields['start_time'])
                        end_time = parse_time(availability_fields['end_time'])
                        break_start = parse_time(availability_fields.get('break_start')) if availability_fields.get('break_start') else None
                        break_end = parse_time(availability_fields.get('break_end')) if availability_fields.get('break_end') else None
                        
                        if not start_time or not end_time:
                            return Response({
                                'error': f'Invalid time format for availability item {i}',
                                'details': f'start_time: {availability_fields["start_time"]}, end_time: {availability_fields["end_time"]}'
                            }, status=status.HTTP_400_BAD_REQUEST)
                        
                        # Validate time logic
                        if end_time <= start_time:
                            return Response({
                                'error': f'End time must be after start time for availability item {i}',
                                'details': f'Start: {start_time}, End: {end_time}'
                            }, status=status.HTTP_400_BAD_REQUEST)
                        
                        # Handle is_active
                        is_active_str = availability_fields.get('is_active', 'true')
                        if isinstance(is_active_str, str):
                            is_active = is_active_str.lower() in ['true', '1', 'yes', 'on']
                        else:
                            is_active = bool(is_active_str)
                        
                        availability_item = {
                            'region_id': region_id,
                            'weekday': weekday,
                            'start_time': start_time,
                            'end_time': end_time,
                            'break_start': break_start,
                            'break_end': break_end,
                            'is_active': is_active
                        }
                        
                        availability_data.append(availability_item)
                        logger.debug(f"Added availability item {i}: {availability_item}")
                        
                    except (ValueError, TypeError, KeyError) as e:
                        logger.error(f"Error processing availability item {i}: {e}")
                        return Response({
                            'error': f'Invalid availability data for item {i}',
                            'details': str(e)
                        }, status=status.HTTP_400_BAD_REQUEST)
                    
                    i += 1
            else:
                logger.debug("No availability data found in form_data")
            
            if availability_data:
                data['availability'] = availability_data
                logger.debug(f"Processed {len(availability_data)} availability items")
            
            # Create and validate serializer
            logger.debug(f"🔍 Data type being passed to serializer: {type(data)}")
            logger.debug(f"🔍 Data content being passed to serializer: {data}")
            logger.debug(f"🔍 Regions data type: {type(data.get('regions'))}")
            logger.debug(f"🔍 Regions data content: {data.get('regions')}")
            logger.debug(f"🔍 Services data type: {type(data.get('services'))}")
            logger.debug(f"🔍 Services data content: {data.get('services')}")
            
            # Convert QueryDict to regular dict to avoid double-list issues
            if hasattr(data, 'dict'):
                data_dict = data.dict()
            else:
                data_dict = dict(data)
            
            # Fix any double-list issues for regions and services
            if 'regions' in data_dict and isinstance(data_dict['regions'], list):
                if data_dict['regions'] and isinstance(data_dict['regions'][0], list):
                    data_dict['regions'] = data_dict['regions'][0]
            
            if 'services' in data_dict and isinstance(data_dict['services'], list):
                if data_dict['services'] and isinstance(data_dict['services'][0], list):
                    data_dict['services'] = data_dict['services'][0]
            
            logger.debug(f"🔍 Fixed data content: {data_dict}")
            
            serializer = self.get_serializer(instance, data=data_dict, partial=True)
            
            logger.debug(f"🔍 Serializer created with data keys: {list(data_dict.keys())}")
            
            if not serializer.is_valid():
                logger.error(f"❌ Serializer validation errors: {serializer.errors}")
                return Response({
                    'error': 'Failed to update professional',
                    'details': serializer.errors
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Save the updated instance
            self.perform_update(serializer)
            
            # Get updated instance and return detailed response
            professional = serializer.instance
            detail_serializer = AdminProfessionalDetailSerializer(professional)
            
            # Log admin activity
            AdminActivity.objects.create(
                admin_user=request.user,
                activity_type='professional_verification',
                description=f"Updated professional: {professional.user.email}",
                target_model='Professional',
                target_id=str(professional.id)
            )
            
            logger.info(f"✅ Successfully updated professional {professional.id}")
            return Response(detail_serializer.data, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(f"💥 Unexpected error in update method: {str(e)}")
            logger.error(f"Error type: {type(e).__name__}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            return Response({
                'error': 'Failed to update professional',
                'details': str(e),
                'type': type(e).__name__
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

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


# ===================== CATEGORY MANAGEMENT VIEWS =====================

class AdminCategoryListView(generics.ListCreateAPIView):
    """
    List and create categories (admin)
    """
    permission_classes = [IsAdminUser]
    serializer_class = AdminCategorySerializer
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['region', 'is_active', 'is_featured']
    search_fields = ['name', 'description']
    ordering_fields = ['name', 'created_at', 'services_count']
    ordering = ['name']
    
    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False):
            return Category.objects.none()
        return Category.objects.select_related('region').prefetch_related('services').all()


class AdminCategoryDetailView(generics.RetrieveUpdateDestroyAPIView):
    """
    Get, update, or delete category (admin)
    """
    permission_classes = [IsAdminUser]
    serializer_class = AdminCategorySerializer
    queryset = Category.objects.select_related('region').prefetch_related('services', 'addons')
    
    def perform_destroy(self, instance):
        # Check if category has services
        if instance.services.exists():
            raise serializers.ValidationError("Cannot delete category with existing services")
        instance.delete()


# ===================== SERVICE MANAGEMENT VIEWS =====================

class AdminServiceListView(generics.ListCreateAPIView):
    """
    List and create services (admin)
    """
    permission_classes = [IsAdminUser]
    serializer_class = AdminServiceSerializer
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['category', 'category__region', 'is_active', 'is_featured']
    search_fields = ['name', 'description']
    ordering_fields = ['name', 'created_at', 'professionals_count', 'bookings_count']
    ordering = ['name']
    
    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False):
            return Service.objects.none()
        return Service.objects.select_related('category', 'category__region').all()


class AdminServiceDetailView(generics.RetrieveUpdateDestroyAPIView):
    """
    Get, update, or delete service (admin)
    """
    permission_classes = [IsAdminUser]
    serializer_class = AdminServiceSerializer
    queryset = Service.objects.select_related('category', 'category__region')


# ===================== REGIONAL PRICING MANAGEMENT VIEWS =====================

class AdminRegionalPricingListView(generics.ListCreateAPIView):
    """
    List and create regional pricing (admin)
    """
    permission_classes = [IsAdminUser]
    serializer_class = AdminRegionalPricingSerializer
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['service', 'region', 'service__category']
    search_fields = ['service__name', 'region__name']
    ordering_fields = ['service__name', 'region__name', 'price']
    ordering = ['service__name', 'region__name']
    
    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False):
            return RegionalPricing.objects.none()
        return RegionalPricing.objects.select_related('service', 'service__category', 'region').all()


class AdminRegionalPricingDetailView(generics.RetrieveUpdateDestroyAPIView):
    """
    Get, update, or delete regional pricing (admin)
    """
    permission_classes = [IsAdminUser]
    serializer_class = AdminRegionalPricingSerializer
    queryset = RegionalPricing.objects.select_related('service', 'service__category', 'region')


# ===================== ADDON MANAGEMENT VIEWS =====================

class AdminAddOnListView(generics.ListCreateAPIView):
    """
    List and create addons (admin)
    """
    permission_classes = [IsAdminUser]
    serializer_class = AdminAddOnSerializer
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['region', 'is_active']
    search_fields = ['name', 'description']
    ordering_fields = ['name', 'price', 'created_at']
    ordering = ['name']
    
    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False):
            return AddOn.objects.none()
        return AddOn.objects.select_related('region').prefetch_related('categories').all()


class AdminAddOnDetailView(generics.RetrieveUpdateDestroyAPIView):
    """
    Get, update, or delete addon (admin)
    """
    permission_classes = [IsAdminUser]
    serializer_class = AdminAddOnSerializer
    queryset = AddOn.objects.select_related('region').prefetch_related('categories')


# ===================== BOOKING MANAGEMENT VIEWS =====================

class AdminBookingListView(generics.ListCreateAPIView):
    """
    List and create bookings (admin)
    """
    permission_classes = [IsAdminUser]
    serializer_class = AdminBookingSerializer
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['status', 'payment_status', 'region', 'service', 'professional']
    search_fields = ['booking_id', 'customer__first_name', 'customer__last_name', 'customer__email']
    ordering_fields = ['created_at', 'scheduled_date', 'total_amount']
    ordering = ['-created_at']
    
    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False):
            return Booking.objects.none()
        
        # Get base queryset
        queryset = Booking.objects.select_related(
            'customer', 'professional', 'professional__user', 'service', 'region'
        ).prefetch_related('selected_addons', 'review', 'reschedule_requests', 'messages')
        
        # Filter out cancelled bookings by default unless explicitly requested
        include_cancelled = self.request.query_params.get('include_cancelled', 'false').lower() == 'true'
        if not include_cancelled:
            queryset = queryset.exclude(status='cancelled')
        
        return queryset
    
    def get_serializer_class(self):
        """Use different serializers for different operations"""
        if self.request.method == 'POST':
            return AdminBookingCreateSerializer
        return AdminBookingSerializer
    
    def create(self, request, *args, **kwargs):
        """Handle booking creation with form_data support"""
        import logging
        logger = logging.getLogger(__name__)
        
        logger.debug(f"🔍 AdminBookingListView.create called")
        logger.debug(f"🔍 Request method: {request.method}")
        logger.debug(f"🔍 Content type: {request.content_type}")
        logger.debug(f"🔍 Data keys: {list(request.data.keys())}")
        
        # Handle form_data preprocessing
        data = request.data.copy()
        
        # Handle selected_addons field
        if 'selected_addons' in data:
            addons_data = data.getlist('selected_addons') if hasattr(data, 'getlist') else data.get('selected_addons')
            logger.debug(f"🔍 Raw selected_addons data: {addons_data} (type: {type(addons_data)})")
            if addons_data:
                if not isinstance(addons_data, (list, tuple)):
                    addons_data = [addons_data]
                try:
                    # Flatten the list if it's nested
                    if addons_data and isinstance(addons_data[0], (list, tuple)):
                        addons_data = addons_data[0]
                    
                    # Handle APIClient format conversion (dictionary with numeric keys)
                    if isinstance(addons_data, dict):
                        addons_data = list(addons_data.values())
                    
                    logger.debug(f"🔍 Processed addons_data: {addons_data} (type: {type(addons_data)})")
                    addon_ids = [int(addon_id) for addon_id in addons_data if addon_id]
                    # For many=True fields, we need to pass the list directly
                    data['selected_addons'] = addon_ids
                    logger.debug(f"Processed selected_addons: {addon_ids}")
                except (ValueError, TypeError) as e:
                    logger.error(f"Error processing selected_addons: {e}")
                    return Response({
                        'error': 'Invalid addon IDs provided',
                        'details': str(e)
                    }, status=status.HTTP_400_BAD_REQUEST)
        
        # Handle boolean fields
        boolean_fields = ['booking_for_self', 'deposit_required']
        for field in boolean_fields:
            if field in data:
                value = data.get(field)
                if isinstance(value, str):
                    data[field] = value.lower() in ['true', '1', 'yes', 'on']
        
        # Handle numeric fields
        numeric_fields = ['base_amount', 'addon_amount', 'discount_amount', 'tax_amount', 'total_amount', 'deposit_percentage', 'deposit_amount', 'duration_minutes']
        for field in numeric_fields:
            if field in data:
                try:
                    data[field] = float(data.get(field)) if data.get(field) else 0.0
                except (ValueError, TypeError):
                    data[field] = 0.0
        
        # Create and validate serializer
        serializer = self.get_serializer(data=data)
        if serializer.is_valid():
            booking = serializer.save()
            logger.info(f"✅ Successfully created booking {booking.booking_id}")
            
            # Use AdminBookingSerializer for the response
            response_serializer = AdminBookingSerializer(booking, context=self.get_serializer_context())
            return Response(response_serializer.data, status=status.HTTP_201_CREATED)
        else:
            logger.error(f"❌ Booking creation failed: {serializer.errors}")
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class AdminBookingDetailView(generics.RetrieveUpdateDestroyAPIView):
    """
    Get, update, or delete booking (admin)
    """
    permission_classes = [IsAdminUser]
    lookup_field = 'booking_id'
    queryset = Booking.objects.select_related(
        'customer', 'professional', 'professional__user', 'service', 'region'
    ).prefetch_related('selected_addons', 'review', 'reschedule_requests', 'messages')
    
    def get_serializer_class(self):
        """Use different serializers for different operations"""
        if self.request.method in ['PUT', 'PATCH']:
            return AdminBookingUpdateSerializer
        return AdminBookingSerializer
    
    def perform_destroy(self, instance):
        """
        Soft delete booking by marking it as cancelled
        """
        import logging
        logger = logging.getLogger(__name__)
        
        # Log the deletion attempt
        from admin_panel.models import AdminActivity
        AdminActivity.objects.create(
            admin_user=self.request.user,
            activity_type='booking_action',
            description=f"Admin deleted booking: {instance.booking_id}",
            target_model='Booking',
            target_id=str(instance.booking_id)
        )
        
        # Store previous status before changing
        previous_status = instance.status
        
        # Mark booking as cancelled instead of hard delete
        instance.status = 'cancelled'
        instance.cancelled_by = self.request.user
        instance.cancelled_at = timezone.now()
        instance.cancellation_reason = 'Deleted by admin'
        instance.save()
        
        # Create status history
        from bookings.models import BookingStatusHistory
        BookingStatusHistory.objects.create(
            booking=instance,
            previous_status=previous_status,
            new_status='cancelled',
            changed_by=self.request.user,
            reason='Deleted by admin'
        )
        
        logger.info(f"Admin {self.request.user.email} soft-deleted booking {instance.booking_id}")
    
    def update(self, request, *args, **kwargs):
        """Handle booking update with form_data support"""
        import logging
        logger = logging.getLogger(__name__)
        
        logger.debug(f"🔍 AdminBookingDetailView.update called")
        logger.debug(f"🔍 Request method: {request.method}")
        logger.debug(f"🔍 Content type: {request.content_type}")
        logger.debug(f"🔍 Data keys: {list(request.data.keys())}")
        
        # Handle form_data preprocessing
        data = request.data.copy()
        
        # Handle selected_addons field
        if 'selected_addons' in data:
            addons_data = data.getlist('selected_addons') if hasattr(data, 'getlist') else data.get('selected_addons')
            logger.debug(f"🔍 Raw selected_addons data: {addons_data} (type: {type(addons_data)})")
            if addons_data:
                if not isinstance(addons_data, (list, tuple)):
                    addons_data = [addons_data]
                try:
                    # Flatten the list if it's nested
                    if addons_data and isinstance(addons_data[0], (list, tuple)):
                        addons_data = addons_data[0]
                    
                    # Handle APIClient format conversion (dictionary with numeric keys)
                    if isinstance(addons_data, dict):
                        addons_data = list(addons_data.values())
                    
                    logger.debug(f"🔍 Processed addons_data: {addons_data} (type: {type(addons_data)})")
                    addon_ids = [int(addon_id) for addon_id in addons_data if addon_id]
                    # For many=True fields, we need to pass the list directly
                    data['selected_addons'] = addon_ids
                    logger.debug(f"Processed selected_addons: {addon_ids}")
                except (ValueError, TypeError) as e:
                    logger.error(f"Error processing selected_addons: {e}")
                    return Response({
                        'error': 'Invalid addon IDs provided',
                        'details': str(e)
                    }, status=status.HTTP_400_BAD_REQUEST)
        
        # Handle boolean fields
        boolean_fields = ['booking_for_self', 'deposit_required']
        for field in boolean_fields:
            if field in data:
                value = data.get(field)
                if isinstance(value, str):
                    data[field] = value.lower() in ['true', '1', 'yes', 'on']
        
        # Handle numeric fields
        numeric_fields = ['base_amount', 'addon_amount', 'discount_amount', 'tax_amount', 'total_amount', 'deposit_percentage', 'deposit_amount', 'duration_minutes']
        for field in numeric_fields:
            if field in data:
                try:
                    data[field] = float(data.get(field)) if data.get(field) else 0.0
                except (ValueError, TypeError):
                    data[field] = 0.0
        
        # Convert QueryDict to regular dict to avoid double-list issues
        if hasattr(data, 'dict'):
            data_dict = data.dict()
        else:
            data_dict = dict(data)
        
        # Fix any double-list issues for selected_addons
        if 'selected_addons' in data_dict and isinstance(data_dict['selected_addons'], list):
            if len(data_dict['selected_addons']) == 1 and isinstance(data_dict['selected_addons'][0], list):
                data_dict['selected_addons'] = data_dict['selected_addons'][0]
        
        logger.debug(f"🔍 Data type being passed to serializer: {type(data_dict)}")
        logger.debug(f"🔍 Data content being passed to serializer: {data_dict}")
        
        # Create and validate serializer
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=data_dict, partial=True)
        if serializer.is_valid():
            booking = serializer.save()
            logger.info(f"✅ Successfully updated booking {booking.booking_id}")
            
            # Use AdminBookingSerializer for the response to avoid RelatedManager issues
            from admin_panel.serializers import AdminBookingSerializer
            response_serializer = AdminBookingSerializer(booking, context=self.get_serializer_context())
            return Response(response_serializer.data)
        else:
            logger.error(f"❌ Booking update failed: {serializer.errors}")
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# ===================== PAYMENT MANAGEMENT VIEWS =====================

class AdminPaymentListView(generics.ListAPIView):
    """
    List payments (admin)
    """
    permission_classes = [IsAdminUser]
    serializer_class = AdminPaymentSerializer
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['status', 'payment_type', 'booking__region']
    search_fields = ['payment_id', 'customer__first_name', 'customer__last_name', 'customer__email']
    ordering_fields = ['created_at', 'amount']
    ordering = ['-created_at']
    
    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False):
            return Payment.objects.none()
        return Payment.objects.select_related('customer', 'booking', 'booking__region').all()


class AdminPaymentDetailView(generics.RetrieveAPIView):
    """
    Get payment details (admin)
    """
    permission_classes = [IsAdminUser]
    serializer_class = AdminPaymentSerializer
    lookup_field = 'payment_id'
    queryset = Payment.objects.select_related('customer', 'booking', 'booking__region')


# ===================== REGION MANAGEMENT VIEWS =====================

class AdminRegionListView(generics.ListCreateAPIView):
    """
    List and create regions (admin)
    """
    permission_classes = [IsAdminUser]
    serializer_class = AdminRegionSerializer
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['is_active']
    search_fields = ['name', 'code', 'description']
    ordering_fields = ['name', 'code', 'created_at']
    ordering = ['name']
    
    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False):
            return Region.objects.none()
        return Region.objects.all()


class AdminRegionDetailView(generics.RetrieveUpdateDestroyAPIView):
    """
    Get, update, or delete region (admin)
    """
    permission_classes = [IsAdminUser]
    serializer_class = AdminRegionSerializer
    queryset = Region.objects.all()


class AdminRegionalSettingsView(generics.RetrieveUpdateAPIView):
    """
    Get and update regional settings (admin)
    """
    permission_classes = [IsAdminUser]
    serializer_class = AdminRegionalSettingsSerializer
    
    def get_object(self):
        region_id = self.kwargs.get('region_id')
        if region_id:
            return RegionalSettings.objects.get(region_id=region_id)
        return RegionalSettings.objects.first()


# ===================== REVIEW MODERATION VIEWS =====================

class AdminReviewListView(generics.ListAPIView):
    """
    List reviews for moderation (admin)
    """
    permission_classes = [IsAdminUser]
    serializer_class = AdminReviewModerationSerializer
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['rating', 'is_approved', 'professional', 'service']
    search_fields = ['customer__first_name', 'customer__last_name', 'professional__user__first_name']
    ordering_fields = ['created_at', 'rating']
    ordering = ['-created_at']
    
    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False):
            return Review.objects.none()
        return Review.objects.select_related(
            'customer', 'professional', 'professional__user', 'service'
        ).all()


# ===================== NOTIFICATION MANAGEMENT VIEWS =====================

class AdminNotificationListView(generics.ListAPIView):
    """
    List notifications (admin)
    """
    permission_classes = [IsAdminUser]
    serializer_class = AdminNotificationSerializer
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['notification_type', 'is_read', 'user']
    search_fields = ['title', 'message', 'user__first_name', 'user__last_name']
    ordering_fields = ['created_at']
    ordering = ['-created_at']
    
    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False):
            return Notification.objects.none()
        return Notification.objects.select_related('user').all()


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
    operation_description="Fix booking payment status (admin utility)",
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
    import logging
    import traceback
    
    logger = logging.getLogger(__name__)
    logger.debug(f"Test professional update called with data: {request.data}")
    
    try:
        # Test the serializer
        serializer = AdminProfessionalUpdateSerializer(data=request.data)
        logger.debug(f"Serializer created, checking validity...")
        
        if serializer.is_valid():
            logger.debug(f"Serializer is valid, validated data: {serializer.validated_data}")
            return Response({
                'message': 'Serializer is valid',
                'validated_data': serializer.validated_data
            })
        else:
            logger.error(f"Serializer validation failed: {serializer.errors}")
            return Response({
                'message': 'Serializer validation failed',
                'errors': serializer.errors
            }, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        logger.error(f"Error in test_professional_update: {str(e)}")
        logger.error(f"Full traceback:\n{traceback.format_exc()}")
        return Response({
            'error': str(e),
            'type': type(e).__name__,
            'traceback': traceback.format_exc().split('\n')
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAdminUser])
def debug_info(request):
    """
    Debug information endpoint
    """
    return Response({
        'message': 'Debug endpoint working',
        'user': request.user.username if request.user.is_authenticated else 'Anonymous',
        'timestamp': timezone.now().isoformat()
    })


# ===================== BOOKING PICTURE UPLOAD =====================

@api_view(['POST'])
@permission_classes([IsAdminUser])
@swagger_auto_schema(
    operation_description="Upload booking pictures (admin only)",
    request_body=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        required=['booking_id', 'picture_type', 'images'],
        properties={
            'booking_id': openapi.Schema(type=openapi.TYPE_STRING, format='uuid', description='Booking UUID'),
            'picture_type': openapi.Schema(type=openapi.TYPE_STRING, enum=['before', 'after'], description='Type of picture'),
            'images': openapi.Schema(type=openapi.TYPE_ARRAY, items=openapi.Schema(type=openapi.TYPE_FILE), description='Image files (1-6 files)'),
            'captions': openapi.Schema(type=openapi.TYPE_ARRAY, items=openapi.Schema(type=openapi.TYPE_STRING), description='Optional captions for images'),
        }
    ),
    responses={
        200: 'Pictures uploaded successfully',
        400: 'Validation error',
        404: 'Booking not found'
    }
)
def upload_booking_pictures(request):
    """
    Upload before/after pictures for a booking (admin only)
    """
    import logging
    logger = logging.getLogger(__name__)
    
    try:
        # Get booking
        booking_id = request.data.get('booking_id')
        if not booking_id:
            return Response(
                {'error': 'booking_id is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            booking = Booking.objects.get(booking_id=booking_id)
        except Booking.DoesNotExist:
            return Response(
                {'error': 'Booking not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Get picture type
        picture_type = request.data.get('picture_type')
        if picture_type not in ['before', 'after']:
            return Response(
                {'error': 'picture_type must be "before" or "after"'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Get images from request
        images = request.FILES.getlist('images')
        if not images:
            return Response(
                {'error': 'At least one image is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if len(images) > 6:
            return Response(
                {'error': 'Maximum 6 images allowed per upload'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Check existing picture count
        existing_count = booking.pictures.filter(picture_type=picture_type).count()
        if existing_count + len(images) > 6:
            return Response(
                {'error': f'Maximum 6 {picture_type} pictures allowed. Currently have {existing_count}, trying to add {len(images)}'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Get captions if provided
        captions = request.data.getlist('captions') if 'captions' in request.data else []
        
        # Validate captions count matches images count
        if captions and len(captions) != len(images):
            return Response(
                {'error': 'Number of captions must match number of images'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Upload pictures
        uploaded_pictures = []
        from bookings.models import BookingPicture
        
        for i, image in enumerate(images):
            try:
                # Validate image
                if image.size > 10 * 1024 * 1024:  # 10MB limit
                    return Response(
                        {'error': f'Image {i+1} is too large. Maximum size is 10MB'},
                        status=status.HTTP_400_BAD_REQUEST
                    )
                
                # Create booking picture
                picture = BookingPicture.objects.create(
                    booking=booking,
                    picture_type=picture_type,
                    image=image,
                    caption=captions[i] if i < len(captions) else '',
                    uploaded_by=request.user
                )
                
                uploaded_pictures.append(picture)
                logger.info(f"Uploaded {picture_type} picture {i+1} for booking {booking_id}")
                
            except Exception as e:
                logger.error(f"Failed to upload image {i+1}: {str(e)}")
                return Response(
                    {'error': f'Failed to upload image {i+1}: {str(e)}'},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
        
        # Serialize uploaded pictures
        from bookings.serializers import BookingPictureSerializer
        serializer = BookingPictureSerializer(uploaded_pictures, many=True, context={'request': request})
        
        return Response({
            'message': f'Successfully uploaded {len(uploaded_pictures)} {picture_type} picture(s)',
            'uploaded_pictures': serializer.data,
            'booking_id': str(booking_id),
            'picture_type': picture_type
        })
        
    except Exception as e:
        logger.error(f"Upload booking pictures error: {str(e)}")
        return Response(
            {'error': 'Internal server error'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


# ===================== MISSING API FUNCTIONS =====================

@api_view(['POST'])
@permission_classes([IsAdminUser])
@swagger_auto_schema(
    operation_description="Update booking status (admin)",
    request_body=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        required=['booking_id', 'new_status'],
        properties={
            'booking_id': openapi.Schema(type=openapi.TYPE_STRING, format='uuid'),
            'new_status': openapi.Schema(type=openapi.TYPE_STRING, enum=['pending', 'confirmed', 'in_progress', 'completed', 'cancelled']),
            'admin_notes': openapi.Schema(type=openapi.TYPE_STRING),
        }
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
    
    if not booking_id or not new_status:
        return Response(
            {'error': 'booking_id and new_status are required'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    try:
        booking = Booking.objects.get(booking_id=booking_id)
        booking.status = new_status
        if admin_notes:
            booking.admin_notes = admin_notes
        booking.save()
        
        return Response({'message': f'Booking status updated to {new_status}'})
    except Booking.DoesNotExist:
        return Response(
            {'error': 'Booking not found'},
            status=status.HTTP_404_NOT_FOUND
        )


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
        payment.status = new_status
        if admin_notes:
            payment.admin_notes = admin_notes
        payment.save()
        
        return Response({'message': f'Payment status updated to {new_status}'})
    except Payment.DoesNotExist:
        return Response(
            {'error': 'Payment not found'},
            status=status.HTTP_404_NOT_FOUND
        )


@api_view(['POST'])
@permission_classes([IsAdminUser])
@swagger_auto_schema(
    operation_description="Moderate review (admin)",
    request_body=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        required=['review_id', 'action'],
        properties={
            'review_id': openapi.Schema(type=openapi.TYPE_INTEGER),
            'action': openapi.Schema(type=openapi.TYPE_STRING, enum=['approve', 'reject']),
            'admin_notes': openapi.Schema(type=openapi.TYPE_STRING),
        }
    ),
    responses={200: 'Review moderated'}
)
def moderate_review(request):
    """
    Moderate review by admin
    """
    review_id = request.data.get('review_id')
    action = request.data.get('action')
    admin_notes = request.data.get('admin_notes', '')
    
    if not review_id or not action:
        return Response(
            {'error': 'review_id and action are required'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    if action not in ['approve', 'reject']:
        return Response(
            {'error': 'action must be either "approve" or "reject"'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    try:
        review = Review.objects.get(id=review_id)
        review.is_approved = (action == 'approve')
        if admin_notes:
            review.admin_notes = admin_notes
        review.save()
        
        return Response({'message': f'Review {action}ed successfully'})
    except Review.DoesNotExist:
        return Response(
            {'error': 'Review not found'},
            status=status.HTTP_404_NOT_FOUND
        )


@api_view(['POST'])
@permission_classes([IsAdminUser])
@swagger_auto_schema(
    operation_description="Send broadcast notification (admin)",
    request_body=BroadcastNotificationSerializer,
    responses={200: 'Notification sent'}
)
def send_broadcast_notification(request):
    """
    Send broadcast notification by admin
    """
    serializer = BroadcastNotificationSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    target = serializer.validated_data['target']
    region = serializer.validated_data.get('region')
    title = serializer.validated_data['title']
    message = serializer.validated_data['message']
    send_push = serializer.validated_data.get('send_push', True)
    send_email = serializer.validated_data.get('send_email', False)
    
    # Determine target users based on target type
    if target == 'all':
        users = User.objects.filter(is_active=True)
    elif target == 'customers':
        users = User.objects.filter(user_type='customer', is_active=True)
    elif target == 'professionals':
        users = User.objects.filter(user_type='professional', is_active=True)
    elif target == 'region':
        if not region:
            return Response(
                {'error': 'region is required for region target'},
                status=status.HTTP_400_BAD_REQUEST
            )
        users = User.objects.filter(current_region=region, is_active=True)
    elif target == 'verified_professionals':
        users = User.objects.filter(
            user_type='professional',
            is_active=True,
            professional__is_verified=True
        )
    else:
        return Response(
            {'error': 'Invalid target type'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    # Create notifications for all target users
    notifications_created = 0
    for user in users:
        Notification.objects.create(
            user=user,
            title=title,
            message=message,
            notification_type='admin_broadcast',
            sender=request.user
        )
        notifications_created += 1
    
    return Response({
        'message': f'Broadcast notification sent to {notifications_created} users',
        'users_notified': notifications_created
    })


@api_view(['POST'])
@permission_classes([IsAdminUser])
@swagger_auto_schema(
    operation_description="Perform bulk operations (admin)",
    request_body=BulkOperationSerializer,
    responses={200: 'Bulk operation completed'}
)
def bulk_operations(request):
    """
    Perform bulk operations by admin
    """
    serializer = BulkOperationSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    ids = serializer.validated_data['ids']
    operation = serializer.validated_data['operation']
    reason = serializer.validated_data.get('reason', '')
    
    # Determine model based on operation
    if operation in ['activate', 'deactivate']:
        model = User
        field = 'is_active'
        value = (operation == 'activate')
    elif operation in ['verify', 'unverify']:
        model = Professional
        field = 'is_verified'
        value = (operation == 'verify')
    elif operation in ['feature', 'unfeature']:
        model = Service
        field = 'is_featured'
        value = (operation == 'feature')
    elif operation == 'delete':
        # Handle deletion separately
        try:
            # Try to delete from multiple models
            deleted_count = 0
            for model_class in [User, Professional, Service, Category]:
                deleted_count += model_class.objects.filter(id__in=ids).delete()[0]
            
            return Response({
                'message': f'Successfully deleted {deleted_count} items',
                'deleted_count': deleted_count
            })
        except Exception as e:
            return Response(
                {'error': f'Error during deletion: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    else:
        return Response(
            {'error': 'Invalid operation'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    # Perform bulk update
    try:
        updated_count = model.objects.filter(id__in=ids).update(**{field: value})
        
        return Response({
            'message': f'Successfully {operation}d {updated_count} items',
            'updated_count': updated_count
        })
    except Exception as e:
        return Response(
            {'error': f'Error during bulk operation: {str(e)}'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
