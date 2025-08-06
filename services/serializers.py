from rest_framework import serializers
from decimal import Decimal
from .models import Category, Service, AddOn, RegionalPricing, ServiceImage, ServiceReview


class CategorySerializer(serializers.ModelSerializer):
    """
    Category serializer for services
    """
    services_count = serializers.SerializerMethodField()
    addons = serializers.SerializerMethodField()
    
    class Meta:
        model = Category
        fields = [
            'id', 'name', 'description', 'icon', 'sort_order', 
            'services_count', 'slug', 'addons', 'is_featured'
        ]
    
    def get_services_count(self, obj):
        return obj.services.filter(is_active=True).count()

    def get_addons(self, obj):
        return AddOnSerializer(obj.addons.filter(is_active=True), many=True).data


class AddOnSerializer(serializers.ModelSerializer):
    """
    Service add-on serializer
    """
    region = serializers.StringRelatedField()
    categories = serializers.PrimaryKeyRelatedField(many=True, read_only=True)
    class Meta:
        model = AddOn
        fields = [
            'id', 'name', 'description', 'price', 'duration_minutes',
            'max_quantity', 'region', 'categories', 'is_active', 'created_at', 'updated_at'
        ]


class AddOnListSerializer(serializers.ModelSerializer):
    """
    Service add-on list serializer (lightweight for listings)
    """
    region = serializers.StringRelatedField()
    categories = serializers.PrimaryKeyRelatedField(many=True, read_only=True)
    class Meta:
        model = AddOn
        fields = [
            'id', 'name', 'description', 'price', 'duration_minutes',
            'max_quantity', 'region', 'categories', 'is_active', 'created_at', 'updated_at'
        ]


class ServiceImageSerializer(serializers.ModelSerializer):
    """
    Service image serializer
    """
    class Meta:
        model = ServiceImage
        fields = ['id', 'image', 'alt_text', 'is_primary', 'sort_order']


class ServiceListSerializer(serializers.ModelSerializer):
    """
    Service list serializer (lightweight for listings)
    """
    category_name = serializers.CharField(source='category.name', read_only=True)
    regional_price = serializers.SerializerMethodField()
    primary_image = serializers.SerializerMethodField()
    
    class Meta:
        model = Service
        fields = [
            'id', 'name', 'description', 'base_price', 'regional_price',
            'duration_minutes', 'category_name', 'is_featured', 
            'primary_image', 'sort_order'
        ]
    
    def get_regional_price(self, obj):
        region = self.context.get('region')
        if region:
            return float(obj.get_regional_price(region))
        return float(obj.base_price)
    
    def get_primary_image(self, obj):
        primary_image = obj.images.filter(is_primary=True).first()
        if primary_image:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(primary_image.image.url)
        return None


class ServiceDetailSerializer(serializers.ModelSerializer):
    """
    Detailed service serializer
    """
    category = CategorySerializer(read_only=True)
    regional_price = serializers.SerializerMethodField()
    promotional_price = serializers.SerializerMethodField()
    addons = serializers.SerializerMethodField()
    images = ServiceImageSerializer(many=True, read_only=True)
    reviews_summary = serializers.SerializerMethodField()
    professionals_count = serializers.SerializerMethodField()
    
    class Meta:
        model = Service
        fields = [
            'id', 'name', 'description', 'base_price', 'regional_price',
            'promotional_price', 'duration_minutes', 'preparation_time',
            'cleanup_time', 'category', 'addons', 'images', 'is_featured',
            'reviews_summary', 'professionals_count', 'slug'
        ]
    
    def get_regional_price(self, obj):
        region = self.context.get('region')
        if region:
            try:
                regional_pricing = obj.regional_pricing.get(region=region, is_active=True)
                return float(regional_pricing.get_current_price())
            except RegionalPricing.DoesNotExist:
                pass
        return float(obj.base_price)
    
    def get_promotional_price(self, obj):
        region = self.context.get('region')
        if region:
            try:
                regional_pricing = obj.regional_pricing.get(region=region, is_active=True)
                current_price = regional_pricing.get_current_price()
                if current_price != regional_pricing.price:
                    return float(current_price)
            except RegionalPricing.DoesNotExist:
                pass
        return None
    
    def get_addons(self, obj):
        addons = obj.category.addons.filter(is_active=True)
        return AddOnSerializer(addons, many=True).data
    
    def get_reviews_summary(self, obj):
        reviews = obj.reviews.filter(is_published=True)
        if reviews.exists():
            from django.db.models import Avg
            avg_rating = reviews.aggregate(avg=Avg('rating'))['avg']
            return {
                'average_rating': round(avg_rating, 2) if avg_rating else 0,
                'total_reviews': reviews.count(),
                'rating_distribution': {
                    '5': reviews.filter(rating=5).count(),
                    '4': reviews.filter(rating=4).count(),
                    '3': reviews.filter(rating=3).count(),
                    '2': reviews.filter(rating=2).count(),
                    '1': reviews.filter(rating=1).count(),
                }
            }
        return {
            'average_rating': 0,
            'total_reviews': 0,
            'rating_distribution': {'5': 0, '4': 0, '3': 0, '2': 0, '1': 0}
        }
    
    def get_professionals_count(self, obj):
        region = self.context.get('region')
        if region:
            return obj.professionals.filter(
                regions=region,
                is_active=True,
                is_verified=True
            ).count()
        return 0


class ServiceSerializer(ServiceListSerializer):
    """
    Standard service serializer (alias for list serializer)
    """
    pass


class ServiceReviewSerializer(serializers.ModelSerializer):
    """
    Service review serializer
    """
    user_name = serializers.CharField(source='user.get_full_name', read_only=True)
    
    class Meta:
        model = ServiceReview
        fields = [
            'id', 'user_name', 'rating', 'comment', 'is_verified',
            'created_at'
        ]


class VideoUploadSerializer(serializers.Serializer):
    video = serializers.FileField()
    title = serializers.CharField(required=False, max_length=255)
    description = serializers.CharField(required=False, allow_blank=True)
