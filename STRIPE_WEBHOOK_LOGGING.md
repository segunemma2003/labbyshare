# Stripe Webhook Logging Enhancement

## Overview

Enhanced logging for Stripe webhook responses to provide better visibility and debugging capabilities.

## What Was Implemented

### 1. Enhanced Webhook Entry Point (`payments/views.py`)

- **Comprehensive incoming webhook logging** with detailed request information
- **Sanitized payload logging** (sensitive data redacted)
- **Step-by-step processing logs** with emojis for easy identification
- **Detailed error logging** with full tracebacks
- **Visual separators** for easy log reading

### 2. Enhanced Webhook Processing (`payments/services.py`)

- **Detailed event processing logs** in `handle_webhook_event()`
- **Enhanced payment success logging** in `handle_payment_success()`
- **Enhanced payment failure logging** in `handle_payment_failure()`
- **Step-by-step operation tracking** with status indicators
- **Comprehensive error handling** with full stack traces

### 3. Django Logging Configuration (`labmyshare/settings.py`)

- **Dedicated `stripe_webhook` logger** configuration
- **Production file logging** support
- **Proper log level configuration** (INFO for webhooks)

### 4. Monitoring Tools

- **Management command**: `python manage.py monitor_webhooks`
- **Test script**: `test_webhook_logging.py`
- **Database tracking**: `PaymentWebhookEvent` model

## Log Locations

### Development

- **Console output**: All webhook logs appear in console
- **File**: `logs/stripe_webhooks.log` (if file logging enabled)

### Production

- **Console**: Standard Django logging
- **File**: `logs/django.log` (includes webhook logs)
- **Error file**: `logs/django_error.log` (error-level logs only)

## Usage

### Monitor Webhooks

```bash
# Monitor last 24 hours
python manage.py monitor_webhooks

# Monitor last 48 hours
python manage.py monitor_webhooks --hours 48

# Show only errors
python manage.py monitor_webhooks --show-errors

# Show unprocessed events
python manage.py monitor_webhooks --show-unprocessed

# Show log file entries
python manage.py monitor_webhooks --log-file
```

### Test Logging

```bash
python test_webhook_logging.py
```

## Log Format Examples

### Incoming Webhook

```
================================================================================
STRIPE WEBHOOK RECEIVED
================================================================================
Request Method: POST
Content Type: application/json
Content Length: 1234 bytes
Stripe Signature Header: whsec_abc123...
Request Headers: {'content-type': 'application/json', ...}
Webhook Payload: {"id": "evt_123", "type": "payment_intent.succeeded", ...}
Verifying webhook signature...
✅ Webhook signature verified successfully
Event ID: evt_123456789
Event Type: payment_intent.succeeded
Event Created: 1640995200
Processing webhook event...
```

### Payment Processing

```
🔍 Processing webhook event: evt_123456789 (payment_intent.succeeded)
📝 Created new webhook event record for evt_123456789
🔄 Processing event type: payment_intent.succeeded
💰 Processing payment success for intent: pi_123456789
🎉 Starting payment success processing for intent: pi_123456789
📡 Retrieving payment intent from Stripe...
✅ Retrieved payment intent: status=succeeded, amount=2000
🔍 Looking for payment record with intent ID: pi_123456789
📋 Payment details found:
   - Payment ID: 123
   - Booking ID: book_abc123
   - Payment type: full
   - Payment amount: 20.00
   - Booking total: 20.00
   - Current booking payment status: pending
   - Stripe amount: 20.00
🔍 Amount verification:
   - Server amount: 20.00
   - Stripe amount: 20.00
   - Difference: 0.00
✅ Amount verification passed
💾 Updating payment status to 'completed'...
✅ Payment status updated successfully
🔄 Updating booking payment status from 'pending'...
💰 Setting booking book_abc123 to fully_paid (full payment)
✅ Booking payment status updated: pending -> fully_paid
📧 Sending payment confirmation notifications...
✅ Payment confirmation notifications sent
🎉 Payment success processing completed for booking book_abc123
✅ Marked webhook event evt_123456789 as processed
🎯 Webhook processing result: {'success': True, ...}
✅ Webhook processed successfully: Event processed
================================================================================
```

## Benefits

1. **Complete Visibility**: Every step of webhook processing is logged
2. **Easy Debugging**: Clear error messages with full context
3. **Performance Monitoring**: Track processing times and success rates
4. **Security**: Sensitive data is automatically redacted
5. **Production Ready**: Proper file logging and rotation
6. **Monitoring Tools**: Built-in commands for monitoring webhook health

## Troubleshooting

### If webhooks aren't being received:

1. Check the webhook endpoint URL in Stripe dashboard
2. Verify the webhook secret is correct
3. Check server logs for incoming requests
4. Use `monitor_webhooks` command to see recent activity

### If webhooks are failing:

1. Check the detailed error logs
2. Verify payment records exist in database
3. Check Stripe API connectivity
4. Review webhook event processing logs

### If logs aren't appearing:

1. Verify logging configuration in settings
2. Check log file permissions
3. Ensure the `stripe_webhook` logger is properly configured
4. Test with the provided test script

