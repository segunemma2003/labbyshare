# admin_panel/admin_operations.py
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework import status
from django.utils import timezone
from django.db.models import Count, Sum, Avg, Q
from datetime import timedelta
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi

from utils.permissions import IsAdminUser
from accounts.models import User
from professionals.models import Professional
from bookings.models import Booking
from payments.models import Payment
from services.models import Service, Category
from regions.models import Region
from .models import AdminActivity


@api_view(['GET'])
@permission_classes([IsAdminUser])
@swagger_auto_schema(
    operation_description="Get detailed user statistics for admin dashboard",
    responses={200: openapi.Response('User statistics')}
)
def get_user_statistics(request):
    """
    Get detailed user statistics for admin
    """
    today = timezone.now().date()
    
    # Registration trends (last 30 days)
    last_30_days = today - timedelta(days=30)
    registration_data = []
    
    for i in range(30):
        date = last_30_days + timedelta(days=i)
        count = User.objects.filter(date_joined__date=date).count()
        registration_data.append({
            'date': date.isoformat(),
            'registrations': count
        })
    
    # User type breakdown
    user_types = User.objects.values('user_type').annotate(count=Count('id'))
    
    # Regional distribution
    regional_distribution = User.objects.filter(
        current_region__isnull=False
    ).values('current_region__name').annotate(count=Count('id'))
    
    # Active users (logged in last 30 days)
    active_users = User.objects.filter(
        last_login__gte=timezone.now() - timedelta(days=30)
    ).count()
    
    # Verification status
    verification_stats = {
        'verified_users': User.objects.filter(is_verified=True).count(),
        'unverified_users': User.objects.filter(is_verified=False).count(),
        'verified_professionals': Professional.objects.filter(is_verified=True).count(),
        'pending_professionals': Professional.objects.filter(is_verified=False, is_active=True).count()
    }
    
    return Response({
        'registration_trends': registration_data,
        'user_types': list(user_types),
        'regional_distribution': list(regional_distribution),
        'active_users': active_users,
        'total_users': User.objects.count(),
        'verification_stats': verification_stats
    })


@api_view(['GET'])
@permission_classes([IsAdminUser])
@swagger_auto_schema(
    operation_description="Get detailed booking statistics for admin dashboard",
    responses={200: openapi.Response('Booking statistics')}
)
def get_booking_statistics(request):
    """
    Get detailed booking statistics for admin
    """
    today = timezone.now().date()
    
    # Booking trends (last 30 days)
    last_30_days = today - timedelta(days=30)
    booking_data = []
    
    for i in range(30):
        date = last_30_days + timedelta(days=i)
        bookings = Booking.objects.filter(created_at__date=date)
        booking_data.append({
            'date': date.isoformat(),
            'bookings': bookings.count(),
            'revenue': float(bookings.aggregate(total=Sum('total_amount'))['total'] or 0)
        })
    
    # Status distribution
    status_distribution = Booking.objects.values('status').annotate(count=Count('id'))
    
    # Popular services
    popular_services = Service.objects.annotate(
        booking_count=Count('booking')
    ).order_by('-booking_count')[:10].values('name', 'booking_count')
    
    # Regional performance
    regional_performance = Region.objects.annotate(
        booking_count=Count('booking_set'),
        total_revenue=Sum('booking_set__total_amount')
    ).values('name', 'booking_count', 'total_revenue')
    
    # Time-based analysis
    hourly_distribution = Booking.objects.extra(
        select={'hour': 'EXTRACT(hour FROM scheduled_time)'}
    ).values('hour').annotate(count=Count('id')).order_by('hour')
    
    # Professional performance
    top_professionals = Professional.objects.annotate(
        booking_count=Count('bookings'),
        avg_rating=Avg('reviews_received__overall_rating')
    ).filter(booking_count__gt=0).order_by('-booking_count')[:10]
    
    professional_performance = []
    for prof in top_professionals:
        professional_performance.append({
            'name': prof.user.get_full_name(),
            'booking_count': prof.booking_count,
            'avg_rating': float(prof.avg_rating or 0),
            'total_reviews': prof.total_reviews
        })
    
    return Response({
        'booking_trends': booking_data,
        'status_distribution': list(status_distribution),
        'popular_services': list(popular_services),
        'regional_performance': list(regional_performance),
        'hourly_distribution': list(hourly_distribution),
        'professional_performance': professional_performance
    })


