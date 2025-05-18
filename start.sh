#!/bin/bash

# Configurações
MAX_DB_RETRIES=30
RETRY_INTERVAL=5
ATTEMPT=1

# Função para testar conexão com o MySQL
test_db_connection() {
    echo "Tentando conectar ao MySQL (tentativa $ATTEMPT/$MAX_DB_RETRIES)..."
    mysql -h"$DB_HOST" -P"$DB_PORT" -u"$DB_USER" -p"$DB_PASSWORD" \
          --connect-timeout=30 \
          -e "SHOW STATUS LIKE 'Uptime';" "$DB_NAME" >/dev/null 2>&1
    return $?
}
# Aguardar MySQL ficar disponível
if [ -n "$DB_HOST" ]; then
    while [ $ATTEMPT -le $MAX_DB_RETRIES ]; do
        if test_db_connection; then
            echo "Conexão com MySQL estabelecida com sucesso!"
            break
        fi

        if [ $ATTEMPT -eq $MAX_DB_RETRIES ]; then
            echo "ERRO: Não foi possível conectar ao MySQL após $MAX_DB_RETRIES tentativas"
            exit 1
        fi

        echo "MySQL não está disponível. Tentando novamente em $RETRY_INTERVAL segundos..."
        sleep $RETRY_INTERVAL
        ATTEMPT=$((ATTEMPT+1))
    done
fi

# Iniciar Xvfb no background
Xvfb :99 -screen 0 1024x768x24 > /dev/null 2>&1 &

# Exportar variáveis de ambiente necessárias
export DISPLAY=:99
export CHROME_BIN=/usr/bin/google-chrome
export CHROMEDRIVER_PATH=/usr/local/bin/chromedriver

# Iniciar a aplicação
echo "Iniciando a aplicação..."
exec gunicorn app:app \
    --bind 0.0.0.0:8000 \
    --workers 1 \
    --threads 4 \
    --worker-class gthread \
    --timeout 120 \
    --log-level info \
    --access-logfile - \
    --error-logfile -