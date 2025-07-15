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
        
        # Cache the serialized results (not the model objects)
        if response.status_code == 200 and 'results' in response.data:
            cache.set(
                cache_key, 
                response.data['results'],  # This is already serialized JSON data
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
    
    def retrieve(self, request, *args, **kwargs):
        code = self.kwargs['code'].upper()
        cache_key = f"region:code:{code}"
        
        # Try to get serialized data from cache
        cached_data = cache.get(cache_key)
        if cached_data is not None:
            return Response(cached_data)
        
        # If not in cache, get from database and serialize
        try:
            region = self.get_queryset().get(code=code)
            serializer = self.get_serializer(region)
            serialized_data = serializer.data
            
            # Cache the serialized data
            cache.set(cache_key, serialized_data, settings.CACHE_TIMEOUTS['REGIONS'])
            
            return Response(serialized_data)
        except Region.DoesNotExist:
            return Response({'error': 'Region not found'}, status=404)


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