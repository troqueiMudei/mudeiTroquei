#!/bin/bash
set -e

# Function to test MySQL connection
test_mysql_connection() {
    mysqladmin ping -h"viaduct.proxy.rlwy.net" -P"24171" -u"root" -p"SOiZeRqyiKiUqqCIcdMrGncUJzzRrIji" --silent
}

# Wait for MySQL
echo "Waiting for MySQL to become available..."
RETRIES=30
until test_mysql_connection || [ $RETRIES -eq 0 ]; do
    echo "Waiting for MySQL connection, $((RETRIES--)) remaining attempts..."
    sleep 2
done

if [ $RETRIES -eq 0 ]; then
    echo "Could not connect to MySQL, exiting..."
    exit 1
fi

echo "MySQL is available"

# Start application with gunicorn
exec gunicorn --bind 0.0.0.0:8000 \
    --workers 4 \
    --timeout 120 \
    --access-logfile - \
    --error-logfile - \
    app:app