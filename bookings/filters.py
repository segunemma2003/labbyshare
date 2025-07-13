import django_filters
from .models import Booking


class BookingFilter(django_filters.FilterSet):
    """
    Booking filtering
    """
    status = django_filters.CharFilter(field_name='status')
    payment_status = django_filters.CharFilter(field_name='payment_status')
    scheduled_date = django_filters.DateFilter(field_name='scheduled_date')
    date_from = django_filters.DateFilter(field_name='scheduled_date', lookup_expr='gte')
    date_to = django_filters.DateFilter(field_name='scheduled_date', lookup_expr='lte')
    upcoming = django_filters.BooleanFilter(method='filter_upcoming')
    
    class Meta:
        model = Booking
        fields = ['status', 'payment_status', 'scheduled_date', 'date_from', 'date_to', 'upcoming']
    
    def filter_upcoming(self, queryset, name, value):
        if value:
            from django.utils import timezone
            return queryset.filter(
                scheduled_date__gte=timezone.now().date(),
                status__in=['confirmed', 'pending']
            )
        return queryset