from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt


@csrf_exempt
def handler404(request, exception=None):
    """Custom 404 handler"""
    return JsonResponse({
        'error': True,
        'message': 'Endpoint not found',
        'status_code': 404
    }, status=404)


@csrf_exempt
def handler500(request):
    """Custom 500 handler"""
    return JsonResponse({
        'error': True,
        'message': 'Internal server error',
        'status_code': 500
    }, status=500)