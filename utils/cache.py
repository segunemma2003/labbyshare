"""
Caching utilities for high-performance operations
"""
from django.core.cache import cache
from django.conf import settings
from functools import wraps
import hashlib
import json


def cache_key_generator(prefix, *args, **kwargs):
    """Generate cache key from arguments"""
    key_data = f"{prefix}:{args}:{sorted(kwargs.items())}"
    return hashlib.md5(key_data.encode()).hexdigest()


def cached_function(timeout=3600, prefix=None):
    """Decorator for caching function results"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Generate cache key
            cache_prefix = prefix or f"{func.__module__}.{func.__name__}"
            cache_key = cache_key_generator(cache_prefix, *args, **kwargs)
            
            # Try to get from cache
            result = cache.get(cache_key)
            if result is not None:
                return result
            
            # Execute function and cache result
            result = func(*args, **kwargs)
            cache.set(cache_key, result, timeout)
            return result
        return wrapper
    return decorator


def invalidate_cache_pattern(pattern):
    """Invalidate cache keys matching pattern"""
    try:
        from django_redis import get_redis_connection
        redis_conn = get_redis_connection("default")
        keys = redis_conn.keys(f"*{pattern}*")
        if keys:
            redis_conn.delete(*keys)
        return len(keys)
    except:
        return 0


class RegionAwareCache:
    """Region-aware caching utility"""
    
    @staticmethod
    def get_key(region, key_template, *args):
        """Generate region-specific cache key"""
        region_code = region.code if region else 'global'
        return key_template.format(region_code, *args)
    
    @staticmethod
    def set_regional(region, key_template, value, timeout=3600, *args):
        """Set cache value for specific region"""
        cache_key = RegionAwareCache.get_key(region, key_template, *args)
        cache.set(cache_key, value, timeout)
    
    @staticmethod
    def get_regional(region, key_template, *args):
        """Get cache value for specific region"""
        cache_key = RegionAwareCache.get_key(region, key_template, *args)
        return cache.get(cache_key)
    
    @staticmethod
    def invalidate_regional(region, key_template, *args):
        """Invalidate regional cache"""
        cache_key = RegionAwareCache.get_key(region, key_template, *args)
        cache.delete(cache_key)