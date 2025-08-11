from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
import os
import json
from payments.models import PaymentWebhookEvent, Payment


class Command(BaseCommand):
    help = 'Monitor Stripe webhook activity and logs'

    def add_arguments(self, parser):
        parser.add_argument(
            '--hours',
            type=int,
            default=24,
            help='Number of hours to look back (default: 24)'
        )
        parser.add_argument(
            '--show-errors',
            action='store_true',
            help='Show only webhook events with errors'
        )
        parser.add_argument(
            '--show-unprocessed',
            action='store_true',
            help='Show only unprocessed webhook events'
        )
        parser.add_argument(
            '--log-file',
            action='store_true',
            help='Show recent entries from stripe_webhooks.log file'
        )

    def handle(self, *args, **options):
        hours = options['hours']
        show_errors = options['show_errors']
        show_unprocessed = options['show_unprocessed']
        show_log_file = options['log_file']
        
        cutoff_time = timezone.now() - timedelta(hours=hours)
        
        self.stdout.write(self.style.SUCCESS(f"🔍 Monitoring Stripe webhooks (last {hours} hours)"))
        self.stdout.write("=" * 80)
        
        # Check webhook events in database
        if show_errors:
            events = PaymentWebhookEvent.objects.filter(
                created_at__gte=cutoff_time,
                processing_error__isnull=False
            ).exclude(processing_error='')
        elif show_unprocessed:
            events = PaymentWebhookEvent.objects.filter(
                created_at__gte=cutoff_time,
                processed=False
            )
        else:
            events = PaymentWebhookEvent.objects.filter(created_at__gte=cutoff_time)
        
        self.stdout.write(f"📊 Found {events.count()} webhook events")
        
        if events.exists():
            self.stdout.write("\n📋 Recent Webhook Events:")
            self.stdout.write("-" * 80)
            
            for event in events.order_by('-created_at')[:20]:  # Show last 20
                status_icon = "✅" if event.processed else "⏳"
                error_icon = "❌" if event.processing_error else ""
                
                self.stdout.write(
                    f"{status_icon} {event.stripe_event_id} | "
                    f"{event.event_type} | "
                    f"{event.created_at.strftime('%Y-%m-%d %H:%M:%S')} | "
                    f"{'Processed' if event.processed else 'Pending'}"
                )
                
                if event.processing_error:
                    self.stdout.write(f"   {error_icon} Error: {event.processing_error}")
        
        # Check recent payments
        recent_payments = Payment.objects.filter(
            created_at__gte=cutoff_time
        ).order_by('-created_at')
        
        self.stdout.write(f"\n💰 Recent Payments ({recent_payments.count()}):")
        self.stdout.write("-" * 80)
        
        for payment in recent_payments[:10]:  # Show last 10
            status_icon = {
                'pending': '⏳',
                'completed': '✅',
                'failed': '❌',
                'cancelled': '🚫'
            }.get(payment.status, '❓')
            
            self.stdout.write(
                f"{status_icon} {payment.payment_id} | "
                f"{payment.payment_type} | "
                f"{payment.amount} {payment.currency} | "
                f"{payment.status} | "
                f"{payment.created_at.strftime('%Y-%m-%d %H:%M:%S')}"
            )
        
        # Show log file entries if requested
        if show_log_file:
            log_file = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))), 'logs', 'stripe_webhooks.log')
            
            if os.path.exists(log_file):
                self.stdout.write(f"\n📄 Recent Log Entries from {log_file}:")
                self.stdout.write("-" * 80)
                
                try:
                    with open(log_file, 'r') as f:
                        lines = f.readlines()
                        # Show last 20 lines
                        for line in lines[-20:]:
                            self.stdout.write(line.rstrip())
                except Exception as e:
                    self.stdout.write(self.style.ERROR(f"Error reading log file: {e}"))
            else:
                self.stdout.write(self.style.WARNING(f"Log file not found: {log_file}"))
        
        # Summary statistics
        total_events = PaymentWebhookEvent.objects.filter(created_at__gte=cutoff_time).count()
        processed_events = PaymentWebhookEvent.objects.filter(created_at__gte=cutoff_time, processed=True).count()
        error_events = PaymentWebhookEvent.objects.filter(created_at__gte=cutoff_time, processing_error__isnull=False).exclude(processing_error='').count()
        
        self.stdout.write(f"\n📈 Summary:")
        self.stdout.write("-" * 80)
        self.stdout.write(f"Total webhook events: {total_events}")
        self.stdout.write(f"Successfully processed: {processed_events}")
        self.stdout.write(f"Failed events: {error_events}")
        self.stdout.write(f"Success rate: {(processed_events/total_events*100):.1f}%" if total_events > 0 else "No events")
        
        self.stdout.write(self.style.SUCCESS("\n✅ Webhook monitoring completed!")) 
