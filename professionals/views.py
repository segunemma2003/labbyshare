from rest_framework import generics, status, permissions
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from django.db.models import Q, Avg, Count, Prefetch
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import OrderingFilter, SearchFilter
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi
from django.utils import timezone
from datetime import datetime, timedelta
from decimal import Decimal

from .models import (
    Professional, ProfessionalAvailability, ProfessionalUnavailability,
    ProfessionalService, ProfessionalDocument
)
from .serializers import (
    ProfessionalListSerializer, ProfessionalDetailSerializer,
    ProfessionalRegistrationSerializer, AvailabilityCreateSerializer,
    UnavailabilitySerializer, ProfessionalDocumentSerializer,
    AvailabilitySlotSerializer, ProfessionalSearchSerializer,
    ProfessionalUpdateSerializer, ProfessionalAdminDetailSerializer
)
from .filters import ProfessionalFilter
from utils.permissions import IsVerifiedProfessional, IsOwnerOrReadOnly


class ProfessionalListView(generics.ListAPIView):
    """
    List and search professionals
    """
    serializer_class = ProfessionalListSerializer
    permission_classes = [permissions.AllowAny]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_class = ProfessionalFilter
    search_fields = ['user__first_name', 'user__last_name', 'bio']
    ordering_fields = ['rating', 'total_reviews', 'experience_years', 'created_at']
    ordering = ['-rating', '-total_reviews']
    
    @swagger_auto_schema(
        operation_description="Search and filter professionals",
        manual_parameters=[
            openapi.Parameter(
                'service_id', openapi.IN_QUERY,
                description="Filter by service ID",
                type=openapi.TYPE_INTEGER
            ),
            openapi.Parameter(
                'min_rating', openapi.IN_QUERY,
                description="Minimum rating filter",
                type=openapi.TYPE_NUMBER
            ),
            openapi.Parameter(
                'verified_only', openapi.IN_QUERY,
                description="Show only verified professionals",
                type=openapi.TYPE_BOOLEAN
            ),
        ],
        responses={200: ProfessionalListSerializer(many=True)}
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)
    
    def get_queryset(self):
        region = getattr(self.request, 'region', None)
        if not region:
            return Professional.objects.none()
        
        return Professional.objects.get_active_professionals(region).select_related(
            'user'
        ).prefetch_related('regions', 'services')


class ProfessionalDetailView(generics.RetrieveAPIView):
    """
    Get detailed professional information
    """
    serializer_class = ProfessionalDetailSerializer
    permission_classes = [permissions.AllowAny]
    lookup_field = 'id'
    
    @swagger_auto_schema(
        operation_description="Get detailed professional information",
        responses={200: ProfessionalDetailSerializer()}
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)
    
    def get_queryset(self):
        region = getattr(self.request, 'region', None)
        if not region:
            return Professional.objects.none()
        
        return Professional.objects.filter(
            is_active=True,
            regions=region
        ).select_related('user').prefetch_related(
            'regions',
            'services',
            'availability_schedule',
            'reviews_received'
        )
    
    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['region'] = getattr(self.request, 'region', None)
        return context


