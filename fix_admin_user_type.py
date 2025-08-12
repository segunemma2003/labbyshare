#!/usr/bin/env python3
"""
Fix admin user type
"""
import os
import sys
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'labmyshare.local_settings')
django.setup()

from django.contrib.auth import get_user_model

User = get_user_model()

def fix_admin_user_type():
    """Fix admin user type"""
    print("🔧 Fixing admin user type...")
    
    # Get admin user
    admin_user = User.objects.get(email='admin@labmyshare.com')
    
    # Change user_type to admin
    admin_user.user_type = 'admin'
    admin_user.save()
    
    print(f"✅ Admin user updated: {admin_user.email}")
    print(f"   user_type: {admin_user.user_type}")
    print(f"   is_superuser: {admin_user.is_superuser}")
    print(f"   is_staff: {admin_user.is_staff}")
    
    print("🎉 Admin user type fixed!")

if __name__ == "__main__":
    fix_admin_user_type() 