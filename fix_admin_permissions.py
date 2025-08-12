#!/usr/bin/env python3
"""
Fix admin user permissions
"""
import os
import sys
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'labmyshare.local_settings')
django.setup()

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType

User = get_user_model()

def fix_admin_permissions():
    """Fix admin user permissions"""
    print("🔧 Fixing admin user permissions...")
    
    # Get admin user
    admin_user = User.objects.get(email='admin@labmyshare.com')
    
    # Make sure user is superuser and staff
    admin_user.is_superuser = True
    admin_user.is_staff = True
    admin_user.save()
    
    print(f"✅ Admin user updated: {admin_user.email}")
    print(f"   is_superuser: {admin_user.is_superuser}")
    print(f"   is_staff: {admin_user.is_staff}")
    
    # Get all permissions
    all_permissions = Permission.objects.all()
    print(f"📋 Found {all_permissions.count()} total permissions")
    
    # Assign all permissions to admin user
    admin_user.user_permissions.set(all_permissions)
    
    print(f"✅ Assigned {all_permissions.count()} permissions to admin user")
    
    # Verify permissions
    user_permissions = admin_user.user_permissions.all()
    print(f"✅ Admin user now has {user_permissions.count()} permissions")
    
    print("🎉 Admin permissions fixed!")

if __name__ == "__main__":
    fix_admin_permissions() 