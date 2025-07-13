from rest_framework import serializers
from django.db import models
from .models import Region, RegionalSettings


class RegionSerializer(serializers.ModelSerializer):
    """
    Region serializer for basic region information
    """
    class Meta:
        model = Region
        fields = [
            'id', 'code', 'name', 'currency', 'currency_symbol', 
            'timezone', 'country_code', 'business_start_time', 
            'business_end_time', 'is_active'
        ]


class RegionalSettingsSerializer(serializers.ModelSerializer):
    """
    Regional settings serializer
    """
    value_parsed = serializers.SerializerMethodField()
    
    class Meta:
        model = RegionalSettings
        fields = [
            'id', 'key', 'value', 'value_parsed', 'value_type', 
            'description', 'created_at', 'updated_at'
        ]
    
    def get_value_parsed(self, obj):
        """Return parsed value based on type"""
        return obj.get_value()


class RegionDetailSerializer(serializers.ModelSerializer):
    """
    Detailed region information with settings
    """
    settings = RegionalSettingsSerializer(many=True, read_only=True)
    services_count = serializers.SerializerMethodField()
    professionals_count = serializers.SerializerMethodField()
    
    class Meta:
        model = Region
        fields = [
            'id', 'code', 'name', 'currency', 'currency_symbol',
            'timezone', 'country_code', 'default_tax_rate',
            'business_start_time', 'business_end_time', 
            'support_email', 'support_phone', 'is_active',
            'settings', 'services_count', 'professionals_count',
            'created_at', 'updated_at'
        ]
    
    def get_services_count(self, obj):
        """Get count of active services in this region"""
        return obj.categories.filter(is_active=True).aggregate(
            total=models.Count('services', filter=models.Q(services__is_active=True))
        )['total'] or 0
    
    def get_professionals_count(self, obj):
        """Get count of active professionals in this region"""
        return obj.professionals.filter(is_active=True, is_verified=True).count()