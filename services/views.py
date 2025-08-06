from rest_framework import generics, permissions, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from django.core.cache import cache
from django.conf import settings
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi
from rest_framework.parsers import MultiPartParser, FormParser
from .serializers import VideoUploadSerializer

from .models import Category, Service, AddOn
from .serializers import (
    CategorySerializer, ServiceListSerializer, ServiceDetailSerializer,
    AddOnSerializer, AddOnListSerializer, ServiceReviewSerializer
)


class AddOnListView(generics.ListAPIView):
    """
    List all add-ons for the current region (not category-specific)
    """
    serializer_class = AddOnListSerializer
    permission_classes = [permissions.AllowAny]
    
    @swagger_auto_schema(
        operation_description="Get all add-ons for current region",
        responses={200: AddOnListSerializer(many=True)}
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)
    
    def get_queryset(self):
        region = getattr(self.request, 'region', None)
        if not region:
            return AddOn.objects.none()
        return AddOn.objects.filter(region=region, is_active=True)


class CategoryListView(generics.ListAPIView):
    """
    List categories for current region
    """
    serializer_class = CategorySerializer
    permission_classes = [permissions.AllowAny]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['is_featured']
    search_fields = ['name', 'description']
    ordering_fields = ['sort_order', 'name', 'is_featured']
    ordering = ['sort_order', 'name']
    
    @swagger_auto_schema(
        operation_description="Get categories for current region",
        manual_parameters=[
            openapi.Parameter(
                'X-Region', openapi.IN_HEADER,
                description="Region code (UK, UAE)",
                type=openapi.TYPE_STRING
            ),
            openapi.Parameter(
                'is_featured', openapi.IN_QUERY,
                description="Filter featured categories only",
                type=openapi.TYPE_BOOLEAN,
                required=False
            ),
        ],
        responses={200: CategorySerializer(many=True)}
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)
    
    def get_queryset(self):
        region = getattr(self.request, 'region', None)
        if not region:
            return Category.objects.none()
        
        # Check cache first
        cache_key = settings.CACHE_KEYS['CATEGORIES'].format(region.id)
        cached_categories = cache.get(cache_key)
        
        if cached_categories is not None:
            return cached_categories
        
        queryset = Category.objects.filter(
            region=region,
            is_active=True
        ).prefetch_related('services').order_by('sort_order', 'name')
        
        # Cache the queryset
        cache.set(cache_key, queryset, settings.CACHE_TIMEOUTS['CATEGORIES'])
        
        return queryset
    
    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['include_addons'] = True
        return context


class ServiceListView(generics.ListAPIView):
    """
    List services for current region with filtering
    """
    serializer_class = ServiceListSerializer
    permission_classes = [permissions.AllowAny]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['category', 'is_featured']
    search_fields = ['name', 'description']
    ordering_fields = ['name', 'base_price', 'duration_minutes', 'sort_order']
    ordering = ['sort_order', 'name']
    
    @swagger_auto_schema(
        operation_description="Get services for current region",
        manual_parameters=[
            openapi.Parameter(
                'category', openapi.IN_QUERY,
                description="Filter by category ID",
                type=openapi.TYPE_INTEGER
            ),
            openapi.Parameter(
                'is_featured', openapi.IN_QUERY,
                description="Filter featured services only",
                type=openapi.TYPE_BOOLEAN
            ),
        ],
        responses={200: ServiceListSerializer(many=True)}
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)
    
    def get_queryset(self):
        region = getattr(self.request, 'region', None)
        if not region:
            return Service.objects.none()
        
        return Service.objects.filter(
            category__region=region,
            is_active=True
        ).select_related('category').prefetch_related('images')
    
    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['region'] = getattr(self.request, 'region', None)
        return context


class ServiceDetailView(generics.RetrieveAPIView):
    """
    Get detailed service information
    """
    serializer_class = ServiceDetailSerializer
    permission_classes = [permissions.AllowAny]
    lookup_field = 'id'
    
    @swagger_auto_schema(
        operation_description="Get detailed service information",
        responses={200: ServiceDetailSerializer()}
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)
    
    def get_queryset(self):
        region = getattr(self.request, 'region', None)
        if not region:
            return Service.objects.none()
        
        return Service.objects.filter(
            category__region=region,
            is_active=True
        ).select_related('category').prefetch_related(
            'images',
            'regional_pricing',
            'reviews__user',
            'professionals'
        )
    
    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['region'] = getattr(self.request, 'region', None)
        return context


