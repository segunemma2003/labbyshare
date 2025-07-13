from django.core.management.base import BaseCommand
from django.db import connection
from django.conf import settings


class Command(BaseCommand):
    help = 'Optimize database for production performance'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--analyze',
            action='store_true',
            help='Run ANALYZE on all tables',
        )
        parser.add_argument(
            '--vacuum',
            action='store_true',
            help='Run VACUUM on all tables',
        )
        parser.add_argument(
            '--reindex',
            action='store_true',
            help='Reindex all tables',
        )
    
    def handle(self, *args, **options):
        with connection.cursor() as cursor:
            
            if options['analyze']:
                self.stdout.write('Running ANALYZE...')
                cursor.execute('ANALYZE;')
                self.stdout.write(self.style.SUCCESS('ANALYZE completed'))
            
            if options['vacuum']:
                self.stdout.write('Running VACUUM...')
                cursor.execute('VACUUM;')
                self.stdout.write(self.style.SUCCESS('VACUUM completed'))
            
            if options['reindex']:
                self.stdout.write('Reindexing database...')
                cursor.execute('REINDEX DATABASE %s;' % settings.DATABASES['default']['NAME'])
                self.stdout.write(self.style.SUCCESS('REINDEX completed'))
            
            # Show database statistics
            self.show_database_stats(cursor)
    
    def show_database_stats(self, cursor):
        """Show database performance statistics"""
        self.stdout.write('\n--- Database Statistics ---')
        
        # Table sizes
        cursor.execute("""
            SELECT 
                schemaname,
                tablename,
                pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) as size,
                pg_total_relation_size(schemaname||'.'||tablename) as size_bytes
            FROM pg_tables 
            WHERE schemaname = 'public'
            ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC
            LIMIT 10;
        """)
        
        self.stdout.write('\nTop 10 Largest Tables:')
        for row in cursor.fetchall():
            self.stdout.write(f'{row[1]}: {row[2]}')
        
        # Index usage
        cursor.execute("""
            SELECT 
                indexrelname,
                idx_tup_read,
                idx_tup_fetch,
                pg_size_pretty(pg_relation_size(indexrelname::regclass)) as size
            FROM pg_stat_user_indexes 
            ORDER BY idx_tup_read DESC
            LIMIT 10;
        """)
        
        self.stdout.write('\nTop 10 Most Used Indexes:')
        for row in cursor.fetchall():
            self.stdout.write(f'{row[0]}: {row[1]} reads, {row[3]}')
