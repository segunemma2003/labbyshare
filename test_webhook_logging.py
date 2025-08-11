#!/usr/bin/env python3
"""
Test script to verify Stripe webhook logging functionality
"""
import os
import sys
import django
import logging
from datetime import datetime

# Add the project directory to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'labmyshare.settings')
django.setup()

def test_webhook_logging():
    """Test the webhook logging functionality"""
    
    # Get the stripe webhook logger
    stripe_webhook_logger = logging.getLogger('stripe_webhook')
    
    print("🧪 Testing Stripe Webhook Logging")
    print("=" * 50)
    
    # Test basic logging
    stripe_webhook_logger.info("=" * 80)
    stripe_webhook_logger.info("TEST WEBHOOK LOGGING")
    stripe_webhook_logger.info("=" * 80)
    stripe_webhook_logger.info(f"Test timestamp: {datetime.now()}")
    stripe_webhook_logger.info("This is a test webhook log entry")
    
    # Test different log levels
    stripe_webhook_logger.debug("Debug message (should not appear with INFO level)")
    stripe_webhook_logger.info("Info message")
    stripe_webhook_logger.warning("Warning message")
    stripe_webhook_logger.error("Error message")
    
    # Test webhook-like data
    test_webhook_data = {
        "id": "evt_test_123456789",
        "type": "payment_intent.succeeded",
        "created": int(datetime.now().timestamp()),
        "data": {
            "object": {
                "id": "pi_test_123456789",
                "amount": 2000,
                "currency": "gbp",
                "status": "succeeded"
            }
        }
    }
    
    stripe_webhook_logger.info(f"Test webhook event: {test_webhook_data['id']} ({test_webhook_data['type']})")
    stripe_webhook_logger.info("=" * 80)
    
    print("✅ Webhook logging test completed!")
    print("\n📋 Check the following locations for logs:")
    print("   - Console output (above)")
    print("   - logs/stripe_webhooks.log (if file logging is enabled)")
    print("   - logs/django.log (in production)")
    
    # Check if log file exists
    log_file = os.path.join(os.path.dirname(__file__), 'logs', 'stripe_webhooks.log')
    if os.path.exists(log_file):
        print(f"   - Found log file: {log_file}")
        with open(log_file, 'r') as f:
            lines = f.readlines()
            print(f"   - Log file contains {len(lines)} lines")
    else:
        print(f"   - Log file not found: {log_file}")

if __name__ == "__main__":
    test_webhook_logging() 