class CategoryServicesView(generics.ListAPIView):
    """
    Get services for a specific category
    """
    serializer_class = ServiceListSerializer
    permission_classes = [permissions.AllowAny]
    
    @swagger_auto_schema(
        operation_description="Get services for a specific category",
        responses={200: ServiceListSerializer(many=True)}
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)
    
    def get_queryset(self):
        category_id = self.kwargs['category_id']
        region = getattr(self.request, 'region', None)
        
        if not region:
            return Service.objects.none()
        
        return Service.objects.filter(
            category_id=category_id,
            category__region=region,
            is_active=True
        ).select_related('category').prefetch_related('images')
    
    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['region'] = getattr(self.request, 'region', None)
        return context


class CategoryAddOnsView(generics.ListAPIView):
    """
    Get add-ons for a specific category
    """
    serializer_class = AddOnSerializer
    permission_classes = [permissions.AllowAny]
    
    @swagger_auto_schema(
        operation_description="Get add-ons for a specific category",
        responses={200: AddOnSerializer(many=True)}
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)
    
    def get_queryset(self):
        category_id = self.kwargs['category_id']
        region = getattr(self.request, 'region', None)
        
        if not region:
            return AddOn.objects.none()
        
        return AddOn.objects.filter(categories__id=category_id, region=region, is_active=True).order_by('name')


class ServiceReviewsView(generics.ListAPIView):
    """
    Get reviews for a specific service
    """
    serializer_class = ServiceReviewSerializer
    permission_classes = [permissions.AllowAny]
    
    @swagger_auto_schema(
        operation_description="Get reviews for a specific service",
        responses={200: ServiceReviewSerializer(many=True)}
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)
    
    def get_queryset(self):
        service_id = self.kwargs['service_id']
        return Service.objects.get(id=service_id).reviews.filter(
            is_published=True
        ).select_related('user').order_by('-created_at')


class VideoUploadView(generics.ListCreateAPIView):
    serializer_class = VideoUploadSerializer
    permission_classes = [permissions.IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def get_queryset(self):
        # Placeholder: return empty queryset or implement video model if needed
        return []

    def perform_create(self, serializer):
        # Handle file saving logic here
        # For now, just pass (or implement actual save logic)
        pass


@api_view(['GET'])
@permission_classes([permissions.AllowAny])
@swagger_auto_schema(
    operation_description="Get featured categories for current region",
    responses={200: CategorySerializer(many=True)}
)
def featured_categories(request):
    """
    Get featured categories for current region
    """
    region = getattr(request, 'region', None)
    if not region:
        return Response({'error': 'Region not found'}, status=400)
    
    # Check cache first
    cache_key = f"featured_categories_{region.id}"
    cached_categories = cache.get(cache_key)
    
    if cached_categories is not None:
        return Response(cached_categories)
    
    categories = Category.objects.filter(
        region=region,
        is_active=True,
        is_featured=True
    ).prefetch_related('services').order_by('sort_order', 'name')
    
    serializer = CategorySerializer(categories, many=True, context={'request': request})
    data = serializer.data
    
    # Cache for 1 hour
    cache.set(cache_key, data, 3600)
    
    return Response(data)


@api_view(['GET'])
@permission_classes([permissions.AllowAny])
@swagger_auto_schema(
    operation_description="Get featured services for current region",
    responses={200: ServiceListSerializer(many=True)}
)
def featured_services(request):
    """
    Get featured services for current region
    """
    region = getattr(request, 'region', None)
    if not region:
        return Response([])
    
    services = Service.objects.filter(
        category__region=region,
        is_active=True,
        is_featured=True
    ).select_related('category').prefetch_related('images')[:10]
    
    serializer = ServiceListSerializer(
        services,
        many=True,
        context={'request': request, 'region': region}
    )
    
    return Response(serializer.data)


@api_view(['GET'])
@permission_classes([permissions.AllowAny])
@swagger_auto_schema(
    operation_description="Search services",
    manual_parameters=[
        openapi.Parameter(
            'q', openapi.IN_QUERY,
            description="Search query",
            type=openapi.TYPE_STRING
        ),
        openapi.Parameter(
            'category', openapi.IN_QUERY,
            description="Category ID",
            type=openapi.TYPE_INTEGER
        ),
    ],
    responses={200: ServiceListSerializer(many=True)}
)
def search_services(request):
    """
    Search services by name and description
    """
    region = getattr(request, 'region', None)
    if not region:
        return Response([])
    
    query = request.GET.get('q', '')
    category_id = request.GET.get('category')
    
    services = Service.objects.filter(
        category__region=region,
        is_active=True
    ).select_related('category')
    
    if query:
        services = services.filter(
            name__icontains=query
        ) | services.filter(
            description__icontains=query
        )
    
    if category_id:
        services = services.filter(category_id=category_id)
    
    services = services.order_by('sort_order', 'name')[:20]
    
    serializer = ServiceListSerializer(
        services,
        many=True,
        context={'request': request, 'region': region}
    )
    
    return Response(serializer.data)