class ProfessionalRegistrationView(generics.CreateAPIView):
    """
    Register as a professional
    """
    serializer_class = ProfessionalRegistrationSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    @swagger_auto_schema(
        operation_description="Register as a professional",
        request_body=ProfessionalRegistrationSerializer,
        responses={201: ProfessionalDetailSerializer()}
    )
    def post(self, request, *args, **kwargs):
        # Check if user is already a professional
        if hasattr(request.user, 'professional_profile'):
            return Response(
                {'error': 'User is already registered as a professional'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        response = super().create(request, *args, **kwargs)
        
        if response.status_code == 201:
            # Update user type
            request.user.user_type = 'professional'
            request.user.save(update_fields=['user_type'])
        
        return response
    
    def perform_create(self, serializer):
        professional = serializer.save()
        
        # Send notification to admin for verification
        from notifications.tasks import send_admin_notification
        send_admin_notification.delay(
            'professional_registration',
            f"New professional registration: {professional.user.get_full_name()}",
            {'professional_id': professional.id}
        )


class ProfessionalProfileView(generics.RetrieveUpdateAPIView):
    """
    View and update professional profile
    """
    permission_classes = [IsVerifiedProfessional, IsOwnerOrReadOnly]
    
    def get_serializer_class(self):
        if self.request.method in ['PUT', 'PATCH']:
            return ProfessionalUpdateSerializer
        return ProfessionalDetailSerializer
    
    def get_object(self):
        # Handle schema generation with AnonymousUser
        if getattr(self, 'swagger_fake_view', False):
            return None
            
        if hasattr(self.request.user, 'professional_profile'):
            return self.request.user.professional_profile
        return None
    
    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['region'] = getattr(self.request, 'region', None)
        return context
    
    def update(self, request, *args, **kwargs):
        """Add debugging to see what's in the request"""
        import logging
        logger = logging.getLogger(__name__)
        logger.debug(f"Update method called with request method: {request.method}")
        logger.debug(f"Request content type: {request.content_type}")
        logger.debug(f"Request data type: {type(request.data)}")
        logger.debug(f"Request data keys: {list(request.data.keys()) if hasattr(request.data, 'keys') else 'No keys'}")
        if 'profile_picture' in request.data:
            logger.debug(f"profile_picture in request data type: {type(request.data['profile_picture'])}, value: {request.data['profile_picture']}")
        if hasattr(request, 'FILES') and request.FILES:
            logger.debug(f"Request FILES keys: {list(request.FILES.keys())}")
            if 'profile_picture' in request.FILES:
                logger.debug(f"profile_picture in FILES type: {type(request.FILES['profile_picture'])}")
        
        return super().update(request, *args, **kwargs)


class AvailabilityManagementView(generics.ListCreateAPIView):
    """
    Manage professional availability
    """
    serializer_class = AvailabilityCreateSerializer
    permission_classes = [IsVerifiedProfessional]
    
    def get_queryset(self):
        # Handle schema generation with AnonymousUser
        if getattr(self, 'swagger_fake_view', False):
            return ProfessionalAvailability.objects.none()
            
        if not hasattr(self.request.user, 'professional_profile'):
            return ProfessionalAvailability.objects.none()
            
        professional = self.request.user.professional_profile
        region = getattr(self.request, 'region', None)
        
        return ProfessionalAvailability.objects.filter(
            professional=professional,
            region=region
        ).order_by('weekday', 'start_time')
        
    
    def get_serializer_context(self):
        context = super().get_serializer_context()
        
        # Handle schema generation
        if getattr(self, 'swagger_fake_view', False):
            return context
            
        if hasattr(self.request.user, 'professional_profile'):
            context['professional'] = self.request.user.professional_profile
        context['region'] = getattr(self.request, 'region', None)
        return context
    
    @swagger_auto_schema(
        operation_description="Set availability schedule",
        request_body=AvailabilityCreateSerializer,
        responses={201: AvailabilityCreateSerializer()}
    )
    def post(self, request, *args, **kwargs):
        return super().post(request, *args, **kwargs)


class AvailabilityUpdateView(generics.RetrieveUpdateDestroyAPIView):
    """
    Update or delete specific availability slot
    """
    serializer_class = AvailabilityCreateSerializer
    permission_classes = [IsVerifiedProfessional]
    
    def get_queryset(self):
        # Handle schema generation with AnonymousUser
        if getattr(self, 'swagger_fake_view', False):
            return ProfessionalAvailability.objects.none()
            
        if not hasattr(self.request.user, 'professional_profile'):
            return ProfessionalAvailability.objects.none()
            
        professional = self.request.user.professional_profile
        return ProfessionalAvailability.objects.filter(professional=professional)



class UnavailabilityView(generics.ListCreateAPIView):
    """
    Manage unavailable dates/times
    """
    serializer_class = UnavailabilitySerializer
    permission_classes = [IsVerifiedProfessional]
    
    def get_queryset(self):
        # Handle schema generation with AnonymousUser
        if getattr(self, 'swagger_fake_view', False):
            return ProfessionalUnavailability.objects.none()
            
        if not hasattr(self.request.user, 'professional_profile'):
            return ProfessionalUnavailability.objects.none()
            
        professional = self.request.user.professional_profile
        region = getattr(self.request, 'region', None)
        
        return ProfessionalUnavailability.objects.filter(
            professional=professional,
            region=region,
            date__gte=timezone.now().date()
        ).order_by('date', 'start_time')
    
    def get_serializer_context(self):
        context = super().get_serializer_context()
        
        # Handle schema generation
        if getattr(self, 'swagger_fake_view', False):
            return context
            
        if hasattr(self.request.user, 'professional_profile'):
            context['professional'] = self.request.user.professional_profile
        context['region'] = getattr(self.request, 'region', None)
        return context


class DocumentUploadView(generics.ListCreateAPIView):
    """
    Upload verification documents
    """
    serializer_class = ProfessionalDocumentSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        # Handle schema generation with AnonymousUser
        if getattr(self, 'swagger_fake_view', False):
            return ProfessionalDocument.objects.none()
            
        if hasattr(self.request.user, 'professional_profile'):
            return ProfessionalDocument.objects.filter(
                professional=self.request.user.professional_profile
            )
        return ProfessionalDocument.objects.none()
    
    def perform_create(self, serializer):
        # Handle schema generation
        if getattr(self, 'swagger_fake_view', False):
            return
            
        if hasattr(self.request.user, 'professional_profile'):
            professional = self.request.user.professional_profile
            serializer.save(professional=professional)


@api_view(['GET'])
@permission_classes([permissions.AllowAny])
@swagger_auto_schema(
    operation_description="Get available time slots for professional. Optionally, provide start_date and end_date to get all available slots for a date range.",
    manual_parameters=[
        openapi.Parameter(
            'professional_id', openapi.IN_QUERY,
            description="Professional ID",
            type=openapi.TYPE_INTEGER,
            required=True
        ),
        openapi.Parameter(
            'service_id', openapi.IN_QUERY,
            description="Service ID",
            type=openapi.TYPE_INTEGER,
            required=True
        ),
        openapi.Parameter(
            'date', openapi.IN_QUERY,
            description="Date (YYYY-MM-DD)",
            type=openapi.TYPE_STRING,
            required=False
        ),
        openapi.Parameter(
            'start_date', openapi.IN_QUERY,
            description="Start date for range (YYYY-MM-DD)",
            type=openapi.TYPE_STRING,
            required=False
        ),
        openapi.Parameter(
            'end_date', openapi.IN_QUERY,
            description="End date for range (YYYY-MM-DD)",
            type=openapi.TYPE_STRING,
            required=False
        ),
    ],
    responses={200: AvailabilitySlotSerializer(many=True)}
)
def get_available_slots(request):
    """
    Get available time slots for a professional on a specific date, or for a date range if start_date and end_date are provided.
    Slots are generated every 30 minutes within the available range, regardless of service duration.
    """
    professional_id = request.GET.get('professional_id')
    service_id = request.GET.get('service_id')
    date_str = request.GET.get('date')
    start_date_str = request.GET.get('start_date')
    end_date_str = request.GET.get('end_date')

    # Validate required params
    if not all([professional_id, service_id]):
        return Response(
            {'error': 'professional_id and service_id are required'},
            status=status.HTTP_400_BAD_REQUEST
        )

    try:
        professional = Professional.objects.get(id=professional_id, is_active=True)
        from services.models import Service
        service = Service.objects.get(id=service_id)
    except (Professional.DoesNotExist, Service.DoesNotExist):
        return Response(
            {'error': 'Invalid parameters'},
            status=status.HTTP_400_BAD_REQUEST
        )

    def get_slots_for_date(date):
        availability = professional.availability_schedule.filter(
            weekday=date.weekday(),
            is_active=True
        )
        if not availability.exists():
            return []
        slots = []
        slot_duration = 30  # 30-minute slots
        for avail in availability:
            current_time = datetime.combine(date, avail.start_time)
            end_time = datetime.combine(date, avail.end_time)
            # Handle breaks
            break_start = None
            break_end = None
            if avail.break_start and avail.break_end:
                break_start = datetime.combine(date, avail.break_start)
                break_end = datetime.combine(date, avail.break_end)
            while current_time + timedelta(minutes=slot_duration) <= end_time:
                slot_end = current_time + timedelta(minutes=slot_duration)
                # Check if slot conflicts with break time
                if break_start and break_end:
                    if not (slot_end <= break_start or current_time >= break_end):
                        current_time += timedelta(minutes=slot_duration)
                        continue
                # Check unavailability (no region filter)
                unavailabilities = professional.unavailable_dates.filter(date=date)
                is_unavailable = False
                for unavail in unavailabilities:
                    if unavail.start_time is None and unavail.end_time is None:
                        is_unavailable = True
                        break
                    if unavail.start_time is None or unavail.end_time is None:
                        is_unavailable = True
                        break
                    if (current_time.time() < unavail.end_time and slot_end.time() > unavail.start_time):
                        is_unavailable = True
                        break
                if is_unavailable:
                    current_time += timedelta(minutes=slot_duration)
                    continue
                # Check for existing bookings (no region filter)
                from bookings.models import Booking
                existing_bookings = Booking.objects.filter(
                    professional=professional,
                    scheduled_date=date,
                    status__in=['confirmed', 'in_progress']
                )
                is_booked = False
                for booking in existing_bookings:
                    booking_start = booking.scheduled_time
                    booking_end = (datetime.combine(date, booking_start) + timedelta(minutes=booking.duration_minutes)).time()
                    if (current_time.time() < booking_end and slot_end.time() > booking_start):
                        is_booked = True
                        break
                slots.append({
                    'date': date,
                    'start_time': current_time.time(),
                    'end_time': slot_end.time(),
                    'is_available': not (is_unavailable or is_booked),
                    'price': service.get_regional_price(getattr(booking, 'region', None)) if is_booked else service.get_regional_price(None)
                })
                current_time += timedelta(minutes=slot_duration)
        return slots

    # If start_date and end_date are provided, return all available slots for the range
    if start_date_str and end_date_str:
        try:
            start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
            end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
        except ValueError:
            return Response({'error': 'Invalid date format for start_date or end_date'}, status=status.HTTP_400_BAD_REQUEST)
        if start_date > end_date:
            return Response({'error': 'start_date must be before or equal to end_date'}, status=status.HTTP_400_BAD_REQUEST)
        results = []
        current_date = start_date
        while current_date <= end_date:
            slots = get_slots_for_date(current_date)
            if slots:
                results.append({
                    'date': current_date,
                    'slots': slots
                })
            current_date += timedelta(days=1)
        return Response(results)

    # Default: single date (legacy behavior)
    if not date_str:
        return Response({'error': 'date is required if start_date and end_date are not provided'}, status=status.HTTP_400_BAD_REQUEST)
    try:
        date = datetime.strptime(date_str, '%Y-%m-%d').date()
    except ValueError:
        return Response({'error': 'Invalid date format for date'}, status=status.HTTP_400_BAD_REQUEST)
    slots = get_slots_for_date(date)
    serializer = AvailabilitySlotSerializer(slots, many=True)
    return Response(serializer.data)


@api_view(['GET'])
@permission_classes([permissions.AllowAny])
@swagger_auto_schema(
    operation_description="Search professionals with advanced filters",
    manual_parameters=[
        openapi.Parameter(
            'service_id', openapi.IN_QUERY,
            description="Service ID",
            type=openapi.TYPE_INTEGER
        ),
        openapi.Parameter(
            'date', openapi.IN_QUERY,
            description="Preferred date",
            type=openapi.TYPE_STRING
        ),
        openapi.Parameter(
            'time', openapi.IN_QUERY,
            description="Preferred time (HH:MM)",
            type=openapi.TYPE_STRING
        ),
        openapi.Parameter(
            'min_rating', openapi.IN_QUERY,
            description="Minimum rating",
            type=openapi.TYPE_NUMBER
        ),
        openapi.Parameter(
            'max_price', openapi.IN_QUERY,
            description="Maximum price",
            type=openapi.TYPE_NUMBER
        ),
    ],
    responses={200: ProfessionalListSerializer(many=True)}
)
def search_professionals(request):
    """
    Advanced professional search with availability and pricing filters
    """
    region = getattr(request, 'region', None)
    if not region:
        return Response([])
    
    # Get search parameters
    service_id = request.GET.get('service_id')
    date_str = request.GET.get('date')
    time_str = request.GET.get('time')
    min_rating = request.GET.get('min_rating')
    max_price = request.GET.get('max_price')
    verified_only = request.GET.get('verified_only', 'true').lower() == 'true'
    
    # Base queryset
    queryset = Professional.objects.get_active_professionals(region)
    
    if verified_only:
        queryset = queryset.filter(is_verified=True)
    
    if min_rating:
        queryset = queryset.filter(rating__gte=float(min_rating))
    
    if service_id:
        queryset = queryset.filter(
            professionalservice__service_id=service_id,
            professionalservice__region=region,
            professionalservice__is_active=True
        )
        
        # Filter by price if specified
        if max_price:
            # This is complex as we need to check both custom and base prices
            from services.models import Service
            try:
                service = Service.objects.get(id=service_id)
                regional_price = service.get_regional_price(region)
                
                queryset = queryset.filter(
                    Q(professionalservice__custom_price__lte=float(max_price)) |
                    Q(professionalservice__custom_price__isnull=True, 
                      professionalservice__service__base_price__lte=float(max_price))
                )
            except Service.DoesNotExist:
                pass
    
    # Filter by availability if date/time specified
    if date_str and time_str and service_id:
        try:
            date = datetime.strptime(date_str, '%Y-%m-%d').date()
            time = datetime.strptime(time_str, '%H:%M').time()
            
            from services.models import Service
            service = Service.objects.get(id=service_id)
            
            # Filter professionals who are available
            available_professionals = []
            for professional in queryset:
                if professional.is_available(date, time, service.duration_minutes, region):
                    available_professionals.append(professional.id)
            
            queryset = queryset.filter(id__in=available_professionals)
            
        except (ValueError, Service.DoesNotExist):
            pass
    
    # Serialize and return
    professionals = queryset.distinct().order_by('-rating', '-total_reviews')[:20]
    serializer = ProfessionalListSerializer(professionals, many=True)
    return Response(serializer.data)


@api_view(['GET'])
@permission_classes([permissions.AllowAny])
@swagger_auto_schema(
    operation_description="Get top rated professionals",
    responses={200: ProfessionalListSerializer(many=True)}
)
def top_rated_professionals(request):
    """
    Get top rated professionals for current region
    """
    region = getattr(request, 'region', None)
    if not region:
        return Response([])
    
    professionals = Professional.objects.get_top_rated(region, limit=10)
    serializer = ProfessionalListSerializer(professionals, many=True)
    return Response(serializer.data)


# Professional Dashboard Views (for professional users)

@api_view(['GET'])
@permission_classes([IsVerifiedProfessional])
@swagger_auto_schema(
    operation_description="Get professional dashboard stats",
    responses={200: openapi.Response('Dashboard stats')}
)
def professional_dashboard(request):
    """
    Get professional dashboard statistics
    """
    professional = request.user.professional_profile
    region = getattr(request, 'region', None)
    
    # Get stats for current month
    from django.utils import timezone
    from bookings.models import Booking
    
    current_month = timezone.now().replace(day=1)
    
    bookings_this_month = Booking.objects.filter(
        professional=professional,
        region=region,
        created_at__gte=current_month
    )
    
    completed_bookings = bookings_this_month.filter(status='completed')
    
    stats = {
        'total_bookings_this_month': bookings_this_month.count(),
        'completed_bookings_this_month': completed_bookings.count(),
        'pending_bookings': Booking.objects.filter(
            professional=professional,
            region=region,
            status='pending'
        ).count(),
        'upcoming_bookings': Booking.objects.filter(
            professional=professional,
            region=region,
            status='confirmed',
            scheduled_date__gte=timezone.now().date()
        ).count(),
        'total_earnings_this_month': sum(
            booking.total_amount for booking in completed_bookings
        ),
        'average_rating': float(professional.rating),
        'total_reviews': professional.total_reviews,
        'profile_completion': {
            'bio_completed': bool(professional.bio),
            'services_added': professional.services.count() > 0,
            'availability_set': professional.availability_schedule.filter(
                region=region
            ).exists(),
            'documents_uploaded': professional.documents.exists(),
            'is_verified': professional.is_verified
        }
    }
    
    return Response(stats)


class AdminProfessionalDetailView(generics.RetrieveAPIView):
    """
    Get comprehensive professional information for admin
    """
    serializer_class = ProfessionalAdminDetailSerializer
    permission_classes = [permissions.IsAdminUser]
    lookup_field = 'id'
    
    @swagger_auto_schema(
        operation_description="Get comprehensive professional information for admin",
        responses={200: ProfessionalAdminDetailSerializer()}
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)
    
    def get_queryset(self):
        return Professional.objects.select_related(
            'user'
        ).prefetch_related(
            'regions',
            'services',
            'availability_schedule',
            'documents',
            'professionalservice_set__service__category',
            'professionalservice_set__region',
            'professionalregion_set__region'
        )


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def test_file_upload(request):
    """Test endpoint to debug file upload issues"""
    import logging
    logger = logging.getLogger(__name__)
    
    logger.debug(f"Test file upload called")
    logger.debug(f"Request method: {request.method}")
    logger.debug(f"Request content type: {request.content_type}")
    logger.debug(f"Request data type: {type(request.data)}")
    logger.debug(f"Request data keys: {list(request.data.keys()) if hasattr(request.data, 'keys') else 'No keys'}")
    
    if hasattr(request, 'FILES') and request.FILES:
        logger.debug(f"Request FILES keys: {list(request.FILES.keys())}")
        for key, value in request.FILES.items():
            logger.debug(f"File {key}: type={type(value)}, name={getattr(value, 'name', 'No name')}, size={getattr(value, 'size', 'No size')}")
    
    if 'profile_picture' in request.data:
        logger.debug(f"profile_picture in data: type={type(request.data['profile_picture'])}, value={request.data['profile_picture']}")
    
    return Response({
        'message': 'File upload test completed',
        'data_keys': list(request.data.keys()) if hasattr(request.data, 'keys') else [],
        'files_keys': list(request.FILES.keys()) if hasattr(request, 'FILES') else [],
        'content_type': request.content_type
    })


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def simple_file_test(request):
    """Simple test to isolate file upload issues"""
    import logging
    logger = logging.getLogger(__name__)
    
    logger.debug("=== SIMPLE FILE TEST ===")
    logger.debug(f"Request method: {request.method}")
    logger.debug(f"Request content type: {request.content_type}")
    logger.debug(f"Request data type: {type(request.data)}")
    
    # Check request.data
    if hasattr(request.data, 'keys'):
        logger.debug(f"Request data keys: {list(request.data.keys())}")
        for key, value in request.data.items():
            logger.debug(f"  {key}: type={type(value)}, value={value}")
    
    # Check request.FILES
    if hasattr(request, 'FILES') and request.FILES:
        logger.debug(f"Request FILES keys: {list(request.FILES.keys())}")
        for key, value in request.FILES.items():
            logger.debug(f"  File {key}: type={type(value)}")
            if hasattr(value, 'name'):
                logger.debug(f"    name: {value.name}")
            if hasattr(value, 'size'):
                logger.debug(f"    size: {value.size}")
            if hasattr(value, 'content_type'):
                logger.debug(f"    content_type: {value.content_type}")
    else:
        logger.debug("No FILES in request")
    
    # Try to access profile_picture specifically
    if 'profile_picture' in request.data:
        profile_pic = request.data['profile_picture']
        logger.debug(f"profile_picture in data: type={type(profile_pic)}")
        try:
            if hasattr(profile_pic, 'name'):
                logger.debug(f"  name: {profile_pic.name}")
            else:
                logger.debug(f"  No name attribute")
        except Exception as e:
            logger.error(f"Error accessing profile_picture.name: {e}")
    
    if hasattr(request, 'FILES') and 'profile_picture' in request.FILES:
        profile_pic = request.FILES['profile_picture']
        logger.debug(f"profile_picture in FILES: type={type(profile_pic)}")
        try:
            if hasattr(profile_pic, 'name'):
                logger.debug(f"  name: {profile_pic.name}")
            else:
                logger.debug(f"  No name attribute")
        except Exception as e:
            logger.error(f"Error accessing profile_picture.name: {e}")
    
    return Response({
        'message': 'Simple file test completed',
        'data_keys': list(request.data.keys()) if hasattr(request.data, 'keys') else [],
        'files_keys': list(request.FILES.keys()) if hasattr(request, 'FILES') else [],
        'content_type': request.content_type
    })