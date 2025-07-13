#!/bin/bash
set -e

# Wait for database
echo "Waiting for database..."
./docker/scripts/wait-for-it.sh db:5432 --timeout=30 --strict

# Wait for Redis
echo "Waiting for Redis..."
./docker/scripts/wait-for-it.sh redis:6379 --timeout=30 --strict

# Run migrations
echo "Running database migrations..."
python manage.py migrate --noinput

# Create initial data
echo "Creating initial data..."
python manage.py create_initial_data

# Collect static files
echo "Collecting static files..."
python manage.py collectstatic --noinput

# Create superuser if it doesn't exist
echo "Creating superuser..."
python manage.py shell << EOF
from apps.accounts.models import User
if not User.objects.filter(email='admin@labmyshare.com').exists():
    User.objects.create_superuser(
        username='admin',
        email='admin@labmyshare.com',
        password='admin123',
        first_name='Admin',
        last_name='User'
    )
    print('Superuser created: admin@labmyshare.com / admin123')
else:
    print('Superuser already exists')
EOF

echo "Starting application..."
exec "$@"