@api_view(['GET'])
@permission_classes([IsAdminUser])
@swagger_auto_schema(
    operation_description="Get detailed revenue statistics for admin dashboard",
    responses={200: openapi.Response('Revenue statistics')}
)
def get_revenue_statistics(request):
    """
    Get detailed revenue statistics for admin
    """
    today = timezone.now().date()
    
    # Revenue trends (last 30 days)
    last_30_days = today - timedelta(days=30)
    revenue_data = []
    
    for i in range(30):
        date = last_30_days + timedelta(days=i)
        payments = Payment.objects.filter(
            created_at__date=date,
            status='succeeded'
        )
        revenue_data.append({
            'date': date.isoformat(),
            'revenue': float(payments.aggregate(total=Sum('amount'))['total'] or 0),
            'transactions': payments.count()
        })
    
    # Payment method distribution
    payment_methods = Payment.objects.filter(
        status='succeeded'
    ).values('payment_type').annotate(
        count=Count('id'),
        total_amount=Sum('amount')
    )
    
    # Revenue by region
    revenue_by_region = Payment.objects.filter(
        status='succeeded'
    ).values('booking__region__name').annotate(
        total_revenue=Sum('amount'),
        transaction_count=Count('id')
    )
    
    # Average transaction values
    avg_transaction = Payment.objects.filter(
        status='succeeded'
    ).aggregate(avg_amount=Avg('amount'))
    
    # Monthly comparison
    current_month = today.replace(day=1)
    prev_month = (current_month - timedelta(days=1)).replace(day=1)
    
    current_month_revenue = Payment.objects.filter(
        created_at__date__gte=current_month,
        status='succeeded'
    ).aggregate(total=Sum('amount'))['total'] or 0
    
    prev_month_revenue = Payment.objects.filter(
        created_at__date__gte=prev_month,
        created_at__date__lt=current_month,
        status='succeeded'
    ).aggregate(total=Sum('amount'))['total'] or 0
    
    # Failed payments analysis
    failed_payments = Payment.objects.filter(
        status='failed',
        created_at__date__gte=last_30_days
    ).count()
    
    total_payments = Payment.objects.filter(
        created_at__date__gte=last_30_days
    ).count()
    
    failure_rate = (failed_payments / max(total_payments, 1)) * 100
    
    return Response({
        'revenue_trends': revenue_data,
        'payment_methods': list(payment_methods),
        'revenue_by_region': list(revenue_by_region),
        'average_transaction': float(avg_transaction['avg_amount'] or 0),
        'monthly_comparison': {
            'current_month': float(current_month_revenue),
            'previous_month': float(prev_month_revenue),
            'growth_rate': ((float(current_month_revenue) - float(prev_month_revenue)) / max(float(prev_month_revenue), 1)) * 100
        },
        'payment_failure_rate': round(failure_rate, 2),
        'failed_payments_count': failed_payments
    })


