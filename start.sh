#!/bin/bash

# Extrair o host da URL do MySQL
MYSQL_HOST=$(echo $MYSQL_URL | sed -E 's/.*@([^:]+).*/\1/')

echo "Tentando conectar ao host: $MYSQL_HOST"

# Aguardar o MySQL ficar disponível
while ! mysqladmin ping -h"$MYSQL_HOST" -P"$MYSQLPORT" -u"$MYSQLUSER" -p"$MYSQLPASSWORD" --silent; do
    echo "Aguardando conexão com MySQL..."
    echo "Host: $MYSQL_HOST"
    echo "Port: $MYSQLPORT"
    echo "User: $MYSQLUSER"
    sleep 2
done

echo "MySQL está disponível"

# Iniciar a aplicação
exec gunicorn --bind 0.0.0.0:8000 app:app --timeout 120