#!/bin/bash
set -eo pipefail

# Configurações
XVFB_DISPLAY=":99"
SCREEN_RESOLUTION="1920x1080x24"
MYSQL_HOST="viaduct.proxy.rlwy.net"
MYSQL_PORT="24171"
MYSQL_USER="root"
MYSQL_PASSWORD="SOiZeRqyiKiUqqCIcdMrGncUJzzRrIji"
MAX_RETRIES=30
RETRY_DELAY=2

# Iniciar Xvfb com configurações otimizadas
Xvfb $XVFB_DISPLAY -screen 0 $SCREEN_RESOLUTION \
  -ac \
  +extension RANDR \
  +extension GLX \
  +extension MIT-SHM \
  -nolisten tcp \
  > /dev/null 2>&1 &
export DISPLAY=$XVFB_DISPLAY

# Função para testar conexão MySQL com timeout
test_mysql_connection() {
    timeout 5 mysqladmin ping \
        -h"$MYSQL_HOST" \
        -P"$MYSQL_PORT" \
        -u"$MYSQL_USER" \
        -p"$MYSQL_PASSWORD" \
        --silent || return 1
}

# Esperar pelo MySQL com tratamento de erro melhorado
echo "Waiting for MySQL to become available..."
retry_count=0
while [ $retry_count -lt $MAX_RETRIES ]; do
    if test_mysql_connection; then
        echo "MySQL is available!"
        break
    else
        retry_count=$((retry_count+1))
        echo "Waiting for MySQL connection... (attempt $retry_count/$MAX_RETRIES)"
        sleep $RETRY_DELAY
    fi
done

if [ $retry_count -eq $MAX_RETRIES ]; then
    echo "ERROR: Could not connect to MySQL after $MAX_RETRIES attempts" >&2
    exit 1
fi

# Verificar se o Xvfb está rodando
if ! ps aux | grep -q "[X]vfb $XVFB_DISPLAY"; then
    echo "ERROR: Xvfb failed to start" >&2
    exit 1
fi

# Configurações otimizadas para o Gunicorn
WORKERS=$((2 * $(nproc) + 1))  # Fórmula recomendada para workers
THREADS=4
TIMEOUT=300
MAX_REQUESTS=1000
MAX_REQUESTS_JITTER=50

echo "Starting application with $WORKERS workers and $THREADS threads..."

# Iniciar o Gunicorn com configurações otimizadas
exec gunicorn app:app \
    --bind 0.0.0.0:8000 \
    --workers $WORKERS \
    --timeout $TIMEOUT \
    --max-requests $MAX_REQUESTS \
    --max-requests-jitter $MAX_REQUESTS_JITTER \
    --worker-class gthread \
    --threads $THREADS \
    --access-logfile - \
    --error-logfile - \
    --log-level info \
    --capture-output \
    --enable-stdio-inheritance