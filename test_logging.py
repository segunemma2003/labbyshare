#!/usr/bin/env python3
"""
Test script to verify logging functionality
"""
import os
import sys
import django
import logging

# Add the project directory to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'labmyshare.settings')
django.setup()

def test_logging():
    """Test the logging functionality"""
    print("🧪 Testing Logging Configuration")
    
    # Test different loggers
    loggers_to_test = [
        'django',
        'admin_panel',
        'professionals',
        'services',
        'bookings',
        'payments',
    ]
    
    for logger_name in loggers_to_test:
        logger = logging.getLogger(logger_name)
        print(f"\n📝 Testing logger: {logger_name}")
        
        # Test different log levels
        logger.debug(f"DEBUG message from {logger_name}")
        logger.info(f"INFO message from {logger_name}")
        logger.warning(f"WARNING message from {logger_name}")
        logger.error(f"ERROR message from {logger_name}")
    
    # Test admin_panel specifically
    admin_logger = logging.getLogger('admin_panel')
    admin_logger.info("🔍 ADMIN PANEL LOGGING TEST")
    admin_logger.debug("🔍 ADMIN PANEL DEBUG TEST")
    admin_logger.warning("⚠️ ADMIN PANEL WARNING TEST")
    admin_logger.error("❌ ADMIN PANEL ERROR TEST")
    
    print("\n✅ Logging test completed!")
    print("Check your server logs to see if these messages appear.")

if __name__ == "__main__":
    test_logging() 