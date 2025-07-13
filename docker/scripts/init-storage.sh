#!/bin/bash
# docker/scripts/init-storage.sh
# Initialize persistent storage directories

set -e

echo "🚀 Initializing persistent storage directories..."

# Create storage directories
STORAGE_DIRS=(
    "storage/postgres"
    "storage/redis" 
    "storage/static"
    "storage/media"
    "storage/logs"
    "storage/ssl"
    "storage/nginx-logs"
    "backups/postgres"
    "backups/media"
)

for dir in "${STORAGE_DIRS[@]}"; do
    if [ ! -d "$dir" ]; then
        mkdir -p "$dir"
        echo "✅ Created directory: $dir"
    else
        echo "ℹ️  Directory already exists: $dir"
    fi
done

# Set proper permissions
echo "🔐 Setting proper permissions..."

# Media directory - needs write access for web container
chmod 755 storage/media
chmod 755 storage/static
chmod 755 storage/logs

# Database directory - needs write access for postgres
chmod 700 storage/postgres

# Redis directory
chmod 755 storage/redis

# SSL directory
chmod 700 storage/ssl

echo "✅ Storage directories initialized successfully!"

# Create .gitkeep files to preserve directory structure
for dir in "${STORAGE_DIRS[@]}"; do
    if [ ! -f "$dir/.gitkeep" ]; then
        touch "$dir/.gitkeep"
    fi
done

echo "📁 Directory structure preserved with .gitkeep files"