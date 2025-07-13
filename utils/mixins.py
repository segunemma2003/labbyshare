"""
Custom mixins for views
"""
from rest_framework import status
from rest_framework.response import Response
from django.core.cache import cache


class CachedListMixin:
    """
    Mixin to cache list view results
    """
    cache_timeout = 3600
    cache_key_prefix = None
    
    def get_cache_key(self):
        """Generate cache key for this view"""
        prefix = self.cache_key_prefix or f"{self.__class__.__name__}"
        region = getattr(self.request, 'region', None)
        region_code = region.code if region else 'global'
        query_params = self.request.GET.urlencode()
        return f"{prefix}:{region_code}:{hash(query_params)}"
    
    def list(self, request, *args, **kwargs):
        """Override list method to add caching"""
        cache_key = self.get_cache_key()
        cached_response = cache.get(cache_key)
        
        if cached_response is not None:
            return Response(cached_response)
        
        response = super().list(request, *args, **kwargs)
        
        if response.status_code == 200:
            cache.set(cache_key, response.data, self.cache_timeout)
        
        return response


class RegionFilterMixin:
    """
    Mixin to automatically filter by region
    """
    
    def get_queryset(self):
        """Filter queryset by current region"""
        queryset = super().get_queryset()
        region = getattr(self.request, 'region', None)
        
        if region and hasattr(queryset.model, 'region'):
            queryset = queryset.filter(region=region)
        
        return queryset
