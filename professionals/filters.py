import django_filters
from .models import Professional


class ProfessionalFilter(django_filters.FilterSet):
    """
    Professional filtering for search and listing
    """
    service = django_filters.NumberFilter(
        field_name='services',
        lookup_expr='exact'
    )
    min_rating = django_filters.NumberFilter(
        field_name='rating',
        lookup_expr='gte'
    )
    max_rating = django_filters.NumberFilter(
        field_name='rating',
        lookup_expr='lte'
    )
    min_experience = django_filters.NumberFilter(
        field_name='experience_years',
        lookup_expr='gte'
    )
    verified_only = django_filters.BooleanFilter(
        field_name='is_verified'
    )
    region = django_filters.NumberFilter(
        field_name='regions',
        lookup_expr='exact'
    )
    
    class Meta:
        model = Professional
        fields = [
            'service', 'min_rating', 'max_rating', 
            'min_experience', 'verified_only', 'region'
        ]