from django.utils import timezone
from datetime import timedelta
import os
import json
from payments.models import PaymentWebhookEvent, Payment


class Command(BaseCommand):
    help = 'Monitor Stripe webhook activity and logs'

    def add_arguments(self, parser):
        parser.add_argument(
            '--hours',
            type=int,
            default=24,
            help='Number of hours to look back (default: 24)'
        )
        parser.add_argument(
            '--show-errors',
            action='store_true',
            help='Show only webhook events with errors'
        )
        parser.add_argument(
            '--show-unprocessed',
            action='store_true',
            help='Show only unprocessed webhook events'
        )
        parser.add_argument(
            '--log-file',
            action='store_true',
            help='Show recent entries from stripe_webhooks.log file'
        )

    def handle(self, *args, **options):
        hours = options['hours']
        show_errors = options['show_errors']
        show_unprocessed = options['show_unprocessed']
        show_log_file = options['log_file']
        
        cutoff_time = timezone.now() - timedelta(hours=hours)
        
        self.stdout.write(self.style.SUCCESS(f"🔍 Monitoring Stripe webhooks (last {hours} hours)"))
        self.stdout.write("=" * 80)
        
        # Check webhook events in database
        if show_errors:
            events = PaymentWebhookEvent.objects.filter(
                created_at__gte=cutoff_time,
                processing_error__isnull=False
            ).exclude(processing_error='')
        elif show_unprocessed:
            events = PaymentWebhookEvent.objects.filter(
                created_at__gte=cutoff_time,
                processed=False
            )
        else:
            events = PaymentWebhookEvent.objects.filter(created_at__gte=cutoff_time)
        
        self.stdout.write(f"📊 Found {events.count()} webhook events")
        
        if events.exists():
            self.stdout.write("\n📋 Recent Webhook Events:")
            self.stdout.write("-" * 80)
            
            for event in events.order_by('-created_at')[:20]:  # Show last 20
                status_icon = "✅" if event.processed else "⏳"
                error_icon = "❌" if event.processing_error else ""
                
                self.stdout.write(
                    f"{status_icon} {event.stripe_event_id} | "
                    f"{event.event_type} | "
                    f"{event.created_at.strftime('%Y-%m-%d %H:%M:%S')} | "
                    f"{'Processed' if event.processed else 'Pending'}"
                )
                
                if event.processing_error:
                    self.stdout.write(f"   {error_icon} Error: {event.processing_error}")
        
        # Check recent payments
        recent_payments = Payment.objects.filter(
            created_at__gte=cutoff_time
        ).order_by('-created_at')
        
        self.stdout.write(f"\n💰 Recent Payments ({recent_payments.count()}):")
        self.stdout.write("-" * 80)
        
        for payment in recent_payments[:10]:  # Show last 10
            status_icon = {
                'pending': '⏳',
                'completed': '✅',
                'failed': '❌',
                'cancelled': '🚫'
            }.get(payment.status, '❓')
            
            self.stdout.write(
                f"{status_icon} {payment.payment_id} | "
                f"{payment.payment_type} | "
                f"{payment.amount} {payment.currency} | "
                f"{payment.status} | "
                f"{payment.created_at.strftime('%Y-%m-%d %H:%M:%S')}"
            )
        
        # Show log file entries if requested
        if show_log_file:
            log_file = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))), 'logs', 'stripe_webhooks.log')
            
            if os.path.exists(log_file):
                self.stdout.write(f"\n📄 Recent Log Entries from {log_file}:")
                self.stdout.write("-" * 80)
                
                try:
                    with open(log_file, 'r') as f:
                        lines = f.readlines()
                        # Show last 20 lines
                        for line in lines[-20:]:
                            self.stdout.write(line.rstrip())
                except Exception as e:
                    self.stdout.write(self.style.ERROR(f"Error reading log file: {e}"))
            else:
                self.stdout.write(self.style.WARNING(f"Log file not found: {log_file}"))
        
        # Summary statistics
        total_events = PaymentWebhookEvent.objects.filter(created_at__gte=cutoff_time).count()
        processed_events = PaymentWebhookEvent.objects.filter(created_at__gte=cutoff_time, processed=True).count()
        error_events = PaymentWebhookEvent.objects.filter(created_at__gte=cutoff_time, processing_error__isnull=False).exclude(processing_error='').count()
        
        self.stdout.write(f"\n📈 Summary:")
        self.stdout.write("-" * 80)
        self.stdout.write(f"Total webhook events: {total_events}")
        self.stdout.write(f"Successfully processed: {processed_events}")
        self.stdout.write(f"Failed events: {error_events}")
        self.stdout.write(f"Success rate: {(processed_events/total_events*100):.1f}%" if total_events > 0 else "No events")
        
        self.stdout.write(self.style.SUCCESS("\n✅ Webhook monitoring completed!")) 