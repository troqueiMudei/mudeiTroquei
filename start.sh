#!/bin/bash

# Aguardar o MySQL ficar disponível
echo "Aguardando o MySQL ficar disponível..."
while ! mysqladmin ping -h"${MYSQLHOST/mysql://root:SOiZeRqyiKiUqqCIcdMrGncUJzzRrIji@viaduct.proxy.rlwy.net:24171/railway/containers-us-west-207.railway.app}" -P"$MYSQLPORT" -u"$MYSQLUSER" -p"$MYSQLPASSWORD" --silent; do
    echo "Aguardando conexão com MySQL..."
    sleep 2
done

echo "MySQL está disponível"

# Iniciar a aplicação
exec gunicorn --bind 0.0.0.0:8000 app:app --timeout 120