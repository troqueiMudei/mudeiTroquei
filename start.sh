#!/bin/bash

# Aguardar o MySQL ficar disponível
echo "Aguardando o MySQL ficar disponível..."
while ! mysqladmin ping -h"mysql://root:SOiZeRqyiKiUqqCIcdMrGncUJzzRrIji@mysql" -P"3306" -u"root" -p"SOiZeRqyiKiUqqCIcdMrGncUJzzRrIji" --silent; do
    echo "Aguardando conexão com MySQL..."
    echo "Host: mysql://root:SOiZeRqyiKiUqqCIcdMrGncUJzzRrIji@mysql"
    echo "Port: 3306"
    echo "User: root"
    echo "Database: railway"
    sleep 2
done

echo "MySQL está disponível"

# Iniciar a aplicação
exec gunicorn --bind 0.0.0.0:8000 app:app --timeout 120