@api_view(['POST'])
@permission_classes([IsAdminUser])
@swagger_auto_schema(
    operation_description="Reset user password (admin only)",
    request_body=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        properties={
            'user_id': openapi.Schema(type=openapi.TYPE_INTEGER),
            'new_password': openapi.Schema(type=openapi.TYPE_STRING),
        },
        required=['user_id', 'new_password']
    ),
    responses={200: 'Password reset successfully'}
)
def reset_user_password(request):
    """
    Reset user password (admin)
    """
    user_id = request.data.get('user_id')
    new_password = request.data.get('new_password')
    
    if not all([user_id, new_password]):
        return Response(
            {'error': 'user_id and new_password are required'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    try:
        user = User.objects.get(id=user_id)
        user.set_password(new_password)
        user.save()
        
        # Log admin activity
        AdminActivity.objects.create(
            admin_user=request.user,
            activity_type='user_action',
            description=f"Reset password for user: {user.email}",
            target_model='User',
            target_id=str(user.id)
        )
        
        # Send notification to user
        from notifications.tasks import send_email_notification
        send_email_notification.delay(
            user_id=user.id,
            subject='Password Reset - LabMyShare',
            template='emails/password_reset_admin.html',
            context={'user': user}
        )
        
        return Response({'message': 'Password reset successfully'})
        
    except User.DoesNotExist:
        return Response(
            {'error': 'User not found'},
            status=status.HTTP_404_NOT_FOUND
        )


@api_view(['POST'])
@permission_classes([IsAdminUser])
@swagger_auto_schema(
    operation_description="Generate impersonation token for user (admin only)",
    request_body=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        properties={
            'user_id': openapi.Schema(type=openapi.TYPE_INTEGER),
        },
        required=['user_id']
    ),
    responses={200: openapi.Response('Impersonation token generated')}
)
def impersonate_user(request):
    """
    Generate impersonation token for user (admin)
    """
    user_id = request.data.get('user_id')
    
    if not user_id:
        return Response(
            {'error': 'user_id is required'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    try:
        user = User.objects.get(id=user_id)
        
        # Generate token for user
        from rest_framework.authtoken.models import Token
        token, created = Token.objects.get_or_create(user=user)
        
        # Log admin activity
        AdminActivity.objects.create(
            admin_user=request.user,
            activity_type='user_action',
            description=f"Generated impersonation token for user: {user.email}",
            target_model='User',
            target_id=str(user.id)
        )
        
        return Response({
            'token': token.key,
            'user': {
                'id': user.id,
                'email': user.email,
                'name': user.get_full_name(),
                'user_type': user.user_type
            },
            'message': 'Use this token to impersonate the user'
        })
        
    except User.DoesNotExist:
        return Response(
            {'error': 'User not found'},
            status=status.HTTP_404_NOT_FOUND
        )


@api_view(['GET'])
@permission_classes([IsAdminUser])
@swagger_auto_schema(
    operation_description="Export data in various formats (admin only)",
    manual_parameters=[
        openapi.Parameter(
            'type', openapi.IN_QUERY,
            description="Export type (users, bookings, payments, professionals)",
            type=openapi.TYPE_STRING
        ),
        openapi.Parameter(
            'format', openapi.IN_QUERY,
            description="Export format (csv, json, excel)",
            type=openapi.TYPE_STRING
        ),
        openapi.Parameter(
            'date_from', openapi.IN_QUERY,
            description="Start date (YYYY-MM-DD)",
            type=openapi.TYPE_STRING
        ),
        openapi.Parameter(
            'date_to', openapi.IN_QUERY,
            description="End date (YYYY-MM-DD)",
            type=openapi.TYPE_STRING
        ),
    ],
    responses={200: 'Export initiated'}
)
def export_data(request):
    """
    Export data in various formats (admin)
    """
    export_type = request.GET.get('type', 'users')
    format_type = request.GET.get('format', 'csv')
    date_from = request.GET.get('date_from')
    date_to = request.GET.get('date_to')
    
    # Validate export type
    valid_types = ['users', 'bookings', 'payments', 'professionals', 'reviews']
    if export_type not in valid_types:
        return Response(
            {'error': f'Invalid export type. Must be one of: {", ".join(valid_types)}'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    # Validate format
    valid_formats = ['csv', 'json', 'excel']
    if format_type not in valid_formats:
        return Response(
            {'error': f'Invalid format. Must be one of: {", ".join(valid_formats)}'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    # Log admin activity
    AdminActivity.objects.create(
        admin_user=request.user,
        activity_type='system_configuration',
        description=f"Initiated data export: {export_type} in {format_type} format",
        new_data={
            'export_type': export_type,
            'format': format_type,
            'date_from': date_from,
            'date_to': date_to
        }
    )
    
    # In a real implementation, this would trigger an async task to generate the export
    # For now, returning a placeholder response
    
    return Response({
        'message': f'Export {export_type} in {format_type} format initiated',
        'export_type': export_type,
        'format': format_type,
        'status': 'processing',
        'estimated_time': '5-10 minutes',
        'note': 'You will receive an email when the export is ready for download'
    })


@api_view(['POST'])
@permission_classes([IsAdminUser])
@swagger_auto_schema(
    operation_description="Send maintenance notification to all users",
    request_body=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        properties={
            'title': openapi.Schema(type=openapi.TYPE_STRING),
            'message': openapi.Schema(type=openapi.TYPE_STRING),
            'scheduled_time': openapi.Schema(type=openapi.TYPE_STRING),
            'duration': openapi.Schema(type=openapi.TYPE_STRING),
            'send_email': openapi.Schema(type=openapi.TYPE_BOOLEAN),
        },
        required=['message']
    ),
    responses={200: 'Maintenance notification sent'}
)
def send_maintenance_notification(request):
    """
    Send maintenance notification to all users
    """
    title = request.data.get('title', 'Scheduled Maintenance')
    message = request.data.get('message')
    scheduled_time = request.data.get('scheduled_time')
    duration = request.data.get('duration', '1 hour')
    send_email = request.data.get('send_email', False)
    
    if not message:
        return Response(
            {'error': 'message is required'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    # Enhanced message with details
    full_message = f"{message}\n\nScheduled Time: {scheduled_time}\nExpected Duration: {duration}"
    
    # Send to all active users
    from notifications.tasks import create_notification, send_push_notification, send_email_notification
    
    users = User.objects.filter(is_active=True)
    count = 0
    
    for user in users:
        # Create in-app notification
        create_notification.delay(
            user_id=user.id,
            notification_type='system_announcement',
            title=title,
            message=full_message,
            data={
                'scheduled_time': scheduled_time,
                'duration': duration,
                'type': 'maintenance'
            }
        )
        
        # Send push notification
        send_push_notification.delay(
            user_id=user.id,
            title=title,
            body=message,
            data={
                'type': 'maintenance',
                'scheduled_time': scheduled_time
            }
        )
        
        # Send email if requested
        if send_email:
            send_email_notification.delay(
                user_id=user.id,
                subject=f'{title} - LabMyShare',
                template='emails/maintenance_notification.html',
                context={
                    'title': title,
                    'message': message,
                    'scheduled_time': scheduled_time,
                    'duration': duration
                }
            )
        
        count += 1
    
    # Log admin activity
    AdminActivity.objects.create(
        admin_user=request.user,
        activity_type='system_configuration',
        description=f"Sent maintenance notification to {count} users",
        new_data={
            'title': title,
            'message': message,
            'scheduled_time': scheduled_time,
            'duration': duration,
            'user_count': count,
            'email_sent': send_email
        }
    )
    
    return Response({
        'message': f'Maintenance notification sent to {count} users',
        'user_count': count,
        'push_sent': True,
        'email_sent': send_email
    })


@api_view(['GET'])
@permission_classes([IsAdminUser])
@swagger_auto_schema(
    operation_description="Get system health metrics",
    responses={200: openapi.Response('System health metrics')}
)
def get_system_health(request):
    """
    Get system health and performance metrics
    """
    from django.db import connection
    from django.core.cache import cache
    import time
    
    health_metrics = {
        'status': 'healthy',
        'timestamp': timezone.now().isoformat(),
        'checks': {}
    }
    
    # Database health check
    try:
        start_time = time.time()
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
        db_response_time = (time.time() - start_time) * 1000
        
        health_metrics['checks']['database'] = {
            'status': 'healthy',
            'response_time_ms': round(db_response_time, 2)
        }
    except Exception as e:
        health_metrics['checks']['database'] = {
            'status': 'unhealthy',
            'error': str(e)
        }
        health_metrics['status'] = 'degraded'
    
    # Cache health check
    try:
        start_time = time.time()
        cache.set('health_check', 'test', 10)
        cache.get('health_check')
        cache_response_time = (time.time() - start_time) * 1000
        
        health_metrics['checks']['cache'] = {
            'status': 'healthy',
            'response_time_ms': round(cache_response_time, 2)
        }
    except Exception as e:
        health_metrics['checks']['cache'] = {
            'status': 'unhealthy',
            'error': str(e)
        }
        health_metrics['status'] = 'degraded'
    
    # Queue health check (Celery)
    try:
        from celery import current_app
        inspect = current_app.control.inspect()
        stats = inspect.stats()
        
        if stats:
            active_workers = len(stats)
            health_metrics['checks']['queue'] = {
                'status': 'healthy',
                'active_workers': active_workers
            }
        else:
            health_metrics['checks']['queue'] = {
                'status': 'degraded',
                'message': 'No active workers'
            }
            health_metrics['status'] = 'degraded'
    except Exception as e:
        health_metrics['checks']['queue'] = {
            'status': 'unhealthy',
            'error': str(e)
        }
        health_metrics['status'] = 'degraded'
    
    # Performance metrics
    today = timezone.now().date()
    
    health_metrics['performance'] = {
        'active_users_today': User.objects.filter(
            last_login__date=today
        ).count(),
        'bookings_today': Booking.objects.filter(
            created_at__date=today
        ).count(),
        'payments_today': Payment.objects.filter(
            created_at__date=today
        ).count(),
        'avg_response_time': round((db_response_time + cache_response_time) / 2, 2)
    }
    
    return Response(health_metrics)


@api_view(['POST'])
@permission_classes([IsAdminUser])
@swagger_auto_schema(
    operation_description="Clear system cache",
    request_body=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        properties={
            'cache_type': openapi.Schema(
                type=openapi.TYPE_STRING,
                enum=['all', 'users', 'services', 'regions', 'professionals']
            ),
        }
    ),
    responses={200: 'Cache cleared'}
)
def clear_cache(request):
    """
    Clear system cache (admin)
    """
    cache_type = request.data.get('cache_type', 'all')
    
    from django.core.cache import cache
    
    if cache_type == 'all':
        cache.clear()
        message = 'All cache cleared'
    else:
        # Clear specific cache patterns
        cache_patterns = {
            'users': 'user:*',
            'services': 'services:*',
            'regions': 'regions:*',
            'professionals': 'professionals:*'
        }
        
        pattern = cache_patterns.get(cache_type)
        if pattern:
            # In a real implementation, you'd use Redis commands to delete by pattern
            # For now, we'll clear all cache
            cache.clear()
            message = f'{cache_type.title()} cache cleared'
        else:
            return Response(
                {'error': 'Invalid cache type'},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    # Log admin activity
    AdminActivity.objects.create(
        admin_user=request.user,
        activity_type='system_configuration',
        description=f"Cleared cache: {cache_type}",
        new_data={'cache_type': cache_type}
    )
    
    return Response({'message': message})


@api_view(['GET'])
@permission_classes([IsAdminUser])
@swagger_auto_schema(
    operation_description="Get admin activity log",
    manual_parameters=[
        openapi.Parameter(
            'admin_user', openapi.IN_QUERY,
            description="Filter by admin user ID",
            type=openapi.TYPE_INTEGER
        ),
        openapi.Parameter(
            'activity_type', openapi.IN_QUERY,
            description="Filter by activity type",
            type=openapi.TYPE_STRING
        ),
        openapi.Parameter(
            'days', openapi.IN_QUERY,
            description="Number of days to look back (default: 30)",
            type=openapi.TYPE_INTEGER
        ),
    ],
    responses={200: 'Admin activity log'}
)
def get_admin_activity_log(request):
    """
    Get admin activity log with filtering
    """
    admin_user_id = request.GET.get('admin_user')
    activity_type = request.GET.get('activity_type')
    days = int(request.GET.get('days', 30))
    
    # Filter activities
    activities = AdminActivity.objects.all()
    
    if admin_user_id:
        activities = activities.filter(admin_user_id=admin_user_id)
    
    if activity_type:
        activities = activities.filter(activity_type=activity_type)
    
    # Date filter
    since = timezone.now() - timedelta(days=days)
    activities = activities.filter(created_at__gte=since)
    
    # Serialize activities
    activity_data = []
    for activity in activities.order_by('-created_at')[:100]:  # Limit to 100 recent
        activity_data.append({
            'id': activity.id,
            'admin_user': activity.admin_user.get_full_name(),
            'admin_email': activity.admin_user.email,
            'activity_type': activity.activity_type,
            'description': activity.description,
            'target_model': activity.target_model,
            'target_id': activity.target_id,
            'ip_address': activity.ip_address,
            'created_at': activity.created_at.isoformat()
        })
    
    return Response({
        'activities': activity_data,
        'total_count': activities.count(),
        'filter_applied': {
            'admin_user_id': admin_user_id,
            'activity_type': activity_type,
            'days': days
        }
    })