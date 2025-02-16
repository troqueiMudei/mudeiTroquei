#!/bin/bash
set -e

# Configurar limites de sistema
ulimit -n 65536
ulimit -u 2048

# Limpar arquivos temporários
rm -rf /tmp/chrome_cache/*
rm -rf /tmp/.com.google.Chrome.*

# Iniciar Xvfb com maior resolução e profundidade de cor
Xvfb :99 -screen 0 1920x1080x24 -ac +extension RANDR > /dev/null 2>&1 &

# Aguardar Xvfb iniciar
sleep 2

# Function to test MySQL connection
test_mysql_connection() {
    mysqladmin ping -h"$MYSQL_HOST" -P"$MYSQL_PORT" -u"$MYSQL_USER" -p"$MYSQL_PASSWORD" --silent
}

# Wait for MySQL with timeout
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
    --workers 2 \
    --timeout 300 \
    --max-requests 1000 \
    --max-requests-jitter 50 \
    --worker-class gthread \
    --threads 4 \
    --worker-tmp-dir /dev/shm \
    --access-logfile - \
    --error-logfile - \
    --log-level debug \
    app:app