#!/bin/bash

# Aguardar o MySQL ficar disponível
echo "Aguardando o MySQL ficar disponível..."
while ! mysqladmin ping -h"$MYSQLHOST" -P"$MYSQLPORT" -u"$MYSQLUSER" -p"$MYSQLPASSWORD" --silent; do
    echo "Aguardando conexão com MySQL..."
    echo "Host: $MYSQLHOST"
    echo "Port: $MYSQLPORT"
    echo "User: $MYSQLUSER"
    echo "Database: $MYSQLDATABASE"
    sleep 2
done

echo "MySQL está disponível"

# Iniciar a aplicação
exec gunicorn --bind 0.0.0.0:8000 app:app --timeout 120