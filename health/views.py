from django.http import JsonResponse
from django.db import connection
from django.core.cache import cache
from django.utils import timezone
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
import redis
import logging

logger = logging.getLogger(__name__)


@api_view(['GET'])
@permission_classes([AllowAny])
def health_check(request):
    """
    Basic health check endpoint
    """
    return Response({
        'status': 'healthy',
        'timestamp': timezone.now().isoformat(),
        'service': 'LabMyShare API'
    })


@api_view(['GET'])
@permission_classes([AllowAny])
def detailed_health_check(request):
    """
    Detailed health check including database, cache, and external services
    """
    health_status = {
        'status': 'healthy',
        'timestamp': timezone.now().isoformat(),
        'service': 'LabMyShare API',
        'checks': {}
    }
    
    # Database check
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            health_status['checks']['database'] = {
                'status': 'healthy',
                'response_time_ms': 0  # You could measure this
            }
    except Exception as e:
        health_status['checks']['database'] = {
            'status': 'unhealthy',
            'error': str(e)
        }
        health_status['status'] = 'unhealthy'
    
    # Cache check (Redis)
    try:
        cache.set('health_check', 'test', 10)
        cache.get('health_check')
        health_status['checks']['cache'] = {'status': 'healthy'}
    except Exception as e:
        health_status['checks']['cache'] = {
            'status': 'unhealthy',
            'error': str(e)
        }
        health_status['status'] = 'unhealthy'
    
    # Celery check (basic)
    try:
        from celery import current_app
        inspect = current_app.control.inspect()
        stats = inspect.stats()
        
        if stats:
            health_status['checks']['celery'] = {'status': 'healthy'}
        else:
            health_status['checks']['celery'] = {'status': 'unhealthy', 'error': 'No workers available'}
            health_status['status'] = 'degraded'
    except Exception as e:
        health_status['checks']['celery'] = {
            'status': 'unhealthy',
            'error': str(e)
        }
        health_status['status'] = 'degraded'
    
    return Response(health_status)