from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from rest_framework import permissions
from drf_yasg.views import get_schema_view
from drf_yasg import openapi

# Swagger Schema View
schema_view = get_schema_view(
    openapi.Info(
        title="The beauty Spa by Shea API",
        default_version='v1',
        description="""
        The beauty Spa by Shea Multi-Region Service Booking Platform API
        
        ## Features
        - ✅ Multi-region support (UK, UAE)
        - ✅ Token-based authentication
        - ✅ Social authentication (Google, Apple via Firebase)
        - ✅ Region-specific services and pricing
        - ✅ Professional booking system with availability
        - ✅ Payment processing with Stripe
        - ✅ Push notifications via Firebase
        - ✅ Admin panel with analytics
        - ✅ Health monitoring and analytics
        
        ## Authentication
        Include the token in the Authorization header:
        `Authorization: Token your_token_here`
        
        ## Regions
        All endpoints support region switching via:
        - Header: `X-Region: UK` or `X-Region: UAE`
        - Query parameter: `?region=UK`
        - User profile setting (for authenticated users)
        
        ## Professional Workflow
        1. Register as professional
        2. Upload verification documents
        3. Wait for admin approval
        4. Set availability schedule
        5. Start accepting bookings
        
        ## Booking Workflow
        1. Search professionals by service/location
        2. Check availability slots
        3. Create booking with payment
        4. Receive confirmations
        5. Complete service and review
        """,
        terms_of_service="https://labmyshare.com/terms/",
        contact=openapi.Contact(email="api@labmyshare.com"),
        license=openapi.License(name="MIT License"),
    ),
    public=True,
    permission_classes=[permissions.AllowAny],
    authentication_classes=[],
)

urlpatterns = [
    # Admin
    path('admin/', admin.site.urls),
    
    # API Documentation
    path('swagger<format>/', schema_view.without_ui(cache_timeout=0), name='schema-json'),
    path('swagger/', schema_view.with_ui('swagger', cache_timeout=0), name='schema-swagger-ui'),
    path('redoc/', schema_view.with_ui('redoc', cache_timeout=0), name='schema-redoc'),
    
    # Core API Endpoints
    path('api/v1/auth/', include('accounts.urls')),
    path('api/v1/regions/', include('regions.urls')),
    path('api/v1/services/', include('services.urls')),
    path('api/v1/professionals/', include('professionals.urls')),
    path('api/v1/bookings/', include('bookings.urls')),
    path('api/v1/payments/', include('payments.urls')),
    path('api/v1/notifications/', include('notifications.urls')),
    
    # Admin & Analytics
    path('api/v1/admin/', include('admin_panel.urls')),
    path('api/v1/analytics/', include('analytics.urls')),
    
    # Health check
    path('health/', include('health.urls')),
]

# Serve media files in development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)

# Error handlers
handler404 = 'utils.views.handler404'
handler500 = 'utils.views.handler500'