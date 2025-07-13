from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from django.db.models import Count, Sum, Avg
from django.utils import timezone
from datetime import timedelta
from .models import AnalyticsEvent


@api_view(['POST'])
@permission_classes([AllowAny])
def track_event(request):
    """
    Track analytics event
    """
    try:
        event_data = {
            'event_type': request.data.get('event_type'),
            'page_url': request.data.get('page_url', ''),
            'referrer': request.data.get('referrer', ''),
            'user_agent': request.META.get('HTTP_USER_AGENT', ''),
            'ip_address': request.META.get('REMOTE_ADDR'),
            'session_id': request.session.session_key or '',
            'properties': request.data.get('properties', {})
        }
        
        if request.user.is_authenticated:
            event_data['user'] = request.user
            event_data['region'] = getattr(request, 'region', None)
        
        # Add contextual objects if provided
        service_id = request.data.get('service_id')
        if service_id:
            from services.models import Service
            try:
                event_data['service'] = Service.objects.get(id=service_id)
            except Service.DoesNotExist:
                pass
        
        booking_id = request.data.get('booking_id')
        if booking_id:
            from bookings.models import Booking
            try:
                event_data['booking'] = Booking.objects.get(booking_id=booking_id)
            except Booking.DoesNotExist:
                pass
        
        AnalyticsEvent.objects.create(**event_data)
        
        return Response({'status': 'tracked'})
        
    except Exception as e:
        return Response({'error': str(e)}, status=400)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def user_analytics(request):
    """
    Get analytics for current user
    """
    if not request.user.is_authenticated:
        return Response({'error': 'Authentication required'}, status=401)
    
    # Get user's events from last 30 days
    since = timezone.now() - timedelta(days=30)
    events = AnalyticsEvent.objects.filter(
        user=request.user,
        created_at__gte=since
    )
    
    analytics = {
        'total_events': events.count(),
        'event_breakdown': list(events.values('event_type').annotate(count=Count('id'))),
        'page_views': events.filter(event_type='page_view').count(),
        'searches': events.filter(event_type='search').count(),
        'bookings_started': events.filter(event_type='booking_started').count(),
        'bookings_completed': events.filter(event_type='booking_completed').count(),
    }
    
    return Response(analytics)