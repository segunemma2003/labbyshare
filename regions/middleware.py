from django.utils.deprecation import MiddlewareMixin
from django.core.cache import cache
from .models import Region


class RegionMiddleware(MiddlewareMixin):
    """
    Middleware to handle region context for multi-location support
    """
    
    def process_request(self, request):
        """
        Set region context for each request
        """
        # Get region from header, query param, or user profile
        region_code = self.get_region_code(request)
        
        if region_code:
            region = self.get_cached_region(region_code)
            if region:
                request.region = region
                return
        
        # Fall back to default region (UK)
        request.region = self.get_cached_region('UK')
    
    def get_region_code(self, request):
        """
        Extract region code from various sources
        Priority: Header > Query Param > User Profile > Default
        """
        # 1. Check X-Region header
        region_code = request.META.get('HTTP_X_REGION')
        if region_code:
            return region_code.upper()
        
        # 2. Check query parameter
        region_code = request.GET.get('region')
        if region_code:
            return region_code.upper()
        
        # 3. Check authenticated user's current region
        if hasattr(request, 'user') and request.user.is_authenticated:
            if hasattr(request.user, 'current_region') and request.user.current_region:
                return request.user.current_region.code
        
        return None
    
    def get_cached_region(self, code):
        """
        Get region from cache or database
        """
        cache_key = f"region:code:{code}"
        region = cache.get(cache_key)
        
        if region is None:
            try:
                region = Region.objects.get(code=code, is_active=True)
                cache.set(cache_key, region, 3600)  # Cache for 1 hour
            except Region.DoesNotExist:
                return None
        
        return region