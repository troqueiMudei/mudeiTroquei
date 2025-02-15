#!/bin/bash

# Aguardar o MySQL ficar disponível
echo "Aguardando o MySQL ficar disponível..."
while ! mysqladmin ping -h"viaduct.proxy.rlwy.net" -P"24171" -u"root" -p"SOiZeRqyiKiUqqCIcdMrGncUJzzRrIji" --silent; do
    echo "Aguardando conexão com MySQL..."
    sleep 2
done

echo "MySQL está disponível"

# Iniciar a aplicação
exec gunicorn --bind 0.0.0.0:8000 app:app --timeout 120