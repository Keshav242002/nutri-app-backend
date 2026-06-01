#!/bin/bash
set -e

echo "Running migrations..."
python manage.py migrate --noinput

echo "Seeding recipes (idempotent)..."
python manage.py seed_recipes

echo "Collecting static files..."
python manage.py collectstatic --noinput

echo "Starting server..."
exec "$@"
