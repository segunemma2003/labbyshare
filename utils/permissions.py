from rest_framework import permissions


class IsAdminUser(permissions.BasePermission):
    """
    Permission for admin users only
    """
    def has_permission(self, request, view):
        return (
            request.user and
            request.user.is_authenticated and
            request.user.user_type in ['admin', 'super_admin']
        )


class IsOwnerOrReadOnly(permissions.BasePermission):
    """
    Custom permission to only allow owners of an object to edit it.
    """
    def has_object_permission(self, request, view, obj):
        # Read permissions for any request
        if request.method in permissions.SAFE_METHODS:
            return True
        
        # Write permissions only to the owner
        if hasattr(obj, 'user'):
            return obj.user == request.user
        elif hasattr(obj, 'customer'):
            return obj.customer == request.user
        
        return False


class IsProfessionalOrCustomer(permissions.BasePermission):
    """
    Permission for professional or customer access
    """
    def has_permission(self, request, view):
        return (
            request.user and
            request.user.is_authenticated and
            request.user.user_type in ['professional', 'customer']
        )


class IsVerifiedProfessional(permissions.BasePermission):
    """
    Permission for verified professionals only
    """
    def has_permission(self, request, view):
        return (
            request.user and
            request.user.is_authenticated and
            request.user.user_type == 'professional' and
            hasattr(request.user, 'professional_profile') and
            request.user.professional_profile.is_verified
        )


class IsInSameRegion(permissions.BasePermission):
    """
    Check if user is in the same region as the object
    """
    def has_object_permission(self, request, view, obj):
        request_region = getattr(request, 'region', None)
        
        # Get object region
        if hasattr(obj, 'region'):
            object_region = obj.region
        elif hasattr(obj, 'current_region'):
            object_region = obj.current_region
        else:
            return True  # No region restriction
        
        return request_region == object_region