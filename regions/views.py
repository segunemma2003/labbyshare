# apps/regions/views.py
from rest_framework import generics, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from django.core.cache import cache
from django.conf import settings

from .models import Region, RegionalSettings
from .serializers import RegionSerializer, RegionalSettingsSerializer


class RegionListView(generics.ListAPIView):
    """
    List all active regions
    """
    serializer_class = RegionSerializer
    permission_classes = [AllowAny]
    
    def get_queryset(self):
        return Region.objects.filter(is_active=True).order_by('name')
    
    def list(self, request, *args, **kwargs):
        # Try to get from cache first
        cache_key = settings.CACHE_KEYS['REGIONS']
        cached_regions = cache.get(cache_key)
        
        if cached_regions is not None:
            return Response({
                'count': len(cached_regions),
                'results': cached_regions
            })
        
        # If not in cache, get from database
        response = super().list(request, *args, **kwargs)
        
        # Cache the results
        if response.status_code == 200:
            cache.set(
                cache_key, 
                response.data['results'], 
                settings.CACHE_TIMEOUTS['REGIONS']
            )
        
        return response


class RegionDetailView(generics.RetrieveAPIView):
    """
    Get specific region details
    """
    serializer_class = RegionSerializer
    permission_classes = [AllowAny]
    lookup_field = 'code'
    
    def get_queryset(self):
        return Region.objects.filter(is_active=True)
    
    def get_object(self):
        code = self.kwargs['code'].upper()
        cache_key = f"region:code:{code}"
        
        region = cache.get(cache_key)
        if region is None:
            region = self.get_queryset().get(code=code)
            cache.set(cache_key, region, settings.CACHE_TIMEOUTS['REGIONS'])
        
        return region


class RegionSettingsView(generics.ListAPIView):
    """
    Get region-specific settings
    """
    serializer_class = RegionalSettingsSerializer
    permission_classes = [AllowAny]
    
    def get_queryset(self):
        code = self.kwargs['code'].upper()
        try:
            region = Region.objects.get(code=code, is_active=True)
            return RegionalSettings.objects.filter(region=region)
        except Region.DoesNotExist:
            return RegionalSettings.objects.none()