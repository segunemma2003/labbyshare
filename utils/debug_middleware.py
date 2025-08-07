import logging
import traceback
from django.http import JsonResponse
from django.conf import settings

logger = logging.getLogger(__name__)

class DebugMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        return response

    def process_exception(self, request, exception):
        if settings.DEBUG:
            # Log the full exception with traceback
            logger.error(f"Exception in {request.path}: {str(exception)}")
            logger.error(f"Request method: {request.method}")
            logger.error(f"Request user: {request.user}")
            logger.error(f"Request data: {request.data if hasattr(request, 'data') else 'No data'}")
            logger.error(f"Full traceback:\n{traceback.format_exc()}")
            
            # Return detailed error response in debug mode
            return JsonResponse({
                'error': str(exception),
                'type': type(exception).__name__,
                'path': request.path,
                'method': request.method,
                'traceback': traceback.format_exc().split('\n') if settings.DEBUG else None,
                'request_data': request.data if hasattr(request, 'data') else None,
            }, status=500)
        
        return None 