## Overview

Enhanced logging for Stripe webhook responses to provide better visibility and debugging capabilities.

## What Was Implemented

### 1. Enhanced Webhook Entry Point (`payments/views.py`)

- **Comprehensive incoming webhook logging** with detailed request information
- **Sanitized payload logging** (sensitive data redacted)
- **Step-by-step processing logs** with emojis for easy identification
- **Detailed error logging** with full tracebacks
- **Visual separators** for easy log reading

### 2. Enhanced Webhook Processing (`payments/services.py`)

- **Detailed event processing logs** in `handle_webhook_event()`
- **Enhanced payment success logging** in `handle_payment_success()`
- **Enhanced payment failure logging** in `handle_payment_failure()`
- **Step-by-step operation tracking** with status indicators
- **Comprehensive error handling** with full stack traces

### 3. Django Logging Configuration (`labmyshare/settings.py`)

- **Dedicated `stripe_webhook` logger** configuration
- **Production file logging** support
- **Proper log level configuration** (INFO for webhooks)

### 4. Monitoring Tools

- **Management command**: `python manage.py monitor_webhooks`
- **Test script**: `test_webhook_logging.py`
- **Database tracking**: `PaymentWebhookEvent` model

## Log Locations

### Development

- **Console output**: All webhook logs appear in console
- **File**: `logs/stripe_webhooks.log` (if file logging enabled)

### Production

- **Console**: Standard Django logging
- **File**: `logs/django.log` (includes webhook logs)
- **Error file**: `logs/django_error.log` (error-level logs only)

## Usage

### Monitor Webhooks

```bash
# Monitor last 24 hours
python manage.py monitor_webhooks

# Monitor last 48 hours
python manage.py monitor_webhooks --hours 48

# Show only errors
python manage.py monitor_webhooks --show-errors

# Show unprocessed events
python manage.py monitor_webhooks --show-unprocessed

# Show log file entries
python manage.py monitor_webhooks --log-file
```

### Test Logging

```bash
python test_webhook_logging.py
```

## Log Format Examples

### Incoming Webhook

```
================================================================================
STRIPE WEBHOOK RECEIVED
================================================================================
Request Method: POST
Content Type: application/json
Content Length: 1234 bytes
Stripe Signature Header: whsec_abc123...
Request Headers: {'content-type': 'application/json', ...}
Webhook Payload: {"id": "evt_123", "type": "payment_intent.succeeded", ...}
Verifying webhook signature...
✅ Webhook signature verified successfully
Event ID: evt_123456789
Event Type: payment_intent.succeeded
Event Created: 1640995200
Processing webhook event...
```

### Payment Processing

```
🔍 Processing webhook event: evt_123456789 (payment_intent.succeeded)
📝 Created new webhook event record for evt_123456789
🔄 Processing event type: payment_intent.succeeded
💰 Processing payment success for intent: pi_123456789
🎉 Starting payment success processing for intent: pi_123456789
📡 Retrieving payment intent from Stripe...
✅ Retrieved payment intent: status=succeeded, amount=2000
🔍 Looking for payment record with intent ID: pi_123456789
📋 Payment details found:
   - Payment ID: 123
   - Booking ID: book_abc123
   - Payment type: full
   - Payment amount: 20.00
   - Booking total: 20.00
   - Current booking payment status: pending
   - Stripe amount: 20.00
🔍 Amount verification:
   - Server amount: 20.00
   - Stripe amount: 20.00
   - Difference: 0.00
✅ Amount verification passed
💾 Updating payment status to 'completed'...
✅ Payment status updated successfully
🔄 Updating booking payment status from 'pending'...
💰 Setting booking book_abc123 to fully_paid (full payment)
✅ Booking payment status updated: pending -> fully_paid
📧 Sending payment confirmation notifications...
✅ Payment confirmation notifications sent
🎉 Payment success processing completed for booking book_abc123
✅ Marked webhook event evt_123456789 as processed
🎯 Webhook processing result: {'success': True, ...}
✅ Webhook processed successfully: Event processed
================================================================================
```

## Benefits

1. **Complete Visibility**: Every step of webhook processing is logged
2. **Easy Debugging**: Clear error messages with full context
3. **Performance Monitoring**: Track processing times and success rates
4. **Security**: Sensitive data is automatically redacted
5. **Production Ready**: Proper file logging and rotation
6. **Monitoring Tools**: Built-in commands for monitoring webhook health

## Troubleshooting

### If webhooks aren't being received:

1. Check the webhook endpoint URL in Stripe dashboard
2. Verify the webhook secret is correct
3. Check server logs for incoming requests
4. Use `monitor_webhooks` command to see recent activity

### If webhooks are failing:

1. Check the detailed error logs
2. Verify payment records exist in database
3. Check Stripe API connectivity
4. Review webhook event processing logs

### If logs aren't appearing:

1. Verify logging configuration in settings
2. Check log file permissions
3. Ensure the `stripe_webhook` logger is properly configured
4. Test with the provided test script
